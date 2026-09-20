"use client";

import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";
import { BranchSync } from "@/app/branch-sync";
import { api, type CodebaseStatus, type Issue, type Prd, type PrototypeSession } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, EmptyState, FrostCard, ListRow, MarkdownBlock, PageBody, PageHeader, PagedList, PillButton, Section, StatusChip, TicketLink } from "@/app/ui";
import { apple } from "@/app/theme";

export default function PrdPage() {
  const [status, setStatus] = useState<CodebaseStatus | null>(null);
  const [prds, setPrds] = useState<Prd[]>([]);
  const [current, setCurrent] = useState<Prd | null>(null);
  const [title, setTitle] = useState("");
  const [problem, setProblem] = useState("");
  const [service, setService] = useState("");
  const [issueKey, setIssueKey] = useState("");
  const [tickets, setTickets] = useState<Issue[]>([]);
  const [tagged, setTagged] = useState<Issue[]>([]);
  const [prototypes, setPrototypes] = useState<PrototypeSession[]>([]);
  const [prototypeId, setPrototypeId] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const { tick } = useRefresh();

  async function load() {
    const [data, ac, proto] = await Promise.all([
      api.prds(),
      api.issues("AC").catch(() => ({ issues: [] as Issue[] })),
      api.prototypes().catch(() => ({ prototypes: [] as PrototypeSession[] })),
    ]);
    setStatus(data.codebase);
    setPrds(data.prds);
    setTickets(ac.issues || []);
    setPrototypes(proto.prototypes || []);
    if (!current && data.prds[0]) setCurrent(data.prds[0]);
  }

  useEffect(() => {
    load().catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  const services = useMemo(() => (status?.modules || []).map((row) => row.name).filter((name) => name !== "go_services"), [status]);
  const suggestions = useMemo(() => {
    const query = issueKey.trim().toLowerCase();
    if (query.length < 2) return [];
    const taggedKeys = new Set(tagged.map((row) => row.issue_key));
    return tickets
      .filter((row) => !taggedKeys.has(row.issue_key))
      .filter((row) => row.issue_key.toLowerCase().includes(query) || (row.summary || "").toLowerCase().includes(query))
      .slice(0, 8);
  }, [issueKey, tickets, tagged]);

  function addTicket(issue: Issue) {
    setTagged((current) => (current.some((row) => row.issue_key === issue.issue_key) ? current : [...current, issue]));
    setIssueKey("");
  }

  function addTypedTicket() {
    const match = issueKey.trim().toUpperCase().match(/\b([A-Z][A-Z0-9]+-\d+)\b/);
    if (!match) return;
    const existing = tickets.find((row) => row.issue_key === match[1]);
    addTicket(existing || { issue_key: match[1], summary: match[1], status: "", priority: "", assignee: "", creator: "", due_date: null, updated_at: null, url: "" });
  }

  async function generate(event: React.FormEvent) {
    event.preventDefault();
    if (!title.trim() && !problem.trim() && !tagged.length && !prototypeId) return;
    setBusy(true);
    setError("");
    try {
      const prd = await api.generatePrd({
        title: title.trim(),
        problem: problem.trim(),
        service: service.trim(),
        issue_key: tagged[0]?.issue_key || "",
        issue_keys: tagged.map((row) => row.issue_key),
        prototype_id: prototypeId || undefined,
      });
      setCurrent(prd);
      setPrds((existing) => [prd, ...existing.filter((row) => row.id !== prd.id)]);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function copyMarkdown() {
    if (!current?.markdown) return;
    await navigator.clipboard.writeText(current.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <PageBody>
      <PageHeader
        title="PRD"
        subtitle={status?.indexed_branch ? `${status.indexed_branch} @ ${status.indexed_sha || ""}` : "Needs a Codebase index"}
      />
      {error ? <Banner severity="error">{error}</Banner> : null}
      <BranchSync status={status} page="PRD" />

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3, alignItems: "start" }}>
        <FrostCard>
          <Section title="Generate a PRD">
            <Box component="form" onSubmit={generate}>
              <Stack spacing={2}>
                <TextField label="Title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Variables in agent training" size="small" fullWidth />
                <TextField
                  label="Problem / what to ship"
                  value={problem}
                  onChange={(event) => setProblem(event.target.value)}
                  placeholder="What should change, for whom, and why now."
                  multiline
                  minRows={3}
                  fullWidth
                />
                <TextField select label="Sense prototype (optional)" value={prototypeId || ""} onChange={(event) => setPrototypeId(Number(event.target.value) || 0)} size="small" fullWidth>
                  <MenuItem value="">None</MenuItem>
                  {prototypes.map((row) => (
                    <MenuItem key={row.id} value={row.id}>
                      {row.title || `Prototype ${row.id}`}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField select label="Service (optional)" value={service} onChange={(event) => setService(event.target.value)} size="small" fullWidth>
                  <MenuItem value="">Auto from title</MenuItem>
                  {services.map((name) => (
                    <MenuItem key={name} value={name}>
                      {name}
                    </MenuItem>
                  ))}
                </TextField>
                <div>
                  <Typography sx={{ fontSize: 13, color: apple.muted, mb: 0.75 }}>Tag tickets</Typography>
                  <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mb: 1 }}>
                    {tagged.map((row) => (
                      <Box key={row.issue_key} component="button" type="button" onClick={() => setTagged((current) => current.filter((item) => item.issue_key !== row.issue_key))} sx={{ border: 0, p: 0, bgcolor: "transparent", cursor: "pointer" }}>
                        <StatusChip label={`${row.issue_key} ×`} />
                      </Box>
                    ))}
                  </Stack>
                  <TextField
                    value={issueKey}
                    onChange={(event) => setIssueKey(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        if (suggestions[0]) addTicket(suggestions[0]);
                        else addTypedTicket();
                      }
                    }}
                    placeholder="Type AC-3280 or search a Sense ticket"
                    size="small"
                    fullWidth
                  />
                  {suggestions.length ? (
                    <Stack sx={{ mt: 0.75, border: `1px solid ${apple.hairline}`, borderRadius: "12px", overflow: "hidden" }}>
                      {suggestions.map((row) => (
                        <Box
                          key={row.issue_key}
                          component="button"
                          type="button"
                          onClick={() => addTicket(row)}
                          sx={{ display: "block", width: "100%", textAlign: "left", border: 0, bgcolor: apple.page, p: 1, cursor: "pointer", font: "inherit", fontSize: 13, "&:hover": { bgcolor: apple.wash } }}
                        >
                          {row.issue_key} · {row.summary}
                        </Box>
                      ))}
                    </Stack>
                  ) : null}
                </div>
                <PillButton type="submit" disabled={busy || (!status?.indexed && !prototypeId) || (!title.trim() && !problem.trim() && !tagged.length && !prototypeId)}>
                  {busy ? "Writing…" : "Generate PRD"}
                </PillButton>
              </Stack>
            </Box>
          </Section>
        </FrostCard>

        <Stack spacing={2}>
          <FrostCard>
            <Section title={current ? current.title : "Draft"}>
              {current ? (
                <>
                  <Typography sx={{ mb: 1, fontSize: 13, color: apple.muted }}>
                    {current.branch}@{current.commit_sha}
                    {current.issue_keys?.length ? ` · ${current.issue_keys.join(", ")}` : current.issue_key ? ` · ${current.issue_key}` : ""}
                    {current.llm_used ? " · grounded in code" : " · heuristic draft"}
                  </Typography>
                  <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 1.5 }}>
                    <PillButton variant="gray" type="button" onClick={copyMarkdown}>
                      {copied ? "Copied" : "Copy markdown"}
                    </PillButton>
                    <PillButton variant="gray" href={api.prdPdfUrl(current.id)} target="_blank" rel="noreferrer">
                      Export PDF
                    </PillButton>
                  </Stack>
                  <MarkdownBlock>{current.markdown}</MarkdownBlock>
                </>
              ) : (
                <EmptyState>Generate a PRD, or pick one from history after the first draft.</EmptyState>
              )}
            </Section>
          </FrostCard>
          <Section title="History" count={prds.length}>
            <PagedList
              items={prds}
              getKey={(prd) => prd.id}
              empty={<EmptyState>No PRDs saved yet.</EmptyState>}
              renderItem={(prd) => (
                <ListRow selected={current?.id === prd.id} onClick={() => setCurrent(prd)}>
                  <Typography sx={{ fontSize: 15 }}>{prd.title}</Typography>
                  <Typography sx={{ fontSize: 13, color: apple.muted }}>
                    {prd.issue_keys?.length
                      ? prd.issue_keys.map((key, index) => (
                          <span key={key}>
                            {index ? " · " : ""}
                            <TicketLink issueKey={key} />
                          </span>
                        ))
                      : prd.issue_key ? <TicketLink issueKey={prd.issue_key} /> : ""}
                  </Typography>
                </ListRow>
              )}
            />
          </Section>
        </Stack>
      </Box>
    </PageBody>
  );
}
