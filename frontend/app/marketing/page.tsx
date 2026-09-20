"use client";

import { useCallback, useEffect, useState } from "react";
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import { Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, LinearProgress, Link, MenuItem, Paper, Tab, Tabs, TextField, Typography } from "@mui/material";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import MovieOutlinedIcon from "@mui/icons-material/MovieOutlined";
import Stack from "@/app/ui/stack";
import { PageBody, MarkdownBlock } from "@/app/ui";
import { useRefresh } from "@/app/refresh";
import { marketingApi, formatLabels, type Campaign, type FeatureInput, type MarketingWorkspace } from "@/lib/marketing";
import Mastersheet, { actionable } from "./mastersheet";
import { SceneList, VideoStage } from "./media";
import type { BackgroundJob } from "@/lib/api";

const empty: FeatureInput = {
  name: "", description: "", summary: "", audience: "", benefit: "", notes: "", status: "draft",
  module: "", priority: "P1", hook: "", start_date: "", end_date: "", sheet_status: "Not started",
  script: "", video: "", tag: "New",
};
const sheetStatuses = ["Not started", "In Progress", "Completed"] as const;
const priorities = ["P1", "P2", "P3"] as const;
const channels = ["linkedin", "youtube", "article", "document"] as const;
const channelLabels = { linkedin: "LinkedIn", youtube: "YouTube", article: "Article", document: "Documents" };
function LegacyCampaignPreview({ campaign, close }: { campaign: Campaign; close: () => void }) {
  const [tab, setTab] = useState("strategy");
  const [copyMessage, setCopyMessage] = useState("");
  const strategy = campaign.content.strategy;
  const copy = campaign.content[tab as typeof channels[number]];
  return <Dialog open onClose={close} maxWidth="lg" fullWidth><DialogTitle>{campaign.feature_snapshot.name}<Typography variant="body2" color="text.secondary">Campaign {campaign.id} · Feature version {campaign.feature_revision} · {campaign.status}</Typography></DialogTitle>
    <Tabs value={tab} onChange={(_, value) => { setTab(value); setCopyMessage(""); }} variant="scrollable" sx={{ px: 2 }}><Tab value="strategy" label="Strategy" />{channels.map(c => <Tab key={c} value={c} label={channelLabels[c]} />)}<Tab value="video" label="Video" /><Tab value="files" label="Files" /></Tabs>
    <DialogContent dividers sx={{ minHeight: 450 }}>
      {campaign.error && <Alert severity="warning" sx={{ mb: 2 }}>{campaign.error}</Alert>}
      {tab === "strategy" && (strategy ? <Stack spacing={3}><Typography variant="h5">{strategy.positioning}</Typography><Typography><strong>Buyer problem</strong><br />{strategy.buyer_pain}</Typography><Typography><strong>Why this feature</strong><br />{strategy.differentiation}</Typography><Box>{strategy.pillars?.map(p => <Chip key={p} label={p} sx={{ m: 0.5, maxWidth: "100%", height: "auto", "& .MuiChip-label": { whiteSpace: "normal", py: 1 } }} />)}</Box>{strategy.content_ideas?.map((idea, i) => <Paper key={i} variant="outlined" sx={{ p: 2 }}><Typography variant="overline">{idea.channel}</Typography><Typography sx={{ fontWeight: 600 }}>{idea.idea}</Typography><Typography color="text.secondary">{idea.angle}</Typography></Paper>)}<Typography><strong>Call to action:</strong> {strategy.cta}</Typography></Stack> : <Typography>Content has not been generated yet.</Typography>)}
      {channels.includes(tab as typeof channels[number]) && (copy ? <><Stack direction="row" justifyContent="space-between" spacing={2} sx={{ mb: 2 }}><Typography variant="h5">{copy.title}</Typography><Button onClick={async () => { try { await navigator.clipboard.writeText(copy.body); setCopyMessage("Copied"); } catch { setCopyMessage("Copy unavailable; download the file instead."); } }}>Copy</Button></Stack>{copyMessage && <Typography variant="caption">{copyMessage}</Typography>}<MarkdownBlock>{copy.body}</MarkdownBlock></> : <Typography>This content is not available yet.</Typography>)}
      {tab === "video" && <Stack spacing={2}>
        <VideoStage campaign={campaign} assets={campaign.assets} />
        <SceneList scenes={campaign.content.video?.scenes} />
      </Stack>}
      {tab === "files" && <Stack spacing={1}>{campaign.assets.map(asset => <Paper key={asset.filename} variant="outlined" sx={{ p: 2, display: "flex", gap: 2, alignItems: "center" }}><Typography sx={{ flex: 1 }}>{asset.filename}</Typography><Button href={marketingApi.file(campaign.id, asset.filename)} startIcon={<DownloadRoundedIcon />}>Download</Button>{asset.drive_url && <Button href={asset.drive_url} target="_blank" rel="noreferrer">Drive</Button>}</Paper>)}{!campaign.assets.length && <Typography>No files generated yet.</Typography>}</Stack>}
    </DialogContent><DialogActions>{campaign.drive_url && <Button href={campaign.drive_url} target="_blank" rel="noreferrer">Open Drive folder</Button>}<Button onClick={close}>Close</Button></DialogActions>
  </Dialog>;
}

function CampaignPreview({ campaign, close }: { campaign: Campaign; close: () => void }) {
  const [tab, setTab] = useState("decision");
  const [copied, setCopied] = useState("");
  if (!campaign.content.version) return <LegacyCampaignPreview campaign={campaign} close={close} />;
  const decision = campaign.content.decision;
  const assignments = decision?.assignments || [];
  const state = campaign.content.formats?.[tab];
  const assignment = assignments.find(a => a.format === tab);
  const assets = campaign.assets.filter(a => a.channel === tab);
  return <Dialog open onClose={close} maxWidth="lg" fullWidth>
    <DialogTitle>{campaign.feature_snapshot.name}<Typography variant="body2" color="text.secondary">Campaign {campaign.id} · {campaign.status} · {decision?.model || "PMM assessment pending"}</Typography></DialogTitle>
    <Tabs value={tab} onChange={(_, value) => { setTab(value); setCopied(""); }} variant="scrollable" scrollButtons="auto" sx={{ px: 2 }}>
      <Tab value="decision" label="PMM decision" />{assignments.map(a => <Tab key={a.format} value={a.format} label={formatLabels[a.format]} />)}<Tab value="files" label={`Files (${campaign.assets.length})`} />
    </Tabs>
    <DialogContent dividers sx={{ minHeight: 420 }}>
      {campaign.error && <Alert severity="warning" sx={{ mb: 2 }}>{campaign.error}</Alert>}
      {tab === "decision" && (decision ? <Stack spacing={3}>
        <Box><Chip label={decision.verdict === "approve" ? "Approved for production" : decision.verdict === "skip" ? "Not selected for marketing" : "More evidence needed"} color={decision.verdict === "approve" ? "success" : "default"} sx={{ mb: 2 }} /><Typography variant="h5">{decision.positioning}</Typography><Typography sx={{ mt: 1 }}>{decision.rationale}</Typography></Box>
        <Typography><strong>Buyer problem</strong><br />{decision.buyer_problem}</Typography><Typography><strong>Audience</strong><br />{decision.audience}</Typography>
        {decision.missing_evidence.length > 0 && <Alert severity="info">{decision.missing_evidence.join(" ")}</Alert>}
        {assignments.map(a => <Paper key={a.format} variant="outlined" sx={{ p: 2.5 }}><Stack direction="row" spacing={1} alignItems="center"><Typography sx={{ fontWeight: 600 }}>{formatLabels[a.format]}</Typography><Chip size="small" label={campaign.content.formats?.[a.format]?.status || "queued"} /></Stack><Typography sx={{ mt: 1 }}>{a.reason}</Typography><Typography color="text.secondary" sx={{ mt: 1 }}>Angle: {a.angle}</Typography><Typography color="text.secondary">Goal: {a.objective}</Typography></Paper>)}
        <Box><Typography sx={{ fontWeight: 600, mb: 1 }}>Why other formats were omitted</Typography>{Object.entries(decision.omitted_formats).map(([key, reason]) => <Typography key={key} variant="body2" sx={{ mb: 1 }}><strong>{formatLabels[key]}:</strong> {reason}</Typography>)}</Box>
        <Box><Typography sx={{ fontWeight: 600, mb: 1 }}>Supporting evidence</Typography>{decision.evidence_quotes.map((quote, i) => <Paper key={i} variant="outlined" sx={{ p: 2, mb: 1, bgcolor: "#f7f9fc" }}><Typography variant="body2" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{quote}</Typography></Paper>)}</Box>
      </Stack> : <Typography>The PMM will assess the evidence and choose the content formats before production starts.</Typography>)}
      {assignment && <Stack spacing={2}>
        <Box><Typography variant="h5">{state?.content?.title || assignment.angle}</Typography><Typography color="text.secondary" sx={{ mt: 1 }}>{assignment.reason}</Typography><Chip size="small" sx={{ mt: 1 }} label={state?.status || "Queued"} />{state?.content?.review?.passed && <Chip size="small" color="success" sx={{ mt: 1, ml: 1 }} label="Evidence and editorial checks passed" />}</Box>
        {state?.content?.review?.feature_specificity && <Typography variant="body2" color="text.secondary">{state.content.review.feature_specificity}</Typography>}
        {state?.error && <Alert severity="warning">{state.error}</Alert>}
        {assets.some(a => a.mime === "video/mp4") && <VideoStage campaign={campaign} assets={assets} />}
        {tab === "linkedin_carousel" && <Box role="region" aria-label={`${campaign.feature_snapshot.name} carousel slides. Scroll horizontally to see more.`} sx={{ display: "flex", gap: 2, overflowX: "auto", pb: 1 }}>{assets.filter(a => a.mime === "image/png").map((a, i) => <Box key={a.filename} component="img" alt={`${campaign.feature_snapshot.name} carousel slide ${i + 1}`} src={marketingApi.file(campaign.id, a.filename)} sx={{ width: 260, height: 325, borderRadius: 2, flex: "0 0 auto" }} />)}</Box>}
        {assets.some(a => a.mime === "application/pdf") && <Stack direction="row" spacing={1}>{assets.filter(a => a.mime === "application/pdf").map(a => <Button key={a.filename} variant="outlined" href={marketingApi.file(campaign.id, a.filename)} target="_blank">Open designed PDF</Button>)}</Stack>}
        {state?.content?.body && (assets.some(a => a.mime === "video/mp4") ? (
          <Accordion disableGutters elevation={0} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, "&:before": { display: "none" } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}><Typography variant="body2">Channel copy</Typography></AccordionSummary>
            <AccordionDetails>
              <Button sx={{ mb: 1.5 }} onClick={async () => { try { await navigator.clipboard.writeText(state.content!.body); setCopied("Copied"); } catch { setCopied("Download the copy from Files."); } }}>{copied || "Copy channel text"}</Button>
              <MarkdownBlock>{state.content.body}</MarkdownBlock>
            </AccordionDetails>
          </Accordion>
        ) : (
          <>
            <Button sx={{ alignSelf: "flex-start" }} onClick={async () => { try { await navigator.clipboard.writeText(state.content!.body); setCopied("Copied"); } catch { setCopied("Download the copy from Files."); } }}>{copied || "Copy channel text"}</Button>
            <MarkdownBlock>{state.content.body}</MarkdownBlock>
          </>
        ))}
        <SceneList scenes={state?.content?.scenes} />
        {!state?.content && <Typography color="text.secondary">This specialist will write and review the selected format, then render its files.</Typography>}
      </Stack>}
      {tab === "files" && <Stack spacing={1}>{campaign.assets.map(asset => <Paper key={asset.filename} variant="outlined" sx={{ p: 2, display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}><Typography sx={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>{asset.filename}</Typography><Button href={marketingApi.file(campaign.id, asset.filename)} startIcon={<DownloadRoundedIcon />}>Download</Button>{asset.drive_url && <Button href={asset.drive_url} target="_blank" rel="noreferrer">Drive</Button>}</Paper>)}{!campaign.assets.length && <Typography>No files generated yet.</Typography>}</Stack>}
    </DialogContent><DialogActions>{campaign.drive_url && <Button href={campaign.drive_url} target="_blank" rel="noreferrer">Open Drive folder</Button>}<Button onClick={close}>Close</Button></DialogActions>
  </Dialog>;
}

export default function MarketingPage() {
  const [data, setData] = useState<MarketingWorkspace | null>(() => marketingApi.peekWorkspace() ?? null);
  const [tab, setTab] = useState("sheet");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [add, setAdd] = useState(false);
  const [newRow, setNewRow] = useState<FeatureInput>({ ...empty });
  const [saving, setSaving] = useState(false);
  const [starting, setStarting] = useState(false);
  const [job, setJob] = useState<BackgroundJob | null>(null);
  const [preview, setPreview] = useState<number | null>(null);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const { tick } = useRefresh();
  const busy = starting || Boolean(job && ["queued", "running"].includes(job.status || ""));
  const load = useCallback(async () => {
    const next = await marketingApi.workspace(); setData(next);
    if (next.active_job) setJob(next.active_job);
  }, []);
  useEffect(() => { load().catch(err => setError(String(err))); }, [tick, load]);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => { load().catch(() => {}); }, 6000);
    return () => clearInterval(timer);
  }, [busy, load]);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status || "")) return;
    let stopped = false;
    const timer = setInterval(async () => {
      try {
        const next = await marketingApi.job(job.id);
        if (stopped) return;
        setJob(next);
        if (["completed", "failed"].includes(next.status || "")) {
          if (next.status === "failed") setError(next.error || "The run needs attention. Retry it from Campaigns.");
          else setNotice(next.kind === "marketing-discovery"
            ? "Feature list updated from released seller capabilities."
            : "Run finished. Review campaign results for completed assets or steps that need attention.");
          await load();
        }
      } catch (err) { if (!stopped) setError(String(err)); }
    }, 2500);
    return () => { stopped = true; clearInterval(timer); };
  }, [job?.id, job?.status, load]);
  useEffect(() => {
    if (preview == null) { setCampaign(null); return; }
    const listed = data?.campaigns.find(c => c.id === preview);
    const full = listed?.content && (listed.content.formats || listed.content.linkedin || listed.content.strategy);
    if (full && listed) { setCampaign(listed); return; }
    let cancelled = false;
    marketingApi.campaign(preview).then((row) => { if (!cancelled) setCampaign(row); }).catch((err) => { if (!cancelled) setError(String(err)); });
    return () => { cancelled = true; };
  }, [preview, data?.campaigns]);
  async function start(action: () => Promise<BackgroundJob>) {
    setStarting(true); setError(""); setNotice("");
    try { setJob(await action()); return true; } catch (err) { setError(String(err)); return false; } finally { setStarting(false); }
  }
  async function create() {
    setSaving(true); setError("");
    try {
      await marketingApi.save({
        ...newRow,
        summary: newRow.summary || newRow.hook,
        description: newRow.description || newRow.hook || newRow.summary || "",
        benefit: newRow.hook || newRow.benefit,
        tag: "New",
        sheet_status: newRow.sheet_status || "Not started",
      });
      setAdd(false); setNewRow({ ...empty }); await load();
    } catch (err) { setError(String(err)); } finally { setSaving(false); }
  }
  const features = data?.features || [];
  const latestStep = Object.entries(job?.steps || {}).filter(([, value]) => value.status === "running").at(-1);
  const discovering = job?.kind === "marketing-discovery";
  const sync = data?.last_sync;
  const syncWhen = sync?.finished_at || sync?.created_at;
  const syncStamp = syncWhen ? new Date(syncWhen.endsWith("Z") ? syncWhen : `${syncWhen}Z`).toLocaleString() : "";
  const syncLabel = !sync ? "No sheet sync yet"
    : ["queued", "running"].includes(sync.status || "") ? "Fetching released features…"
    : sync.status === "failed" ? `Last sync failed${syncStamp ? ` · ${syncStamp}` : ""}`
    : `Sheet synced${syncStamp ? ` · ${syncStamp}` : ""}`;
  return <PageBody>
    {error && <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>{error}</Alert>}
    {notice && <Alert severity="success" onClose={() => setNotice("")} sx={{ mb: 2 }}>{notice}</Alert>}
    <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1} sx={{ mb: 2 }} alignItems={{ md: "center" }}>
      <Stack direction="row" flexWrap="wrap" spacing={1} alignItems="center" sx={{ rowGap: 1, minWidth: 0 }}>
        <Chip size="small" variant="outlined" label={!data ? "Checking setup…" : data.video.ready ? "Renderer ready" : "Video setup needed"} />
        {data && <Chip size="small" variant="outlined" label={data.drive.configured ? "Drive" : "Local storage"} />}
        {data && <Chip size="small" variant="outlined" label={data.sheet?.configured ? "Google Sheet" : "Sheet not configured"} />}
        {data && <Chip size="small" variant="outlined" label={syncLabel} />}
      </Stack>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: "wrap", rowGap: 1, minWidth: 0 }}>
        {data?.sheet?.url && <Link href={data.sheet.url} target="_blank" rel="noreferrer" sx={{ fontSize: 12, display: "inline-flex", alignItems: "center", gap: 0.4, whiteSpace: "nowrap" }}>Feature sheet <OpenInNewRoundedIcon sx={{ fontSize: 13 }} /></Link>}
        {data?.drive.url && <Link href={data.drive.url} target="_blank" rel="noreferrer" sx={{ fontSize: 12, display: "inline-flex", alignItems: "center", gap: 0.4, whiteSpace: "nowrap" }}>Artifacts <OpenInNewRoundedIcon sx={{ fontSize: 13 }} /></Link>}
        <Button disabled={busy || !data?.model_configured} onClick={() => void start(() => marketingApi.discover())}>Fetch releases</Button>
        <Button href="/api/marketing/features.csv" startIcon={<DownloadRoundedIcon />}>Export</Button>
        <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setAdd(true)}>Add feature</Button>
      </Stack>
    </Stack>
    {data && !data.model_configured && <Alert severity="warning" sx={{ mb: 2 }}>The writing model is not configured. You can still edit the feature list.</Alert>}
    {busy && <Paper variant="outlined" sx={{ p: 2, mb: 2 }}><Stack direction="row" justifyContent="space-between"><Typography sx={{ fontWeight: 600 }}>{discovering ? "Fetching released seller features" : "Content pipeline is working"}</Typography><Typography variant="body2" color="text.secondary">{latestStep ? latestStep[0] : "Starting"}</Typography></Stack><LinearProgress sx={{ my: 1.5 }} /><Typography variant="body2" color="text.secondary">{discovering ? "New buyer-facing capabilities from the latest release merges are added to this list and the Google Sheet. Production stays manual." : "Generation continues in the background. Each content type updates when its stage finishes."}</Typography></Paper>}
    <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" scrollButtons="auto" sx={{ mb: 2, minHeight: 42 }}>
      <Tab value="sheet" label={`Features (${features.filter(actionable).length})`} />
      <Tab value="campaigns" label={`Campaigns (${data?.campaigns.length || 0})`} />
      <Tab value="pipeline" label="How this works" />
    </Tabs>
    <Box sx={{ display: tab === "sheet" ? "block" : "none" }}>
      <Mastersheet features={features} campaigns={data?.campaigns || []} loading={!data} busy={busy} configured={Boolean(data?.model_configured)} generate={(ids, formats) => start(() => marketingApi.generate(ids, formats))} saved={load} preview={setPreview} />
    </Box>
    {tab === "campaigns" && <Stack spacing={2}>{data?.campaigns.map(item => <Paper key={item.id} variant="outlined" sx={{ p: 3, borderRadius: 3 }}><Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={2}><Box><Stack direction="row" spacing={1} alignItems="center"><Typography sx={{ fontWeight: 600 }}>{item.feature_snapshot.name}</Typography><Chip size="small" label={item.status} color={item.status === "completed" ? "success" : item.error ? "warning" : "default"} /></Stack><Typography variant="caption" color="text.secondary">Campaign {item.id} · Feature version {item.feature_revision} · {new Date(item.created_at + "Z").toLocaleDateString()} · {item.assets.length} files</Typography>{item.error && <Typography color="error" variant="body2" sx={{ mt: 1 }}>{item.error}</Typography>}</Box><Stack direction="row" spacing={1} alignItems="center"><Button onClick={() => setPreview(item.id)}>Open campaign</Button>{["failed", "partial"].includes(item.status) && <Button disabled={busy} onClick={() => start(() => marketingApi.retry(item.id))}>Retry remaining steps</Button>}{item.drive_url && <Button href={item.drive_url} target="_blank" rel="noreferrer">Drive</Button>}</Stack></Stack></Paper>)}{!data?.campaigns.length && <Paper variant="outlined" sx={{ p: 5, textAlign: "center" }}><Typography variant="h6">No campaigns yet</Typography><Typography color="text.secondary">Create a content type from the feature list to start a campaign.</Typography></Paper>}</Stack>}
    {tab === "pipeline" && <Paper variant="outlined" sx={{ p: 4, borderRadius: 3 }}><MovieOutlinedIcon sx={{ fontSize: 40, color: "#1a62f2", mb: 2 }} /><Typography variant="h5" sx={{ mb: 1 }}>Seller feature list, manual content</Typography><Typography color="text.secondary" sx={{ mb: 3 }}>The list stays in sync with the Google Sheet. You choose a feature and a content type. The PMM writes, reviews and renders that type into Drive.</Typography><Stack spacing={2}>{[
      ["01 / Keep the feature list current", "This list is the same seller-facing sheet as Google. Global Refresh pulls the sheet, discovers newly released Sense capabilities from merged release branches, keeps buyer use cases (including small operator tools), hides engineering/internal work, and writes Module, Feature, Description, Use Case and Industry back. Fetch releases does the same discovery without a full platform refresh."],
      ["02 / See every content type", "Each feature shows carousel, artifact, video, release notes, case study and the other PMM formats. Open the content strip to review status or start one type."],
      ["03 / Start one type when you want it", "Create opens a picker so you can run a single format, several formats, or let the PMM recommend. Production never starts from Refresh."],
      ["04 / Review without publishing", "Finished files stay in the app and Drive. Nothing is posted to Comms, social channels or mail from this page."],
    ].map(([title, body]) => <Box key={title} sx={{ borderLeft: "3px solid #d1e1fd", pl: 3 }}><Typography sx={{ fontWeight: 600 }}>{title}</Typography><Typography color="text.secondary">{body}</Typography></Box>)}</Stack></Paper>}
    <Dialog open={add} onClose={() => !saving && setAdd(false)} maxWidth="sm" fullWidth>
      <DialogTitle>Add feature to mastersheet</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5} sx={{ mt: 1 }}>
          {([
            ["module", "Module"], ["name", "Feature"], ["summary", "2-line description"], ["description", "Use case"],
            ["audience", "Relevant industry"], ["priority", "Priority"], ["hook", "Hook"], ["start_date", "Start date"],
            ["end_date", "End date"], ["script", "Script"], ["video", "Video"], ["notes", "Notes"],
          ] as const).map(([key, label]) => (
            key === "priority" ? (
              <TextField key={key} label={label} select value={newRow.priority} onChange={e => setNewRow({ ...newRow, priority: e.target.value })}>
                {priorities.map(value => <MenuItem key={value} value={value}>{value}</MenuItem>)}
              </TextField>
            ) : (
              <TextField key={key} label={label} required={key === "name" || key === "description" || key === "summary"} value={newRow[key]} onChange={e => setNewRow({ ...newRow, [key]: e.target.value })} multiline={["summary", "hook", "description", "script", "video", "notes"].includes(key)} minRows={key === "description" ? 3 : 1} />
            )
          ))}
          <TextField label="Sheet status" select value={newRow.sheet_status} onChange={e => setNewRow({ ...newRow, sheet_status: e.target.value })}>
            {sheetStatuses.map(value => <MenuItem key={value} value={value}>{value}</MenuItem>)}
          </TextField>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button disabled={saving} onClick={() => setAdd(false)}>Cancel</Button>
        <Button variant="contained" disabled={saving || !newRow.name.trim() || !(newRow.description.trim() || (newRow.summary || "").trim() || newRow.hook.trim())} onClick={create}>{saving ? "Saving…" : "Add with New tag"}</Button>
      </DialogActions>
    </Dialog>
    {campaign && <CampaignPreview campaign={campaign} close={() => setPreview(null)} />}
  </PageBody>;
}
