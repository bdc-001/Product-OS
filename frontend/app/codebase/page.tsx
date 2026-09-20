"use client";

import { SourcePanel } from "./source-panel";
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useEffect, useState } from "react";
import { api, type CodebaseAsk, type CodebaseBranch, type CodebaseQueryIndex, type CodebaseStatus } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, EmptyState, FrostCard, ListRow, MarkdownBlock, PageBody, PageHeader, PagedList, PillButton, Section, StatusChip } from "@/app/ui";
import { apple } from "@/app/theme";

function parseDate(raw?: string) {
  const text = (raw || "").trim();
  if (!text) return null;
  const iso = text.match(/(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?/);
  if (!iso) return null;
  const value = new Date(`${iso[1]}T${iso[2] || "00:00"}:00`);
  if (Number.isNaN(value.getTime())) return null;
  return value;
}

function formatDayHeading(day: string) {
  const value = parseDate(day);
  if (!value) return day === "unknown" ? "Unknown date" : day;
  const weekday = value.toLocaleDateString("en-GB", { weekday: "short" });
  const rest = value
    .toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
    .replace("Sept", "Sep");
  return `${weekday} ${rest}`;
}

function formatTime(raw?: string) {
  const value = parseDate(raw);
  if (!value) return "";
  return value.toLocaleTimeString("en-GB", { hour: "numeric", minute: "2-digit", hour12: true });
}

function localDay(raw?: string) {
  const value = parseDate(raw);
  if (!value) return "";
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function todayKey() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function groupByDay(rows: CodebaseBranch[]) {
  const groups: { day: string; label: string; rows: CodebaseBranch[] }[] = [];
  const index = new Map<string, number>();
  for (const row of rows) {
    const day = row.day || localDay(row.date) || "unknown";
    let slot = index.get(day);
    if (slot === undefined) {
      slot = groups.length;
      index.set(day, slot);
      groups.push({
        day,
        label: day === "unknown" ? "Unknown date" : formatDayHeading(day),
        rows: [],
      });
    }
    groups[slot].rows.push(row);
  }
  groups.sort((a, b) => b.day.localeCompare(a.day));
  for (const group of groups) {
    group.rows.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  }
  return groups;
}

function stashDetails(status: CodebaseStatus | null) {
  const raw = (status?.stashed_note || "").trim();
  if (!raw) return null;
  const from = raw.match(/from\s+([^\s.]+)/i)?.[1] || "";
  return { from, raw };
}

export default function CodebasePage() {
  const [status, setStatus] = useState<CodebaseStatus | null>(null);
  const [branches, setBranches] = useState<CodebaseBranch[]>([]);
  const [asks, setAsks] = useState<CodebaseAsk[]>([]);
  const [currentAsk, setCurrentAsk] = useState<CodebaseAsk | null>(null);
  const [question, setQuestion] = useState("");
  const [picked, setPicked] = useState("");
  const [query, setQuery] = useState<CodebaseQueryIndex | null>(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dayOpen, setDayOpen] = useState<Record<string, boolean>>({});
  const { tick } = useRefresh();

  async function loadStatus() {
    const [next, history] = await Promise.all([api.codebaseStatus(), api.codebaseAsks().catch(() => ({ asks: [] as CodebaseAsk[] }))]);
    setStatus(next);
    setAsks(history.asks || []);
    setPicked((current) => current || next.indexed_branch || "");
  }

  function showRemoteMessage(data: { error?: string; remote_blocked?: boolean; fetched?: boolean }) {
    const message = data.error || "";
    if (data.remote_blocked || /whitelist|VPN|local branches only/i.test(message)) {
      setNotice(message);
      setError("");
      return;
    }
    setError(message);
    if (data.fetched) setNotice("");
  }

  useEffect(() => {
    loadStatus().catch((err) => setError(String(err)));
    api
      .codebaseBranches(false)
      .then((data) => {
        setBranches(data.branches || []);
        showRemoteMessage(data);
      })
      .catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  useEffect(() => {
    if (!picked) {
      setQuery(null);
      return;
    }
    let cancelled = false;
    api
      .codebaseQueryIndex(picked)
      .then((data) => {
        if (!cancelled) setQuery(data);
      })
      .catch(() => {
        if (!cancelled) setQuery(null);
      });
    return () => {
      cancelled = true;
    };
  }, [picked]);

  useEffect(() => {
    const rows = picked ? asks.filter((row) => row.branch === picked) : asks;
    setCurrentAsk((cur) => {
      if (cur && rows.some((row) => row.id === cur.id)) return cur;
      return rows[0] || null;
    });
  }, [picked, asks]);

  async function useAsProduct(name: string) {
    const branch = name || picked;
    if (!branch) return;
    setBusy("index");
    setError("");
    setPicked(branch);
    try {
      await api.codebaseSetDataBranch(branch).catch(() => null);
      const next = await api.codebaseIndex(branch);
      if (next && (next.indexed_branch || next.branch)) setStatus(next);
      else setStatus(await api.codebaseStatus());
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!question.trim() || !picked) return;
    setBusy("ask");
    setError("");
    try {
      const row = await api.codebaseAsk(question.trim(), picked);
      setCurrentAsk(row);
      setAsks((existing) => [row, ...existing.filter((item) => item.id !== row.id)]);
      setQuestion("");
      const next = await api.codebaseQueryIndex(picked).catch(() => null);
      if (next) setQuery(next);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  const indexed = status?.indexed_branch || "";
  const dataBranch = status?.data_branch || "";
  const stash = stashDetails(status);
  const askReady = Boolean(picked && query?.ready && query.branch === picked);
  const subtitle = picked
    ? askReady
      ? `Ask ${picked}`
      : picked
    : status?.indexed_at_label
      ? /^indexed\b/i.test(status.indexed_at_label)
        ? status.indexed_at_label
        : `Indexed ${status.indexed_at_label}`
      : status?.exists
        ? "Select a branch to ask"
        : "go_services";
  const listedBranches = (() => {
    const names = new Set(branches.map((row) => row.name));
    const extra: CodebaseBranch[] = [];
    if (indexed && !names.has(indexed)) {
      extra.push({
        name: indexed,
        sha: status?.indexed_sha || "",
        date: status?.commit_at || status?.recent_commits?.[0]?.date || "",
        message: status?.indexed_message || "indexed",
        current: true,
      });
      names.add(indexed);
    }
    if (dataBranch && !names.has(dataBranch)) {
      extra.push({
        name: dataBranch,
        sha: "",
        date: "",
        message: "data branch",
        current: false,
      });
    }
    return extra.length ? [...extra, ...branches] : branches;
  })();
  const needle = filter.trim().toLowerCase();
  const visibleBranches = needle
    ? listedBranches.filter(
        (row) => row.name.toLowerCase().includes(needle) || (row.message || "").toLowerCase().includes(needle),
      )
    : listedBranches;
  const dayGroups = groupByDay(visibleBranches);
  const today = todayKey();
  const searching = Boolean(needle);
  const notableDays = new Set(
    listedBranches
      .filter((row) => row.current || row.name === indexed || row.name === picked)
      .map((row) => row.day || localDay(row.date) || "unknown"),
  );

  function dayExpanded(day: string) {
    if (searching) return true;
    if (Object.prototype.hasOwnProperty.call(dayOpen, day)) return dayOpen[day];
    return day === today || notableDays.has(day);
  }

  const branchAsks = picked ? asks.filter((row) => row.branch === picked) : asks;

  return (
    <PageBody wide>
      <SourcePanel branch={picked} />
      <PageHeader title="Codebase" subtitle={subtitle} />
      {error ? <Banner severity="error">{error}</Banner> : null}
      {notice ? <Banner severity="info">{notice}</Banner> : null}

      <FrostCard sx={{ mb: 3 }}>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "minmax(0,1fr) auto" },
            gap: 2,
            alignItems: { xs: "stretch", md: "center" },
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", color: apple.muted, mb: 0.75 }}>
              Product branch
            </Typography>
            <Typography sx={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em", color: apple.text, overflowWrap: "anywhere" }}>
              {indexed || "None selected"}
            </Typography>
            <Typography sx={{ mt: 0.75, fontSize: 15, color: apple.muted, maxWidth: 520 }}>
              PRDs, Comms, Artifacts, and the rest of the product run on this branch. Pick one below, then set it as product — it indexes automatically.
            </Typography>
            {picked && picked !== indexed ? (
              <Typography sx={{ mt: 1, fontSize: 13, color: apple.muted }}>
                Selected: <Box component="span" sx={{ color: apple.text, fontWeight: 600 }}>{picked}</Box>
              </Typography>
            ) : null}
          </Box>
          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" justifyContent={{ xs: "flex-start", md: "flex-end" }}>
            <PillButton type="button" onClick={() => useAsProduct(picked)} disabled={busy === "index" || !picked}>
              {busy === "index" ? "Indexing…" : picked && picked === indexed ? "Re-index product" : picked ? "Use as product" : "Select a branch"}
            </PillButton>
            <PillButton
              variant="gray"
              type="button"
              disabled={!picked}
              onClick={() => document.getElementById("codebase-ask")?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              Ask this branch
            </PillButton>
          </Stack>
        </Box>
      </FrostCard>
      {status && !status.exists ? <Banner severity="error">CODEBASE_PATH is not a folder. Set it to your Desktop go_services clone in .env.</Banner> : null}
      {status?.pull_error && !notice ? (
        <Banner severity={/whitelist|VPN|local branches/i.test(status.pull_error) ? "info" : "warning"}>{status.pull_error}</Banner>
      ) : null}
      {status?.dirty && !stash ? (
        <Banner severity="warning">Uncommitted changes in the clone. Using a branch as product stashes them, then pulls. Asking a branch does not.</Banner>
      ) : null}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3, alignItems: "start" }}>
        <div>
          <Section title="Branches" count={visibleBranches.length}>
            <TextField
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              placeholder="Find a branch"
              aria-label="Find a branch"
              size="small"
              fullWidth
              sx={{ mb: 1.5, "& .MuiOutlinedInput-root": { borderRadius: "999px" } }}
            />
            {dayGroups.length ? (
              dayGroups.map(({ day, label, rows }) => {
                const open = dayExpanded(day);
                return (
                  <Accordion
                    key={day}
                    disableGutters
                    expanded={open}
                    onChange={() =>
                      setDayOpen((current) => {
                        const was = Object.prototype.hasOwnProperty.call(current, day) ? current[day] : day === today;
                        return { ...current, [day]: !was };
                      })
                    }
                    sx={{ "&:before": { display: "none" }, border: `1px solid ${apple.hairline}`, borderRadius: "16px !important", mb: 1, overflow: "visible", bgcolor: "#fff" }}
                  >
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Stack direction="row" justifyContent="space-between" sx={{ width: "100%", pr: 1 }}>
                        <Typography sx={{ fontSize: 15, fontWeight: 500 }}>{label}</Typography>
                        <Typography sx={{ fontSize: 13, color: apple.muted }}>{rows.length}</Typography>
                      </Stack>
                    </AccordionSummary>
                    <AccordionDetails>
                      <PagedList
                        items={rows}
                        resetKey={`${day}-${needle}`}
                        getKey={(row) => row.name}
                        renderItem={(row) => {
                          const on = picked === row.name;
                          const time = formatTime(row.date);
                          return (
                            <ListRow
                              selected={on}
                              current={Boolean(row.current)}
                              disabled={busy === "index"}
                              onClick={() => setPicked(row.name)}
                            >
                              <Typography sx={{ fontSize: 15, fontWeight: 600 }}>{row.name}</Typography>
                              <Typography sx={{ fontSize: 13, color: apple.muted }}>{row.message || "No commit message"}</Typography>
                              <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 0.75 }}>
                                {row.merged ? <StatusChip label={`Merged${time ? ` ${time}` : ""}`} /> : time ? <StatusChip label={time} /> : null}
                                {indexed === row.name ? <StatusChip label="Product" tone="ink" /> : null}
                                {row.current ? <StatusChip label="Checked out" tone={indexed === row.name ? "default" : "ink"} /> : null}
                                {on && askReady ? <StatusChip label="Ask-ready" /> : null}
                              </Stack>
                            </ListRow>
                          );
                        }}
                      />
                    </AccordionDetails>
                  </Accordion>
                );
              })
            ) : (
              <EmptyState>{listedBranches.length ? "No branch matches that search." : "No origin branches yet. Refresh in the top bar."}</EmptyState>
            )}
          </Section>

        </div>

        <div>
          <FrostCard id="codebase-ask">
            <Section title="Ask">
              <Typography sx={{ mb: 1.5, fontSize: 15, color: apple.muted }}>
                {picked
                  ? query?.error && !askReady
                    ? query.error
                    : askReady
                      ? `Local git index of ${picked}${query?.sha ? ` @ ${query.sha}` : ""}${query?.module_count ? ` · ${query.module_count} modules` : ""}. No checkout.`
                      : `Ask builds a local git index of ${picked}. It does not check out the clone or replace the product (PRD / Comms) map.`
                  : "Select a branch on the left, then ask it."}
              </Typography>
              <Box component="form" onSubmit={ask}>
                <TextField
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder={picked ? `Ask ${picked}…` : "Select a branch on the left"}
                  disabled={!picked || Boolean(busy)}
                  multiline
                  minRows={3}
                  fullWidth
                />
                <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                  <PillButton type="submit" disabled={Boolean(busy) || !picked || !question.trim()}>
                    {busy === "ask" ? (askReady ? "Reading code…" : "Indexing locally…") : "Ask"}
                  </PillButton>
                </Stack>
              </Box>
              {currentAsk ? (
                <>
                  <Typography sx={{ mt: 2, fontSize: 13, color: apple.muted }}>
                    {currentAsk.question} · {currentAsk.branch}@{currentAsk.commit_sha}
                    {currentAsk.llm_used ? " · grounded" : " · local match"}
                  </Typography>
                  <Box sx={{ mt: 1 }}>
                    <MarkdownBlock>{currentAsk.answer}</MarkdownBlock>
                  </Box>
                  {currentAsk.citations?.length ? (
                    <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 1 }}>
                      {currentAsk.citations.map((cite, index) => (
                        <StatusChip key={`${cite.path}-${index}`} label={cite.path || "cite"} />
                      ))}
                    </Stack>
                  ) : null}
                </>
              ) : (
                <Box sx={{ mt: 2 }}>
                  <EmptyState>{picked ? `No questions asked of ${picked} yet.` : "Select a branch on the left, then ask it."}</EmptyState>
                </Box>
              )}
            </Section>
          </FrostCard>
          {branchAsks.length ? (
            <Section title="Recent asks" count={branchAsks.length}>
              <PagedList
                items={branchAsks}
                resetKey={picked}
                getKey={(row) => row.id}
                renderItem={(row) => (
                  <ListRow selected={currentAsk?.id === row.id} onClick={() => setCurrentAsk(row)}>
                    {row.question}
                  </ListRow>
                )}
              />
            </Section>
          ) : null}
        </div>
      </Box>
    </PageBody>
  );
}
