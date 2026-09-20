"use client";

import { useEffect, useState } from "react";
import { Alert, Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Drawer, IconButton, InputAdornment, Paper, Skeleton, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, MenuItem, Tooltip, Typography } from "@mui/material";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import Stack from "@/app/ui/stack";
import { marketingApi, type Campaign, type FeatureInput, type MarketingFeature } from "@/lib/marketing";
import { VideoChips } from "./media";
import { canCreate, ContentStrip, CreateContent, FeatureContent } from "./content";
import { pmm } from "@/app/ui/tokens";

const activeStates = ["queued", "planning", "assessing", "generating", "rendering", "uploading"];
export const actionable = (f: MarketingFeature) => f.status !== "dismissed" && !["skip", "defer"].includes(f.decision?.verdict || "");
const fields: (keyof FeatureInput)[] = ["name", "module", "summary", "description", "hook", "audience", "benefit", "priority", "start_date", "end_date", "sheet_status", "script", "video", "notes", "status", "tag"];
const initial = (f: MarketingFeature): FeatureInput => Object.fromEntries([...fields.map(k => [k, f[k] || ""]), ["revision", f.revision]]) as FeatureInput;
const latestFor = (f: MarketingFeature, campaigns: Campaign[]) => campaigns.filter(c => c.feature_id === f.id && c.feature_revision === f.revision).sort((a, b) => b.id - a.id)[0];
function stage(f: MarketingFeature, c?: Campaign) {
  if (c && ["failed", "partial"].includes(c.status)) return { label: "Needs attention", color: pmm.amber, bg: pmm.amberFill };
  if (c && activeStates.includes(c.status)) return { label: "In production", color: pmm.blueDeep, bg: pmm.blueFill };
  if (f.decision?.verdict === "defer") return { label: "Needs evidence", color: pmm.amber, bg: pmm.amberFill };
  if (!actionable(f)) return { label: "Not selected", color: pmm.muted, bg: pmm.mutedFill };
  if (c?.status === "completed" || f.sheet_status === "Completed") return { label: "Completed", color: pmm.green, bg: pmm.greenFill };
  if (f.tag === "In pipeline" || f.sheet_status === "In Progress") return { label: "In progress", color: pmm.blueDeep, bg: pmm.blueFill };
  return { label: "Not started", color: pmm.muted, bg: pmm.mutedFill };
}
function Status({ row, campaign }: { row: MarketingFeature; campaign?: Campaign }) {
  const s = stage(row, campaign);
  return <Chip size="small" label={s.label} sx={{ bgcolor: s.bg, color: s.color, border: 0, fontWeight: 500, whiteSpace: "nowrap" }} />;
}
const clamp = { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" } as const;

function FeatureEditor({ row, current, campaign, close, saved, openCampaign }: {
  row: MarketingFeature; current: MarketingFeature; campaign?: Campaign; close: () => void; saved: () => Promise<void>; openCampaign: (id: number) => void;
}) {
  const [draft, setDraft] = useState(initial(row));
  const [baseline, setBaseline] = useState(initial(row));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [discard, setDiscard] = useState(false);
  const dirty = fields.some(k => draft[k] !== baseline[k]);
  const conflict = current.revision !== baseline.revision;
  useEffect(() => {
    if (!dirty) { setDraft(initial(current)); setBaseline(initial(current)); }
  }, [current.revision]); // Preserve drafts when background refresh returns newer evidence.
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  async function save() {
    setSaving(true); setError("");
    try {
      const result = await marketingApi.save(draft, row.id);
      setDraft(initial(result)); setBaseline(initial(result));
      await saved();
    } catch (e) { setError(String(e)); }
    finally { setSaving(false); }
  }
  function field(key: keyof FeatureInput, label: string, multiline = false, maxLength = 4000) {
    return <TextField key={key} label={label} value={draft[key] || ""} fullWidth multiline={multiline} minRows={multiline ? 3 : undefined}
      onChange={e => setDraft({ ...draft, [key]: e.target.value })} slotProps={{ htmlInput: { maxLength } }} />;
  }
  const requestClose = () => !saving && (dirty ? setDiscard(true) : close());
  return <>
    <Drawer anchor="right" open onClose={requestClose} slotProps={{ paper: { sx: { width: { xs: "100%", sm: 580 }, maxWidth: "100%", borderRadius: 0 } } }}>
      <Box sx={{ p: 3, borderBottom: "1px solid", borderColor: "divider" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="overline" color="text.secondary">FEATURE BRIEF · {row.id.toString().padStart(2, "0")}</Typography><IconButton aria-label="Close feature editor" onClick={requestClose}><CloseRoundedIcon /></IconButton></Stack>
        <Typography component="h2" sx={{ fontSize: 25, fontWeight: 600, lineHeight: 1.25, mt: 1 }}>{row.name}</Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}><Status row={current} campaign={campaign} /><Typography variant="caption" sx={{ alignSelf: "center" }}>Version {baseline.revision}</Typography></Stack>
      </Box>
      <Stack spacing={3} sx={{ p: 3, overflowY: "auto", flex: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        {conflict && <Alert severity="warning">This feature changed while you were editing. Your draft is preserved. Close and reopen to load the latest version before saving.</Alert>}
        {campaign && <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}><Typography variant="body2">Latest campaign: {campaign.status}</Typography>{campaign.error && <Typography variant="caption" color="error">{campaign.error}</Typography>}<Button size="small" onClick={() => openCampaign(campaign.id)} endIcon={<ArrowForwardRoundedIcon />}>Review campaign</Button></Paper>}
        <Box><Typography sx={{ fontWeight: 600, mb: 2 }}>Positioning & audience</Typography><Stack spacing={2.5}>
          {field("name", "Feature name", false, 180)}{field("module", "Module", false, 120)}{field("summary", "2-line description", true, 280)}{field("description", "Use case", true)}{field("audience", "Relevant industry", false, 500)}{field("hook", "Launch hook", true, 2000)}{field("benefit", "Customer benefit", true, 2000)}
        </Stack></Box>
        <Divider />
        <Box><Typography sx={{ fontWeight: 600, mb: 2 }}>Launch planning</Typography><Stack spacing={2.5}>
          <Stack direction="row" spacing={2}><TextField fullWidth label="Priority" select value={draft.priority} onChange={e => setDraft({ ...draft, priority: e.target.value })}>{[...new Set([draft.priority, "P1", "P2", "P3"])].map(p => <MenuItem key={p} value={p}>{p || "Unassigned"}</MenuItem>)}</TextField>
          <TextField fullWidth label="Sheet status" select value={draft.sheet_status} onChange={e => setDraft({ ...draft, sheet_status: e.target.value })}>{["Not started", "In Progress", "Completed"].map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}</TextField></Stack>
          <Stack direction="row" spacing={2}>{field("start_date", "Start date", false, 32)}{field("end_date", "Target date", false, 32)}</Stack>
          {field("script", "Script / link", true)}
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>Video files</Typography>
            <VideoChips value={draft.video} empty="Add file names or links below" />
          </Box>
          {field("video", "Video files or links", true)}{field("notes", "Notes & creative constraints", true)}
        </Stack></Box>
        <Divider />
        <Box><Typography sx={{ fontWeight: 600, mb: 1 }}>Evidence & assessment</Typography>
          {row.decision && <Typography variant="body2" sx={{ mb: 2 }}>{row.decision.rationale}</Typography>}
          {row.decision?.missing_evidence?.map(item => <Alert key={item} severity="info" sx={{ mb: 1 }}>{item}</Alert>)}
          {row.evidence.map((item, i) => <Box key={i} sx={{ mb: 2, p: 2, bgcolor: pmm.mutedFill, borderRadius: 2 }}><Typography variant="caption">{item.module} · {item.branch} · {item.sha.slice(0, 8)}</Typography><Typography variant="body2" sx={{ whiteSpace: "pre-wrap", mt: 1 }}>{item.quote}</Typography><Typography variant="caption" sx={{ overflowWrap: "anywhere" }}>{item.paths.join(" · ")}</Typography></Box>)}
          <Typography variant="caption">Source: {row.source}. Previous campaigns keep their original feature version.</Typography>
        </Box>
      </Stack>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2.5, borderTop: "1px solid", borderColor: "divider" }}><Typography variant="caption" role="status">{dirty ? "Unsaved changes" : "All changes saved"}</Typography><Button variant="contained" disabled={saving || !dirty || conflict || !draft.name.trim()} onClick={save}>{saving ? "Saving…" : "Save changes"}</Button></Stack>
    </Drawer>
    <Dialog open={discard} onClose={() => setDiscard(false)}><DialogTitle>Keep your edits?</DialogTitle><DialogContent>Your changes have not been saved.</DialogContent><DialogActions><Button onClick={() => setDiscard(false)}>Keep editing</Button><Button color="error" onClick={close}>Discard changes</Button></DialogActions></Dialog>
  </>;
}

export default function Mastersheet({ features, campaigns, loading, busy, configured, generate, saved, preview }: {
  features: MarketingFeature[]; campaigns: Campaign[]; loading: boolean; busy: boolean; configured: boolean;
  generate: (ids: number[], formats?: string[]) => Promise<boolean>; saved: () => Promise<void>; preview: (id: number) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("active");
  const [module, setModule] = useState("all");
  const [sort, setSort] = useState("priority");
  const [selected, setSelected] = useState<number[]>([]);
  const [editing, setEditing] = useState<MarketingFeature | null>(null);
  const [inventory, setInventory] = useState<number | null>(null);
  const [creating, setCreating] = useState<{ ids: number[]; formats?: string[] } | null>(null);
  const canStart = (f: MarketingFeature) => canCreate(f);
  const attention = (f: MarketingFeature) => stage(f, latestFor(f, campaigns)).label === "Needs attention"
    || Object.values(f.content_status || {}).some(s => !s.stale && ["failed", "needs_evidence"].includes(s.status));
  const counts = [
    { value: "active", label: "Active", count: features.filter(actionable).length },
    { value: "ready", label: "Ready", count: features.filter(canStart).length },
    { value: "attention", label: "Needs attention", count: features.filter(attention).length },
    { value: "completed", label: "Completed", count: features.filter(f => stage(f, latestFor(f, campaigns)).label === "Completed").length },
  ];
  const rows = features.filter(f => {
    if (module !== "all" && f.module !== module) return false;
    if (!`${f.name} ${f.module} ${f.summary} ${f.hook} ${f.audience} ${f.description}`.toLowerCase().includes(query.trim().toLowerCase())) return false;
    if (filter === "all") return true;
    if (filter === "active") return actionable(f);
    if (filter === "ready") return canStart(f);
    if (filter === "attention") return attention(f);
    if (filter === "completed") return stage(f, latestFor(f, campaigns)).label === "Completed";
    if (filter === "evidence") return f.decision?.verdict === "defer";
    return !actionable(f);
  }).sort((a, b) => sort === "name" ? a.name.localeCompare(b.name) : sort === "recent" ? b.updated_at.localeCompare(a.updated_at) : (a.priority || "P9").localeCompare(b.priority || "P9") || a.id - b.id);
  const eligible = rows.filter(canStart);
  const targets = features.filter(f => selected.includes(f.id) && canStart(f));
  const visibleSelected = eligible.filter(f => selected.includes(f.id));
  const inventoried = features.find(f => f.id === inventory) || null;
  const creatingRows = features.filter(f => creating?.ids.includes(f.id));
  function toggle(id: number) { setSelected(s => s.includes(id) ? s.filter(n => n !== id) : [...s, id]); }
  function selection(f: MarketingFeature) { return <Checkbox size="small" checked={targets.some(t => t.id === f.id)} disabled={!canStart(f) || busy} onChange={() => toggle(f.id)} slotProps={{ input: { "aria-label": `Select ${f.name}` } }} />; }
  function name(f: MarketingFeature) { return <Box sx={{ minWidth: 0 }}><Typography variant="caption" sx={{ display: "block", mb: 0.5 }}>{f.module || "Unassigned"}</Typography><Button onClick={() => setEditing(f)} sx={{ p: 0, minWidth: 0, justifyContent: "flex-start", textAlign: "left", fontSize: 14, fontWeight: 600, lineHeight: 1.4, whiteSpace: "normal", overflowWrap: "anywhere", "&:hover": { bgcolor: "transparent", color: pmm.blue } }}>{f.name}</Button></Box>; }
  function action(f: MarketingFeature, c?: Campaign) {
    return <Stack direction="row" spacing={0.5} justifyContent="flex-end">
      {c && <Button size="small" onClick={() => preview(c.id)}>Review</Button>}
      <Tooltip title={!configured ? "Writing model is not configured" : !canStart(f) ? "Open this feature to review its brief and remaining content types" : "Choose one content type or let the PMM recommend"}>
        <span><Button size="small" disabled={busy || !configured || !canStart(f)} onClick={() => setCreating({ ids: [f.id] })} startIcon={<PlayArrowRoundedIcon />}>Create</Button></span>
      </Tooltip>
    </Stack>;
  }
  return <>
    <Stack direction="row" flexWrap="wrap" spacing={1} sx={{ mb: 2, rowGap: 1 }}>
      {counts.map(c => <Chip key={c.value} clickable onClick={() => setFilter(c.value)} label={`${loading ? "—" : c.count} ${c.label}`} color={filter === c.value ? "primary" : "default"} variant={filter === c.value ? "filled" : "outlined"} sx={{ fontWeight: 500 }} />)}
    </Stack>
    <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider" }}>
        <TextField size="small" placeholder="Search features, audiences…" value={query} onChange={e => setQuery(e.target.value)} sx={{ flex: 1, minWidth: 160 }} slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }, htmlInput: { "aria-label": "Search features" } }} />
        <TextField select size="small" label="View" value={filter} onChange={e => setFilter(e.target.value)} sx={{ minWidth: 145 }}>{[["active", "Active features"], ["ready", "Ready to start"], ["attention", "Needs attention"], ["completed", "Completed"], ["evidence", "Needs evidence"], ["history", "Not selected"], ["all", "All features"]].map(([v, l]) => <MenuItem key={v} value={v}>{l}</MenuItem>)}</TextField>
        <TextField select size="small" label="Product area" value={module} onChange={e => setModule(e.target.value)} sx={{ minWidth: 145 }}><MenuItem value="all">All areas</MenuItem>{[...new Set(features.map(f => f.module).filter(Boolean))].sort().map(m => <MenuItem key={m} value={m}>{m}</MenuItem>)}</TextField>
        <TextField select size="small" label="Sort by" value={sort} onChange={e => setSort(e.target.value)} sx={{ minWidth: 130 }}><MenuItem value="priority">Priority</MenuItem><MenuItem value="name">Feature name</MenuItem><MenuItem value="recent">Recently updated</MenuItem></TextField>
      </Stack>
      {targets.length > 0 && <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }} sx={{ px: 2, py: 1.5, bgcolor: pmm.blueFill }}><Typography variant="body2" sx={{ flex: 1 }}>{targets.length} selected{targets.length > visibleSelected.length ? ` · ${targets.length - visibleSelected.length} outside this view` : ""}</Typography><Button size="small" onClick={() => setSelected([])}>Clear</Button><Button size="small" variant="contained" disabled={busy || !configured || targets.length > 50} onClick={() => setCreating({ ids: targets.map(f => f.id) })} startIcon={<PlayArrowRoundedIcon />}>{targets.length > 50 ? "Select up to 50 features" : `Create for ${targets.length} selected`}</Button></Stack>}
      {loading ? <Box sx={{ p: 3 }}>{[0, 1, 2, 3].map(n => <Skeleton key={n} height={76} />)}</Box> : rows.length === 0 ? <Box sx={{ textAlign: "center", py: 8, px: 3 }}><Typography sx={{ fontWeight: 600, mb: 1 }}>No features in this view</Typography><Typography variant="body2" color="text.secondary">Try another product area or clear your filters.</Typography><Button sx={{ mt: 2 }} onClick={() => { setQuery(""); setModule("all"); setFilter("all"); }}>Show all features</Button></Box> : <>
        <TableContainer sx={{ display: { xs: "none", md: "block" }, maxHeight: "70vh", overflowX: "auto", width: "100%" }}><Table stickyHeader size="small" aria-label="Feature list" sx={{ tableLayout: "fixed", width: "100%", "& td": { py: 1.4, verticalAlign: "top", borderColor: "#ebebeb" }, "& th": { whiteSpace: "nowrap", py: 1.2, bgcolor: "#fafafb", fontSize: 12, color: "text.secondary", fontWeight: 500 }, "& .MuiTableCell-paddingCheckbox": { width: 52, minWidth: 52, maxWidth: 52, boxSizing: "border-box" } }}>
          <colgroup>
            <col style={{ width: 52 }} />
            <col style={{ width: "16%" }} />
            <col style={{ width: "16%" }} />
            <col style={{ width: "16%" }} />
            <col style={{ width: "12%" }} />
            <col style={{ width: "28%" }} />
            <col style={{ width: 148 }} />
          </colgroup>
          <TableHead><TableRow><TableCell padding="checkbox"><Checkbox size="small" disabled={busy || !eligible.length} checked={!!eligible.length && visibleSelected.length === eligible.length} indeterminate={visibleSelected.length > 0 && visibleSelected.length < eligible.length} onChange={() => setSelected(s => visibleSelected.length === eligible.length ? s.filter(id => !eligible.some(f => f.id === id)) : [...new Set([...s, ...eligible.map(f => f.id)])])} slotProps={{ input: { "aria-label": "Select all eligible visible features" } }} /></TableCell><TableCell>Feature</TableCell><TableCell>Description</TableCell><TableCell>Use case</TableCell><TableCell>Industry</TableCell><TableCell>Content</TableCell><TableCell>Actions</TableCell></TableRow></TableHead>
          <TableBody>{rows.map(f => { const c = latestFor(f, campaigns); return <TableRow key={f.id} hover selected={targets.some(t => t.id === f.id)}><TableCell padding="checkbox">{selection(f)}</TableCell><TableCell>{name(f)}</TableCell><TableCell><Typography variant="body2" sx={{ ...clamp, fontSize: 13 }}>{f.summary || f.hook || "—"}</Typography></TableCell><TableCell><Typography variant="caption" sx={{ ...clamp, WebkitLineClamp: 3 }}>{f.description || "—"}</Typography></TableCell><TableCell><Typography variant="caption" sx={clamp}>{f.audience || "—"}</Typography></TableCell><TableCell sx={{ overflow: "hidden" }}><ContentStrip feature={f} onOpen={() => setInventory(f.id)} /></TableCell><TableCell>{action(f, c)}</TableCell></TableRow>; })}</TableBody>
        </Table></TableContainer>
        <Stack sx={{ display: { xs: "flex", md: "none" } }}>{rows.map(f => { const c = latestFor(f, campaigns); return <Box key={f.id} sx={{ p: 2.5, borderBottom: "1px solid", borderColor: "divider" }}><Stack direction="row" spacing={1} alignItems="flex-start">{selection(f)}<Box sx={{ flex: 1, minWidth: 0 }}>{name(f)}</Box></Stack><Typography variant="body2" sx={{ ...clamp, mt: 1.5 }}>{f.summary || f.hook || f.description}</Typography><Typography variant="caption" sx={{ display: "block", mt: 0.5 }}>{f.audience || "Industry to define"}</Typography><Box sx={{ mt: 1.25, mb: 1.5 }}><ContentStrip feature={f} onOpen={() => setInventory(f.id)} /></Box><Stack direction="row" justifyContent="space-between" alignItems="center"><Status row={f} campaign={c} />{action(f, c)}</Stack></Box>; })}</Stack>
      </>}
      <Typography variant="caption" sx={{ display: "block", px: 2.5, py: 1.5, borderTop: "1px solid", borderColor: "divider" }}>{rows.length} of {features.length} features · Same seller list as the Google Sheet. Refresh pulls, discovers released buyer features, and writes it back.</Typography>
    </Paper>
    {editing && <FeatureEditor key={editing.id} row={editing} current={features.find(f => f.id === editing.id) || editing} campaign={latestFor(editing, campaigns)} close={() => setEditing(null)} saved={saved} openCampaign={preview} />}
    {inventoried && <FeatureContent feature={inventoried} busy={busy} configured={configured} close={() => setInventory(null)} create={(ids, formats) => { void generate(ids, formats); }} choose={() => { setCreating({ ids: [inventoried.id] }); setInventory(null); }} editBrief={() => { setEditing(inventoried); setInventory(null); }} preview={preview} />}
    {creating && creatingRows.length > 0 && <CreateContent features={creatingRows} initialFormats={creating.formats} busy={busy} close={() => setCreating(null)} submit={async formats => generate(creating.ids, formats)} />}
  </>;
}
