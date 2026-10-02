"use client";

import { Collapse } from "@mui/material";
import { httpJson } from "@/lib/http";
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Stack from "@/app/ui/stack";
import { BranchSync } from "@/app/branch-sync";
import { api, type CodebaseStatus, type DriveStatus, type ReleaseFeature, type ReleaseJob, type ReleasePack } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, EmptyState, FrostCard, PageBody, PageHeader, PillButton, Segmented, StatusChip } from "@/app/ui";
import { apple, radius } from "@/app/ui/tokens";
import { CommsPad } from "./pad";
import {
  FORMATS,
  draftFromPack,
  emptyDraft,
  formatLabel,
  markdownFromBlocks,
  packBody,
  previewText,
  type CommsDraft,
  type CommsFormat,
} from "./model";

const IN_FLIGHT = new Set(["detected", "indexing", "extracting", "capturing", "writing", "generated", "pdf_done", "doc_draft", "publishing"]);

function kindOf(pack: ReleasePack): CommsFormat | "pack" {
  if (pack.kind === "whatsapp" || pack.kind === "release_notes" || pack.kind === "newsletter") return pack.kind;
  if (pack.kind && pack.kind !== "pack") return "release_notes";
  const hasNews = Boolean((pack.newsletter || []).length || pack.newsletter_intro);
  const filled = [Boolean(pack.internal_update || pack.whatsapp), Boolean(pack.release_notes), hasNews].filter(Boolean).length;
  if (filled > 1) return "pack";
  if (pack.release_notes) return "release_notes";
  if (hasNews) return "newsletter";
  return "whatsapp";
}

function initialChecked(features: ReleaseFeature[], saved?: string[]) {
  const next: Record<string, boolean> = {};
  for (const feature of features) {
    const confidence = (feature.confidence || "MEDIUM").toUpperCase();
    next[feature.name] = saved ? saved.includes(feature.name) : confidence === "HIGH" || confidence === "MEDIUM";
  }
  return next;
}

function DraftCard({
  selected,
  disabled,
  onClick,
  chips,
  title,
  preview,
}: {
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
  chips: ReactNode;
  title: string;
  preview: string;
}) {
  return (
    <Box
      component="button"
      type="button"
      disabled={disabled}
      onClick={onClick}
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: 0.6,
        width: "100%",
        textAlign: "left",
        appearance: "none",
        WebkitAppearance: "none",
        border: `1px solid ${selected ? apple.ink : apple.hairline}`,
        bgcolor: selected ? apple.selFill : apple.page,
        borderRadius: `${radius.lg}px`,
        px: 1.5,
        py: 1.25,
        mb: 1,
        cursor: disabled ? "not-allowed" : "pointer",
        font: "inherit",
        color: "inherit",
        boxSizing: "border-box",
        transition: `border-color 0.2s ${apple.smooth}, background-color 0.2s ${apple.smooth}`,
        "&:hover": { bgcolor: selected ? apple.selFill : apple.hoverFill },
        "&:disabled": { opacity: 0.55 },
      }}
    >
      <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>{chips}</Box>
      <Typography sx={{ fontSize: 14, fontWeight: 650, lineHeight: 1.35 }}>{title}</Typography>
      <Typography
        sx={{
          fontSize: 12,
          color: apple.muted,
          lineHeight: 1.45,
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        {preview}
      </Typography>
    </Box>
  );
}

function ReleaseNotes({ job }: { job: ReleaseJob }) {
  const notes = job.notes || [];
  if (job.status === "writing") {
    return (
      <Typography sx={{ mt: 1.5, fontSize: 13, color: apple.muted }}>
        Writing one release note per checked feature from its commits and source…
      </Typography>
    );
  }
  if (!notes.length) return null;
  const uploaded = job.status === "uploaded";
  return (
    <Box sx={{ mt: 1.5 }}>
      <Typography sx={{ fontSize: 13, fontWeight: 600 }}>
        {notes.length === 1 ? "Release note" : `${notes.length} release notes`}, one per feature
      </Typography>
      <Stack spacing={1} sx={{ mt: 1 }}>
        {notes.map((note) => (
          <Box
            key={note.feature}
            sx={{ border: `1px solid ${apple.hairline}`, borderRadius: `${radius.lg}px`, px: 1.5, py: 1.25, bgcolor: apple.page }}
          >
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1} useFlexGap flexWrap="wrap">
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography sx={{ fontSize: 14, fontWeight: 650 }}>{note.title || note.feature}</Typography>
                <Typography sx={{ fontSize: 12, color: apple.muted }}>
                  {[note.sections.join(" · ").replace(/📌\s*/g, ""), note.images ? `${note.images} images` : "no images"].filter(Boolean).join(" · ")}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                {note.url ? (
                  <PillButton variant={uploaded ? "gray" : undefined} href={note.url} target="_blank" rel="noreferrer">
                    {uploaded ? "Open in Drive" : "Open draft"}
                  </PillButton>
                ) : null}
                {note.pdf_url ? (
                  <PillButton variant="gray" type="button" onClick={() => window.open(note.pdf_url, "_blank", "noopener,noreferrer")}>
                    Preview PDF
                  </PillButton>
                ) : null}
              </Stack>
            </Stack>
            {note.dek ? <Typography sx={{ mt: 0.75, fontSize: 13, lineHeight: 1.45 }}>{note.dek}</Typography> : null}
            {note.status === "fallback" ? (
              <Typography sx={{ mt: 0.75, fontSize: 12, color: apple.muted }}>
                Written from the extraction only ({note.error || "writer unavailable"}). Regenerate before approving.
              </Typography>
            ) : null}
            {note.warnings.map((warning) => (
              <Typography key={warning} sx={{ mt: 0.5, fontSize: 12, color: apple.muted }}>
                Check the draft: {warning}
              </Typography>
            ))}
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

function ReleaseShots({ job, busy, onRecapture }: { job: ReleaseJob; busy: boolean; onRecapture: () => void }) {
  const shots = job.shots || [];
  const capturing = job.status === "capturing";
  if (!shots.length && !job.shots_reason && !capturing) return null;
  const good = shots.filter((shot) => shot.status === "ok" && shot.url);
  const failed = shots.filter((shot) => shot.status !== "ok");
  const version = encodeURIComponent(job.updated_at || "");
  return (
    <Box sx={{ mt: 1.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} useFlexGap flexWrap="wrap">
        <Typography sx={{ fontSize: 13, fontWeight: 600 }}>Screenshots rendered from the shipped frontend</Typography>
        <PillButton variant="gray" type="button" disabled={busy || capturing} onClick={onRecapture}>
          {capturing ? "Capturing…" : "Recapture screenshots"}
        </PillButton>
      </Stack>
      {capturing ? (
        <Typography sx={{ mt: 0.5, fontSize: 13, color: apple.muted }}>Rendering the changed product components with fixture data…</Typography>
      ) : !good.length && job.shots_reason ? (
        <Typography sx={{ mt: 0.5, fontSize: 13, color: apple.muted }}>{job.shots_reason}</Typography>
      ) : null}
      {good.length ? (
        <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 1.25, mt: 1 }}>
          {good.map((shot) => (
            <Box
              key={shot.id}
              component="figure"
              sx={{ m: 0, border: `1px solid ${apple.hairline}`, borderRadius: `${radius.lg}px`, overflow: "hidden", bgcolor: apple.page }}
            >
              <Box component="a" href={`${shot.url}?v=${version}`} target="_blank" rel="noreferrer" sx={{ display: "block" }}>
                <Box
                  component="img"
                  src={`${shot.url}?v=${version}`}
                  alt={shot.caption || shot.id}
                  loading="lazy"
                  sx={{ display: "block", width: "100%", height: 150, objectFit: "cover", objectPosition: "top left" }}
                />
              </Box>
              <Box component="figcaption" sx={{ px: 1.25, py: 1 }}>
                <Typography sx={{ fontSize: 13, lineHeight: 1.4 }}>{shot.caption || shot.id}</Typography>
                <Typography sx={{ fontSize: 12, color: apple.muted }}>
                  {[shot.feature, shot.section, shot.in_doc ? "in draft" : "not in draft", shot.repaired ? "repaired once" : ""].filter(Boolean).join(" · ")}
                </Typography>
              </Box>
            </Box>
          ))}
        </Box>
      ) : null}
      {failed.map((shot) => (
        <Typography key={shot.id} sx={{ mt: 0.75, fontSize: 12, color: apple.muted }} title={shot.module}>
          Left out {shot.caption || shot.id}: {shot.error || "did not render"}
        </Typography>
      ))}
    </Box>
  );
}

function ReleaseApproval({
  job,
  onChanged,
  onViewPack,
}: {
  job: ReleaseJob;
  onChanged: () => Promise<void>;
  onViewPack: (packId: number) => Promise<void>;
}) {
  const features = job.features || [];
  const [checked, setChecked] = useState<Record<string, boolean>>(() => initialChecked(features, job.extraction?.checked));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [artifacts, setArtifacts] = useState(Boolean(job.create_artifacts));
  const awaiting = job.status === "pending_review" || job.status === "error:publishing";
  const failed = (job.status || "").startsWith("error:");
  const selected = features.filter((feature) => checked[feature.name]).map((feature) => feature.name);
  const hasNotes = Boolean((job.notes || []).length);

  useEffect(() => {
    setChecked(initialChecked(job.features || [], job.extraction?.checked));
  }, [job.id, job.updated_at]);

  async function regen() {
    setBusy("regen");
    setError("");
    try {
      await api.regenerateReleaseJob(job.id, { checked: selected, artifacts });
      await onChanged();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  async function approve() {
    setBusy("approve");
    setError("");
    try {
      const result = await api.approveReleaseJob(job.id);
      if (result.drive_link) {
        await navigator.clipboard.writeText(result.drive_link);
        setCopied(true);
        setTimeout(() => setCopied(false), 2500);
      }
      await onChanged();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  async function recapture() {
    setBusy("shots");
    setError("");
    try {
      await api.recaptureReleaseShots(job.id, features.length ? selected : undefined);
      await onChanged();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  async function retry() {
    setBusy("retry");
    setError("");
    try {
      await api.retryReleaseJob(job.id);
      await onChanged();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  return (
    <Box className={`release-strip ${awaiting ? "awaiting" : failed ? "failed" : "progress"}`}>
      <Stack direction="row" justifyContent="space-between" spacing={1} useFlexGap flexWrap="wrap">
        <Typography sx={{ fontWeight: 600 }}>
          {awaiting
            ? "Release awaiting approval"
            : failed
              ? `Release failed at ${(job.status || "").replace("error:", "")}`
              : `Release ${job.status.replace("_", " ")}`}
        </Typography>
        <Typography sx={{ fontSize: 13, color: apple.muted }}>
          {job.branch}
          {job.merged_at_label ? ` · merged ${job.merged_at_label}` : ""}
          {job.doc_ready ? " · Google Doc ready" : job.pdf_path ? " · PDF ready" : ""}
        </Typography>
      </Stack>
      {job.error_detail ? (
        <Typography sx={{ mt: 1, fontSize: 13, color: apple.muted }} title={job.error_detail}>
          {job.error_detail}
        </Typography>
      ) : null}
      {error ? <Banner severity="error">{error}</Banner> : null}

      {features.length ? (
        <Box className="release-chips">
          <Typography sx={{ fontSize: 13, color: apple.muted }}>Features extracted from {job.branch}. Each checked feature gets its own release note; unchecked ones stay listed here.</Typography>
          {features.map((feature) => {
            const confidence = (feature.confidence || "MEDIUM").toUpperCase();
            const on = Boolean(checked[feature.name]);
            return (
              <Box key={feature.name} component="label" className={`release-chip ${on ? "on" : "off"}`}>
                <input
                  type="checkbox"
                  checked={on}
                  onChange={() => setChecked((current) => ({ ...current, [feature.name]: !current[feature.name] }))}
                />
                <span>
                  <b>{feature.name}</b>
                  {feature.what ? <em>{feature.what}</em> : null}
                  <small>
                    {confidence}
                    {confidence === "LOW" ? " · [unverified]" : ""}
                    {feature.modules?.[0] ? ` · ${feature.modules[0]}` : ""}
                  </small>
                  {feature.evidence ? <small>{feature.evidence}</small> : null}
                </span>
              </Box>
            );
          })}
          {(job.internal || []).length ? (
            <Typography sx={{ fontSize: 13, color: apple.muted }}>internal: {(job.internal || []).join("; ")}</Typography>
          ) : null}
          <FormControlLabel
            control={<Checkbox checked={artifacts} onChange={(event) => setArtifacts(event.target.checked)} />}
            label="Create artifact PDF (A4 brief) for each checked feature"
          />
          {(job.artifacts || []).length ? (
            <Typography sx={{ fontSize: 13, color: apple.muted }}>
              Artifacts:{" "}
              {(job.artifacts || []).map((item, index) => (
                <span key={item.file_id || item.doc_id || item.feature}>
                  {index ? " · " : ""}
                  {item.url ? (
                    <Link href={item.url} target="_blank" rel="noreferrer">
                      {item.feature}
                    </Link>
                  ) : (
                    item.feature
                  )}
                </span>
              ))}
            </Typography>
          ) : null}
        </Box>
      ) : awaiting ? (
        <Typography sx={{ fontSize: 13, color: apple.muted }}>No customer-visible features extracted. Open the draft and write, or regenerate after checking chips.</Typography>
      ) : null}

      <ReleaseNotes job={job} />
      <ReleaseShots job={job} busy={Boolean(busy)} onRecapture={recapture} />

      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 1.5 }}>
        {!hasNotes && job.drive_link && (job.status === "pending_review" || job.status === "error:publishing") ? (
          <PillButton href={job.drive_link} target="_blank" rel="noreferrer">
            Open draft in Google Docs
          </PillButton>
        ) : null}
        {!hasNotes && job.pdf_path ? (
          <PillButton variant="gray" type="button" onClick={() => window.open(`/api/comms/release-jobs/${job.id}/pdf`, "_blank", "noopener,noreferrer")}>
            Preview PDF
          </PillButton>
        ) : null}
        {job.pack_id ? (
          <PillButton variant="gray" type="button" onClick={() => onViewPack(job.pack_id || 0)}>
            Open in editor
          </PillButton>
        ) : null}
        {features.length ? (
          <PillButton variant="gray" type="button" disabled={Boolean(busy) || !selected.length} onClick={regen}>
            {busy === "regen" ? "Regenerating…" : "Regenerate with ☑"}
          </PillButton>
        ) : null}
        {job.status === "error:publishing" ? (
          <PillButton type="button" disabled={Boolean(busy)} onClick={approve}>
            {busy === "approve" ? "Retrying…" : "Retry publish"}
          </PillButton>
        ) : awaiting ? (
          <PillButton type="button" disabled={Boolean(busy)} onClick={approve}>
            {busy === "approve" ? "Publishing…" : copied ? "Published · link copied" : "Approve & Publish"}
          </PillButton>
        ) : failed ? (
          <PillButton type="button" disabled={Boolean(busy)} onClick={retry}>
            {busy === "retry" ? "Retrying…" : "Retry from failed stage"}
          </PillButton>
        ) : null}
        {!hasNotes && job.status === "uploaded" && job.drive_link ? (
          <PillButton variant="gray" href={job.drive_link} target="_blank" rel="noreferrer">
            Open in Drive
          </PillButton>
        ) : null}
      </Stack>
    </Box>
  );
}

export default function CommsPage() {
  const [status, setStatus] = useState<CodebaseStatus | null>(null);
  const [packs, setPacks] = useState<ReleasePack[]>([]);
  const [jobs, setJobs] = useState<ReleaseJob[]>([]);
  const [drive, setDrive] = useState<DriveStatus | null>(null);
  const [id, setId] = useState<number>();
  const [draft, setDraft] = useState<CommsDraft>(emptyDraft("release_notes"));
  const [filter, setFilter] = useState<"all" | CommsFormat>("all");
  const [q, setQ] = useState("");
  const [title, setTitle] = useState("");
  const [angle, setAngle] = useState("");
  const [artifacts, setArtifacts] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [statusLine, setStatusLine] = useState("");
  const [generateOpen, setGenerateOpen] = useState(false);
  const [focusedJob, setFocusedJob] = useState<number | null>(null);
  const { tick } = useRefresh();
  const saveGen = useRef(0);
  const draftRef = useRef(draft);
  const idRef = useRef(id);
  draftRef.current = draft;
  idRef.current = id;

  const pending = useMemo(
    () => jobs.filter((job) => job.status === "pending_review" || job.status === "error:publishing"),
    [jobs],
  );
  const stripJobs = useMemo(
    () => focusedJob ? jobs.filter(job => job.id === focusedJob) : jobs.filter((job) => job.status !== "uploaded").slice(0, 8),
    [jobs, focusedJob],
  );

  async function load() {
    const data = await api.comms();
    setStatus(data.codebase);
    setPacks(data.packs);
    const target = Number(new URLSearchParams(window.location.search).get("release_job"));
    const nextJobs = data.release_jobs || [];
    if (target > 0) {
      const linked = await httpJson<ReleaseJob>(`/api/comms/release-jobs/${target}`, { cache: "no-store" });
      setJobs([linked, ...nextJobs.filter(job => job.id !== target)]);
      setFocusedJob(target);
    } else setJobs(nextJobs);
    setDrive(data.drive || null);
    return data;
  }

  useEffect(() => {
    load().catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  useEffect(() => {
    const target = Number(new URLSearchParams(window.location.search).get("pack"));
    if (target > 0) void viewPack(target);
    // A release link opens its exact saved draft, including drafts outside the recent list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const active = jobs.some((job) => IN_FLIGHT.has(job.status) || (job.status || "").startsWith("error:indexing") || job.status === "extracting");
    if (!active) return;
    const timer = window.setInterval(() => {
      load().catch(() => null);
    }, 4000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.map((job) => `${job.id}:${job.status}`).join("|")]);

  function isBlank(note: CommsDraft) {
    return !note.title.trim() && note.blocks.every((item) => !item.text.trim());
  }

  function patch(next: Partial<CommsDraft>) {
    setDraft((current) => ({ ...current, ...next }));
    setDirty(true);
    setStatusLine("");
  }

  function select(pack?: ReleasePack) {
    if (dirty && !window.confirm("Discard unsaved changes to this draft?")) return;
    setDirty(false);
    setStatusLine("");
    setError("");
    if (!pack) {
      setId(undefined);
      setDraft(emptyDraft(filter === "all" ? "release_notes" : filter));
      return;
    }
    setId(pack.id);
    idRef.current = pack.id;
    const kind = kindOf(pack) === "pack" ? "release_notes" : kindOf(pack);
    if (packBody({ ...pack, kind })) setDraft(draftFromPack({ ...pack, kind }));
    api.commsPack(pack.id).then((full) => {
      if (idRef.current !== full.id) return;
      setDraft(draftFromPack({ ...full, kind: kindOf(full) === "pack" ? "release_notes" : kindOf(full) }));
    }).catch((err) => setError(String(err)));
  }

  async function save(current = draftRef.current, currentId = idRef.current) {
    if (isBlank(current)) return currentId;
    const body = markdownFromBlocks(current.blocks);
    const heading = current.title.trim() || "Untitled draft";
    setBusy("save");
    setError("");
    const gen = ++saveGen.current;
    try {
      const row = currentId
        ? await api.saveComms(currentId, { title: heading, body, kind: current.kind })
        : await api.createComms({ title: heading, body, kind: current.kind });
      if (gen !== saveGen.current) return row.id;
      setId(row.id);
      setDirty(false);
      setStatusLine("Saved");
      const data = await load();
      setPacks(data.packs);
      return row.id;
    } catch (err) {
      if (gen === saveGen.current) setError(String(err));
      return currentId;
    } finally {
      if (gen === saveGen.current) setBusy("");
    }
  }

  useEffect(() => {
    if (!dirty) return;
    if (isBlank(draft)) return;
    const timer = window.setTimeout(() => {
      void save();
    }, 900);
    return () => window.clearTimeout(timer);
  }, [draft, dirty]);

  async function generate(event: React.FormEvent) {
    event.preventDefault();
    setBusy("write");
    setError("");
    try {
      const pack = await api.generateComms({ title: title.trim(), angle: angle.trim(), kind: draft.kind, artifacts: draft.kind === "release_notes" && artifacts });
      setId(pack.id);
      setDraft(draftFromPack(pack));
      setDirty(false);
      setStatusLine("Generated");
      setPacks((existing) => [pack, ...existing.filter((row) => row.id !== pack.id)]);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  async function copy() {
    const text = [draft.title.trim(), markdownFromBlocks(draft.blocks)].filter(Boolean).join("\n\n");
    if (!text.trim()) return;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function exportPdf() {
    const packId = dirty ? await save() : id;
    if (!packId) return;
    window.open(`/api/comms/${packId}/pdf`, "_blank", "noopener,noreferrer");
  }

  async function viewPack(packId: number) {
    if (!packId) return;
    const existing = packs.find((row) => row.id === packId);
    if (existing) {
      select(existing);
      return;
    }
    try {
      const pack = await api.commsPack(packId);
      setPacks((rows) => [pack, ...rows.filter((row) => row.id !== pack.id)]);
      select(pack);
    } catch (err) {
      setError(String(err));
    }
  }

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return packs.filter((pack) => {
      const kind = kindOf(pack);
      if (filter !== "all" && kind !== filter && kind !== "pack") return false;
      if (!needle) return true;
      const hay = `${pack.title} ${pack.preview || ""} ${packBody(pack)} ${pack.branch || ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [packs, filter, q]);

  const locked = Boolean(busy) && busy !== "save";
  const needsFeatures = draft.kind === "release_notes" && !angle.trim();
  const paneSx = {
    p: 0,
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    minHeight: { md: "calc(100dvh - 196px)" },
    maxHeight: { md: "calc(100dvh - 196px)" },
    height: { md: "calc(100dvh - 196px)" },
    "&:hover": { borderColor: apple.hairline },
  } as const;
  const subtitle = [
    status?.indexed_at_label
      ? /^indexed\b/i.test(status.indexed_at_label)
        ? status.indexed_at_label
        : `Indexed ${status.indexed_at_label}`
      : "Needs a Codebase index to generate",
    drive?.label || "Drive: not configured (approval stores locally)",
  ].join(" · ");

  return (
    <PageBody wide>
      <PageHeader title="Comms" subtitle={subtitle} />
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}><Link href="/releases">Release history</Link>{focusedJob && <Link href="/comms">Show all drafts</Link>}</Stack>
      {error ? <Banner severity="error">{error}</Banner> : null}
      {pending.length ? (
        <Typography sx={{ mb: 1.5, fontSize: 15, color: apple.muted }}>
          {pending.length} release{pending.length === 1 ? "" : "s"} awaiting approval
        </Typography>
      ) : null}
      {stripJobs.map((job) => (
        <ReleaseApproval key={job.id} job={job} onChanged={async () => { await load(); }} onViewPack={viewPack} />
      ))}
      <BranchSync status={status} />

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "320px minmax(0,1fr)" },
          gap: 2,
          alignItems: "stretch",
        }}
      >
        <FrostCard sx={paneSx}>
          <Box sx={{ px: 2, pt: 2, pb: 1.5, borderBottom: `1px solid ${apple.hairline}` }}>
            <PillButton fullWidth onClick={() => select()} disabled={Boolean(busy)}>
              New draft
            </PillButton>
          </Box>
          <Box sx={{ px: 2, py: 1.5, borderBottom: `1px solid ${apple.hairline}`, display: "flex", flexDirection: "column", gap: 1.25 }}>
            <TextField size="small" fullWidth label="Search drafts" value={q} onChange={(event) => setQ(event.target.value)} />
            <TextField select size="small" fullWidth label="Show" value={filter} onChange={(event) => setFilter(event.target.value as typeof filter)}>
              <MenuItem value="all">All formats</MenuItem>
              {FORMATS.map((row) => (
                <MenuItem key={row.id} value={row.id}>
                  {row.label}
                </MenuItem>
              ))}
            </TextField>
            <PillButton variant="text" type="button" onClick={() => setGenerateOpen((value) => !value)} aria-expanded={generateOpen}>
              {generateOpen ? "Hide generate" : "Generate from indexed branch"}
            </PillButton>
            <Collapse in={generateOpen}>
              <Box component="form" onSubmit={generate}>
                <TextField
                  size="small"
                  fullWidth
                  label="Generate from this ship"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Feature title (optional)"
                  sx={{ mb: 1 }}
                />
                <TextField
                  size="small"
                  fullWidth
                  multiline
                  minRows={3}
                  label={draft.kind === "release_notes" ? "Features in short" : "Emphasis (optional)"}
                  value={angle}
                  onChange={(event) => setAngle(event.target.value)}
                  placeholder={draft.kind === "release_notes" ? "One line per shipped change" : "Lead with the customer-facing change."}
                  required={draft.kind === "release_notes"}
                  sx={{ mb: 1 }}
                />
                {draft.kind === "release_notes" ? (
                  <FormControlLabel
                    sx={{ mb: 1, ml: 0 }}
                    control={<Checkbox size="small" checked={artifacts} onChange={(event) => setArtifacts(event.target.checked)} />}
                    label="Create artifact PDFs"
                  />
                ) : null}
                <PillButton type="submit" fullWidth disabled={Boolean(busy) || !status?.indexed || needsFeatures}>
                  {busy === "write" ? "Writing…" : `Generate ${formatLabel(draft.kind)}`}
                </PillButton>
              </Box>
            </Collapse>
          </Box>
          <Box sx={{ flex: 1, minHeight: 0, overflow: "auto", px: 1.5, py: 1.5 }}>
            {visible.map((pack) => (
              <DraftCard
                key={pack.id}
                selected={id === pack.id}
                disabled={locked}
                onClick={() => select(pack)}
                chips={
                  <>
                    <StatusChip label={formatLabel(kindOf(pack) === "pack" ? "release_notes" : kindOf(pack))} />
                    {pack.llm_used ? <StatusChip label="AI" tone="ink" /> : null}
                  </>
                }
                title={pack.title || "Untitled"}
                preview={previewText(pack).slice(0, 120) || pack.branch || "Empty draft"}
              />
            ))}
            {!visible.length ? <EmptyState>{q || filter !== "all" ? "No drafts in this filter." : "New draft, or generate from the indexed branch."}</EmptyState> : null}
          </Box>
        </FrostCard>

        <FrostCard sx={paneSx}>
          <Box
            sx={{
              px: 2.5,
              py: 1.5,
              borderBottom: `1px solid ${apple.hairline}`,
              display: "flex",
              alignItems: "center",
              gap: 2,
              flexWrap: "wrap",
            }}
          >
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Segmented
                value={draft.kind}
                onChange={(next) => {
                  if (locked) return;
                  if (next === "release_notes" || next === "whatsapp" || next === "newsletter") patch({ kind: next });
                }}
                options={FORMATS.map((row) => ({ id: row.id, label: row.label }))}
              />
            </Box>
          </Box>
          <Box
            sx={{
              px: 2.5,
              py: 1.25,
              borderBottom: `1px solid ${apple.hairline}`,
              bgcolor: apple.hoverFill,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1.5,
              flexWrap: "wrap",
            }}
          >
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              <PillButton variant="gray" type="button" disabled={isBlank(draft)} onClick={() => void copy()}>
                {copied ? "Copied" : "Copy"}
              </PillButton>
              <PillButton variant="gray" type="button" disabled={isBlank(draft)} onClick={() => void exportPdf()}>
                Export PDF
              </PillButton>
            </Box>
            <Typography role="status" sx={{ fontSize: 12, color: apple.muted, ml: "auto" }}>
              {busy === "save" ? "Saving…" : busy === "write" ? "Writing…" : dirty ? "Editing" : statusLine || "Autosaves as you write"}
            </Typography>
          </Box>
          <Box sx={{ flex: 1, minHeight: 0, overflow: "auto", px: { xs: 2, md: 3 }, py: { xs: 2, md: 2.5 } }}>
            <Box sx={{ maxWidth: 900, mx: "auto" }}>
              <CommsPad draft={draft} busy={locked} onChange={patch} />
            </Box>
          </Box>
        </FrostCard>
      </Box>
    </PageBody>
  );
}
