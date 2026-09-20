"use client";

import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import MenuItem from "@mui/material/MenuItem";
import Skeleton from "@mui/material/Skeleton";
import Snackbar from "@mui/material/Snackbar";
import ArrowOutwardRoundedIcon from "@mui/icons-material/ArrowOutwardRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import InputAdornment from "@mui/material/InputAdornment";
import Box from "@mui/material/Box";
import Collapse from "@mui/material/Collapse";
import Stack from "@/app/ui/stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, type Standup, type StandupItem } from "@/lib/api";
import { WEEK_TABS, buildPulse, itemKind, itemTicketKey, weekBuckets, type WeekView } from "@/lib/pulse";
import { useRefresh } from "@/app/refresh";
import { useCopilot } from "@/app/copilot/context";
import { Banner, EmptyState, FrostCard, PageBody, PagedList, PillButton, RemoveButton, Section, Segmented, StatusChip, SubSection, TicketLink } from "@/app/ui";
import { apple } from "@/app/theme";

const TAB_COPY: Record<WeekView, { title: string; why: string; empty: string }> = {
  week: {
    title: "This week",
    why: "Your weekly plan, with the next step for each item.",
    empty: "Refresh to load this week’s plan.",
  },
  other: {
    title: "Other work",
    why: "UAT, QA, handoff, and tickets outside the Monday plan.",
    empty: "Nothing parked outside this week.",
  },
  uat: {
    title: "UAT",
    why: "Waiting on you or a reviewer. Unblock these first.",
    empty: "No UAT loops right now.",
  },
  none: {
    title: "No ticket",
    why: "Capture these items in Jira to track ownership and progress.",
    empty: "Every item already has a ticket.",
  },
};

type LoadRow = NonNullable<Standup["dev_load"]>[number];

function stripJiraLinks(text: string) {
  return text
    .replace(/\[([A-Z][A-Z0-9]+-\d+)\]\(https?:\/\/[^)]+\)/gi, "$1")
    .replace(/https?:\/\/\S*atlassian\.net\/browse\/[A-Z][A-Z0-9]+-\d+\S*/gi, "")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function cleanTitle(item: StandupItem) {
  const key = itemTicketKey(item);
  let title = (item.title || "").trim();
  if (key) title = title.replace(new RegExp(`^${key}\\s*[:\\-–]?\\s*`, "i"), "");
  return title || key || "Untitled";
}

function ticketsFor(row: LoadRow) {
  if (row.tickets?.length) return row.tickets;
  const keys = row.keys?.length ? row.keys : [...(row.bug_keys || []), ...(row.task_keys || [])];
  return keys.map((key) => ({
    key,
    summary: key,
    kind: (row.bug_keys || []).includes(key) ? "bug" : "task",
  }));
}

function ActionCard({
  item,
  onHide,
  onAttach,
  busy,
}: {
  item: StandupItem;
  onHide: (item: StandupItem) => void;
  onAttach: (item: StandupItem, issueKey: string) => Promise<void>;
  busy: boolean;
}) {
  const key = itemTicketKey(item);
  const href = key ? `/issues/${key}` : "";
  const kind = itemKind(item);
  const body = item.body ? stripJiraLinks(item.body) : "";
  const title = cleanTitle(item);
  const missing = kind === "create_ticket" || !key;
  const [draft, setDraft] = useState("");
  const [suggestions, setSuggestions] = useState<{ issue_key: string; summary: string }[]>([]);
  const [attaching, setAttaching] = useState(false);
  const [attachError, setAttachError] = useState("");
  const { open } = useCopilot();

  useEffect(() => {
    const q = draft.trim();
    if (!missing || q.length < 2) {
      setSuggestions([]);
      return;
    }
    let active = true;
    const timer = window.setTimeout(() => {
      api
        .issuesPage("", q, "", "", 0)
        .then((data) => {
          if (!active) return;
          const rows = (data.issues || []).slice(0, 6).map((row) => ({
            issue_key: row.issue_key,
            summary: row.summary || row.issue_key,
          }));
          // Also allow raw key paste even if not in first page
          const keyMatch = q.toUpperCase().match(/\b([A-Z][A-Z0-9]+-\d+)\b/);
          if (keyMatch && !rows.some((row) => row.issue_key === keyMatch[1])) {
            rows.unshift({ issue_key: keyMatch[1], summary: keyMatch[1] });
          }
          setSuggestions(rows);
        })
        .catch(() => {
          if (active) setSuggestions([]);
        });
    }, 220);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [draft, missing]);

  async function attach(issueKey: string) {
    const normalized = issueKey.trim().toUpperCase();
    if (!normalized) return;
    setAttaching(true);
    setAttachError("");
    try {
      await onAttach(item, normalized);
      setDraft("");
      setSuggestions([]);
    } catch (err) {
      setAttachError(String(err));
    } finally {
      setAttaching(false);
    }
  }

  return (
    <FrostCard sx={{ borderLeft: kind === "blocker" || kind === "uat" ? `3px solid ${apple.danger}` : undefined }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
        <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" alignItems="center">
          {key ? <TicketLink issueKey={key} /> : <StatusChip label="No ticket" tone="danger" />}
          {item.status ? <StatusChip label={item.status} /> : null}
          {item.assignee ? <StatusChip label={item.assignee} /> : null}
          {kind === "uat" ? <StatusChip label="UAT" tone="danger" /> : null}
          {kind === "blocker" ? <StatusChip label="Blocker" tone="danger" /> : null}
        </Stack>
        <RemoveButton disabled={busy || attaching} onClick={() => onHide(item)} title="Hide from my view" />
      </Stack>
      <Typography variant="h3" sx={{ mt: 1.25 }}>
        {href ? <TicketLink issueKey={key}>{title}</TicketLink> : title}
      </Typography>
      {item.action ? (
        <Typography sx={{ mt: 0.75, fontWeight: 600, fontSize: 15 }}>{item.action}</Typography>
      ) : null}
      {(item.state_days || 0) >= 3 && !/^(done|closed|resolved)$/i.test(item.status || "") ? (
        <Typography sx={{ mt: 0.75, fontSize: 13, color: apple.danger, fontWeight: 600 }}>In this state for {item.state_days} days</Typography>
      ) : null}
      {item.why ? (
        <Typography sx={{ mt: 0.75, fontSize: 15, color: apple.muted }}>{item.why}</Typography>
      ) : body ? (
        <Typography sx={{ mt: 0.75, fontSize: 15, color: apple.muted }}>{body}</Typography>
      ) : null}
      {missing ? (
        <Box sx={{ mt: 1.5, p: 1.5, borderRadius: "12px", bgcolor: apple.hoverFill, border: `1px solid ${apple.hairline}` }}>
          <Typography sx={{ fontSize: 13, fontWeight: 600, mb: 1 }}>Attach a Jira ticket</Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "flex-start" }}>
            <Box sx={{ flex: 1, minWidth: 0, width: "100%" }}>
              <TextField
                size="small"
                fullWidth
                value={draft}
                disabled={attaching || busy}
                placeholder="AC-123 or search summary…"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    const match = draft.toUpperCase().match(/\b([A-Z][A-Z0-9]+-\d+)\b/);
                    if (match) void attach(match[1]);
                  }
                }}
              />
              {suggestions.length ? (
                <Stack spacing={0.5} sx={{ mt: 1 }}>
                  {suggestions.map((row) => (
                    <Button
                      key={row.issue_key}
                      disabled={attaching || busy}
                      onClick={() => void attach(row.issue_key)}
                      sx={{
                        justifyContent: "flex-start",
                        textAlign: "left",
                        borderRadius: "10px",
                        px: 1.25,
                        py: 0.75,
                        color: apple.text,
                        bgcolor: apple.page,
                        border: `1px solid ${apple.hairline}`,
                        "&:hover": { bgcolor: apple.page, borderColor: apple.ink },
                      }}
                    >
                      <TicketLink issueKey={row.issue_key} onClick={(event) => event.preventDefault()} />
                      <Typography component="span" sx={{ ml: 1, fontSize: 13, color: apple.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {row.summary}
                      </Typography>
                    </Button>
                  ))}
                </Stack>
              ) : null}
            </Box>
            <PillButton
              disabled={attaching || busy || !/\b[A-Z][A-Z0-9]+-\d+\b/i.test(draft)}
              onClick={() => {
                const match = draft.toUpperCase().match(/\b([A-Z][A-Z0-9]+-\d+)\b/);
                if (match) void attach(match[1]);
              }}
            >
              {attaching ? "Attaching…" : "Attach"}
            </PillButton>
          </Stack>
          {attachError ? <Typography sx={{ mt: 1, fontSize: 12, color: apple.danger }}>{attachError}</Typography> : null}
        </Box>
      ) : null}
      <Box sx={{ mt: 2, pt: 1.5, borderTop: `1px solid ${apple.hairline}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Typography sx={{ fontSize: 11, color: apple.muted }}>{missing ? "Needs a ticket" : "Tracked in Jira"}</Typography>
        {missing ? (
          <PillButton variant="text" onClick={() => open({ notes: `Create a Jira ticket for: ${title}` })} sx={{ py: 0.5, px: 0.5, fontSize: 12 }} endIcon={<ArrowOutwardRoundedIcon sx={{ fontSize: 14 }} />}>
            Or create in Copilot
          </PillButton>
        ) : (
          <PillButton variant="text" href={href} sx={{ py: 0.5, px: 0.5, fontSize: 12 }} endIcon={<ArrowOutwardRoundedIcon sx={{ fontSize: 14 }} />}>
            View ticket
          </PillButton>
        )}
      </Box>
    </FrostCard>
  );
}

function InProgressPanel({ rows }: { rows: LoadRow[] }) {
  const [open, setOpen] = useState<string>("");

  const cell = {
    whiteSpace: "nowrap" as const,
    fontSize: 13,
    py: 1,
    px: 1,
    borderColor: apple.hairline,
  };

  return (
    <FrostCard>
      <Section title="In progress" count={rows.length}>
        <SubSection title="Load by developer">
          {rows.length ? (
            <TableContainer sx={{ overflowX: "auto", mb: open ? 1.5 : 0 }}>
              <Table size="small" sx={{ tableLayout: "fixed", minWidth: 280 }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ ...cell, width: "44%", fontWeight: 600 }}>Developer</TableCell>
                    <TableCell align="right" sx={{ ...cell, width: "18%", fontWeight: 600 }}>
                      Bugs
                    </TableCell>
                    <TableCell align="right" sx={{ ...cell, width: "18%", fontWeight: 600 }}>
                      Tasks
                    </TableCell>
                    <TableCell align="right" sx={{ ...cell, width: "20%", fontWeight: 600 }}>
                      Total
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => {
                    const expanded = open === row.short;
                    const tickets = ticketsFor(row);
                    return (
                      <TableRow
                        key={row.short}
                        hover
                        selected={expanded}
                        onClick={() => setOpen(expanded ? "" : row.short)}
                        tabIndex={0}
                        aria-expanded={expanded}
                        aria-label={`Show tickets for ${row.name}`}
                        onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setOpen(expanded ? "" : row.short); } }}
                        sx={{
                          cursor: "pointer",
                          bgcolor: expanded ? apple.selFill : "transparent",
                          "& td": { borderColor: apple.hairline },
                        }}
                      >
                        <TableCell sx={cell}>
                          <Stack direction="row" alignItems="center" spacing={0.5}>
                            <ExpandMoreIcon
                              sx={{
                                fontSize: 18,
                                color: apple.muted,
                                transform: expanded ? "rotate(0deg)" : "rotate(-90deg)",
                                transition: `transform 0.3s ${apple.smooth}`,
                              }}
                            />
                            <Typography sx={{ fontSize: 13, fontWeight: expanded ? 600 : 400 }}>{row.name}</Typography>
                          </Stack>
                        </TableCell>
                        <TableCell align="right" sx={cell}>
                          {row.bugs ?? 0}
                        </TableCell>
                        <TableCell align="right" sx={cell}>
                          {row.tasks ?? Math.max(0, (row.in_progress || 0) - (row.bugs || 0))}
                        </TableCell>
                        <TableCell align="right" sx={{ ...cell, fontWeight: 700 }}>
                          {row.in_progress}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <EmptyState>Load unknown until Jira refresh.</EmptyState>
          )}
        </SubSection>
        {rows.map((row) => {
          const tickets = ticketsFor(row);
          const expanded = open === row.short;
          return (
            <Collapse key={`${row.short}-tickets`} in={expanded} timeout={280} unmountOnExit>
              <SubSection title={`Tickets · ${row.name}`}>
                {tickets.length ? (
                  <Stack spacing={1}>
                    {tickets.map((ticket) => (
                      <Box
                        key={ticket.key}
                        sx={{
                          border: `1px solid ${apple.hairline}`,
                          borderRadius: "14px",
                          px: 1.5,
                          py: 1,
                          bgcolor: apple.page,
                        }}
                      >
                        <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" alignItems="center" sx={{ mb: 0.5 }}>
                          <TicketLink issueKey={ticket.key} />
                          {ticket.kind ? <StatusChip label={ticket.kind} /> : null}
                        </Stack>
                        <Typography sx={{ fontSize: 13, color: apple.muted }}>{ticket.summary || ticket.key}</Typography>
                      </Box>
                    ))}
                  </Stack>
                ) : (
                  <EmptyState>No ticket keys stored for this developer.</EmptyState>
                )}
              </SubSection>
            </Collapse>
          );
        })}
      </Section>
    </FrostCard>
  );
}

export function HomeView() {
  const params = useSearchParams();
  const router = useRouter();
  const view = (WEEK_TABS.some((tab) => tab.id === params.get("view")) ? params.get("view") : "week") as WeekView;
  const [standup, setStandup] = useState<Standup | null>(null);
  const [name, setName] = useState("Arsalaan");
  const [health, setHealth] = useState<{ jira: boolean; cliq: boolean; llm: boolean } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("priority");
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [hidden, setHidden] = useState<{ card_key: string; title: string }[]>([]);
  const { tick } = useRefresh();

  async function loadSection(section: string) {
    try {
      const result = await api.dashboard(section);
      if(result.standup) setStandup(current=>({...current,...result.standup}) as Standup);
    } catch (err) { setError(`${section}: ${String(err)}`); }
  }
  async function load() {
    setError("");
    await Promise.all([
      ...["summary", "actions", "developer-load"].map(loadSection),
      api.workspaceSummary().then(data=>{setHealth(data);setName((data.pm_display_name||"Arsalaan").split(" ")[0]);}).catch(err=>setError(String(err))),
      api.hiddenCards().then(data=>setHidden(data.hidden||[])).catch(err=>setError(String(err))),
    ]);
  }

  useEffect(() => {
    load().catch((err) => setError(String(err))).finally(() => setLoading(false));
  }, [tick]);

  async function hideItem(item: StandupItem) {
    setPending(true);
    try {
      await api.hideCard({ issue_key: itemTicketKey(item), title: item.title });
      setNotice("Item hidden. You can bring it back from Hidden items.");
      await load();
    } catch (err) { setError(String(err)); }
    finally { setPending(false); }
  }

  async function attachTicket(item: StandupItem, issueKey: string) {
    setPending(true);
    try {
      await api.attachWeekTicket({
        issue_key: issueKey,
        title: item.title,
        card_key: item.card_key || "",
      });
      setNotice(`Attached ${issueKey.toUpperCase()} to this item.`);
      await loadSection("actions");
    } catch (err) {
      setError(String(err));
      throw err;
    } finally {
      setPending(false);
    }
  }

  async function restoreHidden(cardKey: string) {
    setPending(true);
    try {
      await api.unhideCard(cardKey);
      setNotice("Item restored to your workspace.");
      await load();
    } catch (err) { setError(String(err)); }
    finally { setPending(false); }
  }

  const buckets = useMemo(() => weekBuckets(standup), [standup]);
  const allItems = buckets[view] || [];
  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = allItems.filter((item) => [item.title, item.assignee, item.status, item.action, itemTicketKey(item)].some((value) => String(value || "").toLowerCase().includes(q)));
    const priority = (item: StandupItem) => itemKind(item) === "blocker" ? 3 : itemKind(item) === "uat" ? 2 : !itemTicketKey(item) ? 1 : 0;
    return [...filtered].sort((a, b) => sort === "title" ? cleanTitle(a).localeCompare(cleanTitle(b)) : sort === "age" ? (b.state_days || 0) - (a.state_days || 0) : priority(b) - priority(a));
  }, [allItems, query, sort]);
  const copy = TAB_COPY[view];
  const loadRows = standup?.dev_load || [];
  const pulse = buildPulse(standup, name);
  const counts: Record<WeekView, number> = {
    week: buckets.week.length,
    other: buckets.other.length,
    uat: buckets.uat.length,
    none: buckets.none.length,
  };

  if (loading) return <PageBody><Box role="status" aria-label="Loading your workspace"><Skeleton width="40%" height={64} /><Skeleton width="60%" /><Box sx={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 2, mt: 3 }}>{[1, 2, 3, 4].map((id) => <Skeleton key={id} variant="rounded" height={140} />)}</Box></Box></PageBody>;

  return (
    <PageBody>
      <Snackbar open={Boolean(notice)} autoHideDuration={5000} onClose={() => setNotice("")} message={notice} />
      {error ? <Banner severity="error">Could not update the workspace. {error} <Button size="small" onClick={() => load().catch((err) => setError(String(err)))}>Retry</Button></Banner> : null}
      {health && !health.jira ? <Banner severity="error">Jira is not connected.</Banner> : null}

      <Box sx={{ mb: 3.5 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: apple.muted, mb: 1 }}>Workspace overview</Typography>
        <Typography variant="h1" sx={{ fontSize: { xs: 30, md: 38 } }}>{pulse.greeting}</Typography>
        <Typography sx={{ mt: 1, fontSize: 15, color: apple.muted }}>{standup ? "Your priorities, conversations, and delivery work in one place." : "Refresh your sources to build your weekly overview."}</Typography>
        {standup?.window_label ? <Typography sx={{ mt: 0.75, fontSize: 12, color: apple.muted }}>{standup.window_label}</Typography> : null}
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" }, gap: 2, mb: 3.5 }}>
        {([
          { view: "week", label: "Planned this week", value: counts.week, detail: "Weekly commitments" },
          { view: "uat", label: "Ready for review", value: counts.uat, detail: "UAT & reviewer follow-ups" },
          { view: "none", label: "Needs a ticket", value: counts.none, detail: "Work to capture in Jira" },
          { view: "other", label: "Other work", value: counts.other, detail: "Beyond the weekly plan" },
        ] as const).map((metric) => <Button key={metric.view} onClick={() => { setQuery(""); router.push(`/?view=${metric.view}`); }} aria-pressed={view === metric.view} sx={{ display: "block", textAlign: "left", p: { xs: 2, md: 2.5 }, color: apple.text, bgcolor: apple.page, border: `1px solid ${view === metric.view ? apple.ink : apple.hairline}`, borderRadius: "16px", boxShadow: apple.shadow, "&:hover": { bgcolor: apple.hoverFill } }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}><Typography sx={{ fontSize: 12, fontWeight: 500 }}>{metric.label}</Typography><ArrowOutwardRoundedIcon sx={{ fontSize: 15, color: apple.muted }} /></Box>
          <Typography sx={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.04em", my: 0.5, fontVariantNumeric: "tabular-nums" }}>{standup ? metric.value : "—"}</Typography>
          <Typography sx={{ fontSize: 11, color: apple.muted }}>{metric.detail}</Typography>
        </Button>)}
      </Box>
      <Box sx={{ mb: 3, maxWidth: { xs: "100%", md: 720 } }}>
        <Segmented
          value={view}
          onChange={(id) => { setQuery(""); router.push(`/?view=${id}`); }}
          options={WEEK_TABS.map((tab) => ({
            id: tab.id,
            label: (
              <>
                <Box component="b" sx={{ fontWeight: 700, mr: 0.5 }}>
                  {counts[tab.id]}
                </Box>
                {tab.label}
              </>
            ),
          }))}
        />
      </Box>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1fr) 340px" },
          gap: 3,
          alignItems: "start",
        }}
      >
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{display:"flex",justifyContent:"flex-end"}}><PillButton variant="text" onClick={()=>loadSection("actions")} sx={{fontSize:12}}>Reload actions</PillButton></Box>
          <Section title={copy.title} count={items.length}>
            <Typography sx={{ mb: 2, fontSize: 14, color: apple.muted }}>{copy.why}</Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} sx={{ mb: 2.5 }}>
              <TextField size="small" fullWidth value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter by title, owner, or ticket…" slotProps={{ htmlInput: { "aria-label": "Filter action cards" }, input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon sx={{ fontSize: 18 }} /></InputAdornment> } }} />
              <TextField select size="small" value={sort} onChange={(event) => setSort(event.target.value)} label="Sort by" sx={{ minWidth: 150 }}><MenuItem value="priority">Priority</MenuItem><MenuItem value="age">Longest waiting</MenuItem><MenuItem value="title">Title A–Z</MenuItem></TextField>
            </Stack>
            <PagedList
              items={items}
              resetKey={`${view}-${query}-${sort}`}
              getKey={(item, index) => `${item.title}-${index}`}
              empty={<EmptyState>{query ? "No matching items. Try another title, owner, or ticket key." : copy.empty}{query ? <Button size="small" onClick={() => setQuery("")}>Clear filter</Button> : null}</EmptyState>}
              renderItem={(item) => <ActionCard item={item} onHide={hideItem} onAttach={attachTicket} busy={pending} />}
            />
          </Section>
        </Box>
        <Stack spacing={2.5} sx={{ position: { lg: "sticky" }, top: { lg: 100 }, minWidth: 0 }}>
          <FrostCard sx={{ bgcolor: apple.ink, color: "#fff", borderColor: apple.ink }}>
            <Typography sx={{ color: "#c5c5cc", fontSize: 11, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" }}>Focus next</Typography>
            <Typography sx={{ color: "#fff", fontSize: 18, fontWeight: 500, lineHeight: 1.45, mt: 1.5 }}>{standup ? (counts.uat ? `${counts.uat} items are waiting for review.` : counts.none ? `${counts.none} items need a ticket.` : "Make room for your next priority.") : "Bring your workspace up to date."}</Typography>
            <Typography sx={{ color: "#c5c5cc", fontSize: 13, mt: 1 }}>{standup ? "Start with the work you can move forward today." : "Use Refresh to pull the latest work from your sources."}</Typography>
            <PillButton href={counts.uat ? "/?view=uat" : counts.none ? "/?view=none" : "/roadmap"} variant="text" sx={{ color: "#fff", mt: 2, px: 0, fontSize: 13 }}>View {counts.uat ? "review queue" : counts.none ? "untracked work" : "roadmap"}</PillButton>
          </FrostCard>
          <Box><Box sx={{display:"flex",justifyContent:"flex-end"}}><PillButton variant="text" onClick={()=>loadSection("developer-load")} sx={{fontSize:12}}>Reload team load</PillButton></Box><InProgressPanel rows={loadRows} /></Box>
          {hidden.length ? (
            <FrostCard>
              <Section title="Hidden items" count={hidden.length}>
                <PagedList
                  items={hidden}
                  getKey={(row) => row.card_key}
                  renderItem={(row) => (
                    <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} sx={{ py: 0.5 }}>
                      <Typography sx={{ fontSize: 13, minWidth: 0, overflowWrap: "anywhere" }}>{row.title}</Typography>
                      <PillButton variant="text" disabled={pending} onClick={() => restoreHidden(row.card_key)}>
                        Restore
                      </PillButton>
                    </Stack>
                  )}
                />
              </Section>
            </FrostCard>
          ) : null}
        </Stack>
      </Box>
    </PageBody>
  );
}
