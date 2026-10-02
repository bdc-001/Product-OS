"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import NextLink from "next/link";
import { Box, Button, Chip, Link, LinearProgress, MenuItem, Pagination, Tab, Tabs, TextField, Typography } from "@mui/material";
import { Banner, EmptyState, FrostCard, PageBody, PageHeader, Section, Stack } from "@/app/ui";
import { apple } from "@/app/theme";
import { useRefresh } from "@/app/refresh";
import { loadReleases, releaseState, type ReleaseView, type ReleaseWorkspace } from "@/lib/releases";

const labels: Record<string, string> = { approve: "Buyer-facing", skip: "Not selected", defer: "Needs evidence", unassessed: "Not assessed", draft: "Draft", published: "Published", approved_locally: "Approved · local only" };
function Association({ value }: { value: string }) {
  return value === "commit" ? null : <Typography variant="caption" color="text.secondary">{value === "branch" ? "Linked by branch · commit not recorded" : "Related feature content · release commit not recorded"}</Typography>;
}
function Detail({ release }: { release: ReleaseView }) {
  const [tab, setTab] = useState("shipped");
  return <FrostCard sx={{ p: { xs: 2, md: 3 }, minWidth: 0 }}>
    <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" alignItems="center">
      <Typography component="h2" sx={{ fontSize: 22, fontWeight: 600, overflowWrap: "anywhere", flex: 1 }}>{release.branch}</Typography>
      <Chip size="small" label={releaseState[release.state]} color={release.state === "needs_attention" ? "warning" : "default"} />
    </Stack>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{release.merge_verified ? "Merged into main" : "Saved release record · merge history not verified"} · {release.sha.slice(0, 12)}{release.merged_at ? ` · ${release.merged_at.slice(0, 10)}` : ""}</Typography>
    <Box sx={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 1, my: 3 }}>
      {[["Buyer-facing rows", release.counts.buyer_facing], ["Files available", release.counts.artifacts], ["Comms drafts", release.counts.drafts]].map(([label, count]) => <Box key={label} sx={{ p: 1.5, border: `1px solid ${apple.hairline}`, borderRadius: 2 }}><Typography sx={{ fontSize: 24, fontWeight: 600 }}>{count}</Typography><Typography sx={{ fontSize: 12, color: apple.muted }}>{label}</Typography></Box>)}
    </Box>
    <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" allowScrollButtonsMobile sx={{ mb: 3, borderBottom: `1px solid ${apple.hairline}` }} aria-label="Release details">
      <Tab value="shipped" label="What shipped" /><Tab value="buyers" label="Buyer-facing" /><Tab value="files" label="Artifacts" /><Tab value="comms" label="Comms" />
    </Tabs>
    {tab === "shipped" && <>
      {release.changes.length ? <Stack spacing={2}>{release.changes.map((change, i) => <Box key={i} sx={{ pb: 2, borderBottom: `1px solid ${apple.hairline}` }}>
        <Typography sx={{ fontWeight: 600 }}>{change.name}</Typography>
        {change.what && <Typography variant="body2" sx={{ mt: .5 }}>{change.what}</Typography>}
        <Stack direction="row" spacing={1} sx={{ mt: 1 }}>{change.internal && <Chip size="small" label="Internal" />}{change.confidence && <Chip size="small" label={`${change.confidence.toLowerCase()} confidence`} />}</Stack>
        {change.evidence && <Box component="details" sx={{ mt: 1, fontSize: 13, color: apple.muted }}><summary>Source evidence</summary><Typography variant="body2" sx={{ mt: 1, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{change.evidence}</Typography></Box>}
      </Box>)}</Stack> : <EmptyState>No release summary has been extracted yet. Marketing findings below cover only the changes it assessed.</EmptyState>}
      {!!release.assessments.length && <Box sx={{ mt: 3 }}><Section title="Marketing findings" count={release.assessments.length}><Stack spacing={2}>{release.assessments.map((item, i) => <Box key={i}><Stack direction="row" spacing={1} useFlexGap flexWrap="wrap"><Typography sx={{ fontWeight: 600 }}>{item.name}</Typography><Chip size="small" label={labels[item.verdict] || item.verdict} /></Stack><Typography variant="body2" sx={{ mt: .5 }}>{item.summary}</Typography>{item.rationale && <Typography variant="body2" color="text.secondary" sx={{ mt: .5 }}>{item.rationale}</Typography>}</Box>)}</Stack></Section></Box>}
      {!release.changes.length && !release.assessments.length && <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>This release is visible from its merge record. Discovery and drafting have not recorded findings for it.</Typography>}
    </>}
    {tab === "buyers" && <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">Rows linked by release evidence. Buyer-facing reflects the saved Marketing assessment; it does not approve publication.</Typography>
      {release.features.map(feature => <Box key={feature.id} sx={{ pb: 2, borderBottom: `1px solid ${apple.hairline}` }}>
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap"><Link component={NextLink} href={feature.url} sx={{ fontWeight: 600 }}>{feature.name}</Link><Chip size="small" label={feature.buyer_facing ? "Buyer-facing" : feature.status === "dismissed" ? "Dismissed" : labels[feature.verdict] || feature.verdict} /></Stack>
        <Typography variant="body2" sx={{ mt: 1 }}>{feature.summary}</Typography><Typography variant="caption" color="text.secondary">{feature.module}</Typography>
        {feature.rationale && <Typography variant="body2" color="text.secondary" sx={{ mt: .5 }}>{feature.rationale}</Typography>}
      </Box>)}
      {!release.features.length && <EmptyState>No mastersheet rows are linked to this release. This does not mean every change is internal.</EmptyState>}
      {!!release.campaigns.length && <Section title="Related campaigns"><Stack spacing={2}>{release.campaigns.map(c => <Box key={c.id}><Link component={NextLink} href={c.url}>{c.name} · Campaign {c.id}</Link><Typography variant="body2" color="text.secondary">{c.status}</Typography><Association value={c.association} />{c.error && <Typography variant="body2" color="error">{c.error}</Typography>}</Box>)}</Stack></Section>}
    </Stack>}
    {tab === "files" && <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">Existing files from release drafting, Marketing campaigns, and Artifacts.</Typography>
      {release.artifacts.map(a => <Box key={a.url} sx={{ pb: 2, borderBottom: `1px solid ${apple.hairline}`, overflowWrap: "anywhere" }}><Link href={a.url} target="_blank" rel="noreferrer">{a.name}</Link><Typography variant="caption" sx={{ display: "block" }} color="text.secondary">{a.source}</Typography><Association value={a.association} />{a.drive_url && a.drive_url !== a.url && <Link href={a.drive_url} target="_blank" rel="noreferrer" sx={{ display: "block", fontSize: 13, mt: .5 }}>Open in Drive</Link>}</Box>)}
      {!release.artifacts.length && <EmptyState>No accessible files are linked yet. Create content from its feature in Marketing.</EmptyState>}
    </Stack>}
    {tab === "comms" && <Stack spacing={2}>
      <Typography variant="body2" color="text.secondary">Edit and approve in Comms. Viewing a release never publishes or sends anything.</Typography>
      {release.jobs.map(job => <Box key={job.id} sx={{ p: 2, bgcolor: apple.hoverFill, borderRadius: 2 }}><Typography sx={{ fontWeight: 600 }}>Release draft · {job.status.replaceAll("_", " ").replace("error:", "Failed: ")}</Typography>{job.error && <Typography variant="body2" color="error" sx={{ mt: 1 }}>{job.error}</Typography>}<Link component={NextLink} href={job.url} sx={{ display: "inline-block", mt: 1 }}>{job.status === "pending_review" || job.status === "error:publishing" ? "Review in Comms" : "Open release workflow"}</Link></Box>)}
      {release.comms.map(draft => <Box key={draft.id} sx={{ pb: 2, borderBottom: `1px solid ${apple.hairline}` }}><Stack direction="row" spacing={1} useFlexGap flexWrap="wrap"><Link component={NextLink} href={draft.url} sx={{ fontWeight: 600 }}>{draft.title}</Link><Chip size="small" label={labels[draft.state] || draft.state} /></Stack><Typography variant="caption" color="text.secondary">{draft.kind.replaceAll("_", " ")}</Typography><Association value={draft.association} /></Box>)}
      {!release.comms.length && !release.jobs.length && <EmptyState>No Comms draft is linked to this release yet.</EmptyState>}
    </Stack>}
  </FrostCard>;
}

function Releases() {
  const [data, setData] = useState<ReleaseWorkspace | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [mobileDetail, setMobileDetail] = useState(false);
  const { tick } = useRefresh();
  const params = useSearchParams();
  const router = useRouter();
  const requested = params.get("release");
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    loadReleases().then(value => { if (active) setData(value); }).catch(err => { if (active) setError(String(err)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [tick, attempt]);
  useEffect(() => { if (requested) setMobileDetail(true); }, [requested]);
  const needle = query.trim().toLowerCase();
  const visible = (data?.releases || []).filter(r => (filter === "all" || r.state === filter) && `${r.branch} ${r.sha} ${r.features.map(f => f.name).join(" ")} ${r.changes.map(c => c.name).join(" ")}`.toLowerCase().includes(needle));
  const selected = requested ? data?.releases.find(r => r.id === requested) : visible[0];
  const pages = Math.max(1, Math.ceil(visible.length / 10));
  const currentPage = Math.min(page, pages);
  return <PageBody wide>
    <Stack direction="row" spacing={2} sx={{ mb: 2 }}><Link component={NextLink} href="/codebase">Codebase</Link><Typography variant="body2" color="text.secondary">Release history</Typography></Stack>
    <PageHeader title="Releases" subtitle="One thread from shipped code to buyer-facing content. Reviews and approvals stay in their existing workspaces." />
    {data?.warnings.map(w => <Banner key={w} severity="warning">{w}</Banner>)}
    {error && <Banner severity="error">{error} <Button onClick={() => setAttempt(n => n + 1)}>Retry</Button></Banner>}
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 2 }}>
      <TextField size="small" label="Find a release or feature" value={query} onChange={e => { setQuery(e.target.value); setPage(1); }} sx={{ flex: 1 }} />
      <TextField select size="small" label="Status" value={filter} onChange={e => { setFilter(e.target.value); setPage(1); }} sx={{ minWidth: 210 }}><MenuItem value="all">All releases</MenuItem>{Object.entries(releaseState).map(([id, label]) => <MenuItem key={id} value={id}>{label}</MenuItem>)}</TextField>
      <Button disabled={loading} onClick={() => setAttempt(n => n + 1)}>Refresh view</Button>
    </Stack>
    {loading && <LinearProgress aria-label="Loading releases" sx={{ mb: 2 }} />}
    {data && <>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{visible.length} releases · Local history covers the latest {data.history_limit} merge commits plus saved release jobs.</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "280px minmax(0,1fr)" }, gap: 2, alignItems: "start" }}>
        <Box sx={{ display: { xs: mobileDetail && selected ? "none" : "block", md: "block" } }}>
          <FrostCard sx={{ p: 1 }}><Box component="nav" aria-label="Release history">{visible.slice((currentPage - 1) * 10, currentPage * 10).map(r => <Button key={r.id} fullWidth aria-current={selected?.id === r.id ? "page" : undefined} onClick={() => { router.replace(`/releases?release=${encodeURIComponent(r.id)}`, { scroll: false }); setMobileDetail(true); }} sx={{ display: "block", textAlign: "left", p: 1.5, mb: .5, bgcolor: selected?.id === r.id ? apple.hoverFill : "transparent", color: apple.text }}>
            <Typography sx={{ fontWeight: 600, fontSize: 14 }}>{r.branch.replace("release/", "")}</Typography><Typography sx={{ fontSize: 12, color: apple.muted }}>{releaseState[r.state]} · {r.sha.slice(0, 7)}</Typography><Typography sx={{ fontSize: 12, mt: .5, color: apple.muted }}>{r.counts.buyer_facing} buyer-facing · {r.counts.artifacts} files</Typography>
          </Button>)}</Box>{!visible.length && <EmptyState>{query || filter !== "all" ? "No releases match these filters." : "No release records yet. Merged release/YYYY-MM-DD branches appear after the codebase is refreshed."}</EmptyState>}</FrostCard>
          {pages > 1 && <Pagination count={pages} page={currentPage} onChange={(_, n) => setPage(n)} size="small" siblingCount={0} sx={{ mt: 2 }} />}
          {(query || filter !== "all") && <Button onClick={() => { setQuery(""); setFilter("all"); setPage(1); }}>Clear filters</Button>}
        </Box>
        <Box sx={{ minWidth: 0, display: { xs: mobileDetail && selected ? "block" : "none", md: "block" } }}>
          {selected ? <><Button onClick={() => setMobileDetail(false)} sx={{ display: { md: "none" }, mb: 1 }}>Back to releases</Button><Detail key={selected.id} release={selected} /></> : requested ? <EmptyState>This release is not in the available history. Select another release.</EmptyState> : null}
        </Box>
      </Box>
      <Box component="details" sx={{ mt: 3, fontSize: 13, color: apple.muted }}><summary>Records without release evidence</summary><Typography variant="body2" sx={{ mt: 1 }}>{data.unlinked.features} Marketing rows · {data.unlinked.comms} Comms drafts · {data.unlinked.artifacts} artifact PDFs. These remain in their workspaces. Names alone are not used to attach them to a release.</Typography></Box>
    </>}
  </PageBody>;
}

export default function ReleasesPage() { return <Suspense fallback={<LinearProgress />}><Releases /></Suspense>; }
