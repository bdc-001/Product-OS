"use client";
import { useState } from "react";
import { Alert, Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Drawer, FormControlLabel, IconButton, Paper, Radio, RadioGroup, Typography } from "@mui/material";
import CloseRounded from "@mui/icons-material/CloseRounded";
import Stack from "@/app/ui/stack";
import { formatLabels, type ContentStatus, type MarketingFeature } from "@/lib/marketing";

export const running = ["queued", "planning", "generating", "rendering", "uploading"];
export const formatShort: Record<string, string> = {
  linkedin_post: "Post", linkedin_carousel: "Carousel", linkedin_portrait_video: "Portrait",
  youtube_short: "Short", youtube_landscape_video: "Video", article: "Article", feature_brief: "Brief",
  release_notes: "Notes", case_study: "Case",
};
const labels: Record<string, string> = { not_started: "Not started", not_selected: "Not selected by PMM", queued: "Queued", planning: "PMM planning", generating: "Writing & review", rendering: "Design & render", uploading: "Saving to Drive", completed: "Ready to review", failed: "Needs attention", needs_evidence: "Needs evidence", stale: "Previous brief" };
export function typeAvailable(state?: ContentStatus) {
  if (!state || state.stale) return true;
  if (running.includes(state.status) || state.status === "completed") return false;
  if (["needs_evidence", "not_selected"].includes(state.status) && state.campaign_id) return false;
  return true;
}
export function canCreate(feature: MarketingFeature) {
  if (feature.status === "dismissed" || ["skip", "defer"].includes(feature.decision?.verdict || "") || feature.description.trim().length < 20) return false;
  return Object.keys(formatLabels).some(key => typeAvailable(feature.content_status?.[key]));
}
function chipTone(status: string): { color: "success" | "warning" | "primary" | "default"; variant: "filled" | "outlined" } {
  if (status === "completed") return { color: "success", variant: "filled" };
  if (status === "failed" || status === "needs_evidence") return { color: "warning", variant: "outlined" };
  if (running.includes(status)) return { color: "primary", variant: "filled" };
  return { color: "default", variant: "outlined" };
}
export function ContentStrip({ feature, onOpen }: { feature: MarketingFeature; onOpen: () => void }) {
  return <Box onClick={e => { e.stopPropagation(); onOpen(); }} sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, cursor: "pointer" }} role="button" aria-label={`Content for ${feature.name}`}>
    {Object.entries(formatShort).map(([key, label]) => {
      const state = feature.content_status?.[key];
      const status = state?.stale ? "stale" : (state?.status || "not_started");
      const tone = chipTone(status);
      return <Chip key={key} size="small" {...tone} label={label} title={`${formatLabels[key]} · ${labels[status] || status}`} sx={{ height: 22, fontSize: 11, "& .MuiChip-label": { px: 0.8 } }} />;
    })}
  </Box>;
}
export function ContentBadge({ state }: { state?: ContentStatus }) {
  return <Chip size="small" variant="outlined" label={state?.stale ? "Previous brief" : labels[state?.status || "not_started"] || state?.status} color={state?.stale ? "default" : state?.status === "completed" ? "success" : state?.status === "failed" || state?.status === "needs_evidence" ? "warning" : running.includes(state?.status || "") ? "primary" : "default"} />;
}
export function ContentSummary({ feature }: { feature: MarketingFeature }) {
  const values = Object.values(feature.content_status || {});
  const ready = values.filter(s => s.status === "completed" && !s.stale).length;
  const active = values.filter(s => running.includes(s.status) && !s.stale).length;
  const attention = values.filter(s => ["failed", "needs_evidence"].includes(s.status) && !s.stale).length;
  return <Stack spacing={0.5}><Typography variant="body2" sx={{ fontWeight: 600 }}>{ready ? `${ready} ready to review` : "No content ready"}</Typography><Typography variant="caption" color={attention ? "warning.main" : "text.secondary"}>{[active ? `${active} in production` : "", attention ? `${attention} need attention` : ""].filter(Boolean).join(" · ") || "Choose any content type"}</Typography></Stack>;
}
export function FeatureContent({ feature, busy, configured, close, create, choose, editBrief, preview }: { feature: MarketingFeature; busy: boolean; configured: boolean; close: () => void; create: (ids: number[], formats?: string[]) => void; choose: () => void; editBrief: () => void; preview: (id: number) => void }) {
  const disabled = busy || !configured || !canCreate(feature);
  return <Drawer anchor="right" open onClose={close} slotProps={{ paper: { sx: { width: { xs: "100%", sm: 720 }, maxWidth: "100%" } } }}>
    <Box sx={{ p: 3, borderBottom: "1px solid", borderColor: "divider" }}><Stack direction="row" justifyContent="space-between" alignItems="center"><Typography variant="overline">FEATURE CONTENT · V{feature.revision}</Typography><IconButton aria-label="Close feature content" onClick={close}><CloseRounded /></IconButton></Stack><Typography variant="h5" sx={{ mt: 1 }}>{feature.name}</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{feature.summary || feature.description}</Typography><Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 2 }}><ContentSummary feature={feature}/><Stack direction="row" spacing={1}><Button onClick={editBrief}>Edit brief</Button><Button variant="contained" disabled={disabled} onClick={choose}>Create</Button></Stack></Stack></Box>
    <Stack spacing={1.5} sx={{ p: 3, overflowY: "auto" }}>
      {disabled && !busy && <Alert severity="info">{!configured ? "Configure the writing model to create content." : "Update this feature’s brief and evidence before starting production."}</Alert>}
      {Object.entries(formatLabels).map(([key, label]) => {
        const state = feature.content_status?.[key];
        const exists = state?.status === "completed" && !state.stale;
        const pending = running.includes(state?.status || "") && !state?.stale;
        const blocked = state?.status === "needs_evidence" || (state?.status === "not_selected" && Boolean(state.campaign_id));
        return <Paper key={key} variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}><Stack direction="row" justifyContent="space-between" spacing={1} alignItems="center"><Typography sx={{ fontWeight: 600 }}>{label}</Typography><ContentBadge state={state}/></Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{state?.error || (state?.status === "needs_evidence" || state?.status === "not_selected" ? state.reason : state?.stale ? `Created for brief v${state.revision}. Generate again for the current brief.` : exists ? `${state.assets.length} files · ${state.delivery === "uploaded" ? "Stored in Drive" : "Saved locally"}` : key === "case_study" ? "Requires evidence of actual customer use and outcomes." : "A feature-specific story, reviewed by the PMM and editor.")}</Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>{state?.campaign_id && <Button size="small" onClick={() => preview(state.campaign_id!)}>View {exists ? "content" : "run"}</Button>}{!exists && !pending && <Button size="small" disabled={disabled || blocked && !state?.stale} onClick={() => create([feature.id], [key])}>{state?.status === "failed" ? "Retry this type" : "Create this type"}</Button>}</Stack>
        </Paper>;
      })}
    </Stack>
  </Drawer>;
}

export function CreateContent({ features, initialFormats, busy, close, submit }: { features: MarketingFeature[]; initialFormats?: string[]; busy: boolean; close: () => void; submit: (formats?: string[]) => Promise<boolean> }) {
  const [mode, setMode] = useState("choose");
  const [selected, setSelected] = useState<string[]>(initialFormats || []);
  const unavailable = (key: string) => features.every(f => !typeAvailable(f.content_status?.[key]));
  const available = selected.filter(key => !unavailable(key));
  return <Dialog open onClose={() => !busy && close()} fullWidth maxWidth="sm"><DialogTitle>Create content<Typography variant="body2" color="text.secondary">{features.length === 1 ? features[0].name : `${features.length} selected features`}</Typography></DialogTitle><DialogContent dividers>
    <RadioGroup value={mode} onChange={e => setMode(e.target.value)}><FormControlLabel value="choose" control={<Radio/>} label="Choose content types"/><FormControlLabel value="pmm" control={<Radio/>} label="Let the Product Marketing Manager recommend"/></RadioGroup>
    {mode === "choose" ? <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, mt: 1 }}>{Object.entries(formatLabels).map(([key, label]) => <FormControlLabel key={key} sx={{ alignItems: "flex-start", my: 0.5 }} control={<Checkbox disabled={unavailable(key)} checked={available.includes(key)} onChange={() => setSelected(s => s.includes(key) ? s.filter(k => k !== key) : [...s, key])}/>} label={<Box sx={{ pt: 1 }}><Typography variant="body2">{label}</Typography>{unavailable(key) && <Typography variant="caption">Already assessed · view the run</Typography>}</Box>}/>)}</Box> : <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>The PMM selects the smallest useful set of formats based on this feature’s evidence and buyer use case.</Typography>}
    {available.includes("case_study") && mode === "choose" && <Alert severity="info" sx={{ mt: 2 }}>Case studies need documented customer results. If those are missing, this type will show Needs evidence.</Alert>}
    <Typography variant="caption" sx={{ display: "block", mt: 2 }}>Production runs in the background. Finished content is saved for review in the app and Drive.</Typography>
  </DialogContent><DialogActions><Button disabled={busy} onClick={close}>Cancel</Button><Button variant="contained" disabled={busy || mode === "choose" && !available.length} onClick={async () => { if (await submit(mode === "pmm" ? undefined : available)) close(); }}>{busy ? "Starting…" : mode === "pmm" ? "Ask PMM to plan" : `Create ${available.length} ${available.length === 1 ? "type" : "types"}`}</Button></DialogActions></Dialog>;
}
