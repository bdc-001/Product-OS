"use client";

import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import Link from "@mui/material/Link";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState } from "react";
import { BranchSync } from "@/app/branch-sync";
import { api, type CodebaseStatus, type CommsKind, type DriveStatus, type ReleaseFeature, type ReleaseJob, type ReleasePack } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, EmptyState, FrostCard, ListRow, MarkdownBlock, PageBody, PageHeader, PagedList, PillButton, Section } from "@/app/ui";
import { apple } from "@/app/theme";

const FORMATS: { id: Exclude<CommsKind, "pack">; label: string; audience: string }[] = [
  { id: "release_notes", label: "Release notes", audience: "Clients · Inter / Helvetica" },
  { id: "whatsapp", label: "WhatsApp", audience: "Internal · Cliq" },
  { id: "newsletter", label: "Newsletter", audience: "Customers" },
];

const IN_FLIGHT = new Set(["detected", "indexing", "extracting", "generated", "pdf_done", "doc_draft", "publishing"]);

function kindOf(pack: ReleasePack): CommsKind {
  if (pack.kind && pack.kind !== "pack") return pack.kind;
  const hasNews = Boolean((pack.newsletter || []).length || pack.newsletter_intro);
  const filled = [Boolean(pack.internal_update || pack.whatsapp), Boolean(pack.release_notes), hasNews].filter(Boolean).length;
  if (filled > 1) return "pack";
  if (pack.release_notes) return "release_notes";
  if (hasNews) return "newsletter";
  return "whatsapp";
}

function kindLabel(kind: CommsKind) {
  return FORMATS.find((row) => row.id === kind)?.label || "Release pack";
}

function copyText(pack: ReleasePack) {
  const kind = kindOf(pack);
  if (kind === "whatsapp") return pack.whatsapp || pack.internal_update || "";
  if (kind === "release_notes") return pack.release_notes || "";
  if (kind === "newsletter") return pack.newsletter_markdown || "";
  return [pack.whatsapp || pack.internal_update, pack.release_notes, pack.newsletter_markdown].filter(Boolean).join("\n\n");
}

function initialChecked(features: ReleaseFeature[]) {
  const next: Record<string, boolean> = {};
  for (const feature of features) {
    const confidence = (feature.confidence || "MEDIUM").toUpperCase();
    next[feature.name] = confidence === "HIGH" || confidence === "MEDIUM";
  }
  return next;
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
  const [checked, setChecked] = useState<Record<string, boolean>>(() => initialChecked(features));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [artifacts, setArtifacts] = useState(Boolean(job.create_artifacts));
  const awaiting = job.status === "pending_review" || job.status === "error:publishing";
  const failed = (job.status || "").startsWith("error:");
  const selected = features.filter((feature) => checked[feature.name]).map((feature) => feature.name);

  useEffect(() => {
    setChecked(initialChecked(job.features || []));
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
          <Typography sx={{ fontSize: 13, color: apple.muted }}>Features extracted from {job.branch}. Unchecked items stay visible and are not written into the draft.</Typography>
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
        <Typography sx={{ fontSize: 13, color: apple.muted }}>No customer-visible features extracted. Edit the list in the form below, or regenerate after checking chips.</Typography>
      ) : null}

      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mt: 1.5 }}>
        {job.drive_link && (job.status === "pending_review" || job.status === "error:publishing") ? (
          <PillButton href={job.drive_link} target="_blank" rel="noreferrer">
            Open draft in Google Docs
          </PillButton>
        ) : null}
        {job.pdf_path ? (
          <PillButton variant="gray" type="button" onClick={() => window.open(`/api/comms/release-jobs/${job.id}/pdf`, "_blank", "noopener,noreferrer")}>
            Preview PDF
          </PillButton>
        ) : null}
        {job.pack_id ? (
          <PillButton variant="gray" type="button" onClick={() => onViewPack(job.pack_id || 0)}>
            View draft markdown
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
        {job.status === "uploaded" && job.drive_link ? (
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
  const [current, setCurrent] = useState<ReleasePack | null>(null);
  const [kind, setKind] = useState<Exclude<CommsKind, "pack">>("release_notes");
  const [title, setTitle] = useState("");
  const [angle, setAngle] = useState("");
  const [artifacts, setArtifacts] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const { tick } = useRefresh();

  const pending = useMemo(
    () => jobs.filter((job) => job.status === "pending_review" || job.status === "error:publishing"),
    [jobs],
  );
  const stripJobs = useMemo(
    () => jobs.filter((job) => job.status !== "uploaded").slice(0, 8),
    [jobs],
  );

  async function load() {
    const data = await api.comms();
    setStatus(data.codebase);
    setPacks(data.packs);
    setJobs(data.release_jobs || []);
    setDrive(data.drive || null);
    if (!current && data.packs[0]) setCurrent(data.packs[0]);
  }

  useEffect(() => {
    load().catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  useEffect(() => {
    const active = jobs.some((job) => IN_FLIGHT.has(job.status) || (job.status || "").startsWith("error:indexing") || job.status === "extracting");
    if (!active) return;
    const timer = window.setInterval(() => {
      load().catch(() => null);
    }, 4000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs.map((job) => `${job.id}:${job.status}`).join("|")]);

  async function generate(event: React.FormEvent) {
    event.preventDefault();
    setBusy("write");
    setError("");
    try {
      const pack = await api.generateComms({ title: title.trim(), angle: angle.trim(), kind, artifacts: kind === "release_notes" && artifacts });
      setCurrent(pack);
      setPacks((existing) => [pack, ...existing.filter((row) => row.id !== pack.id)]);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  async function copy() {
    if (!current) return;
    await navigator.clipboard.writeText(copyText(current));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function downloadPdf() {
    if (!current) return;
    window.open(`/api/comms/${current.id}/pdf`, "_blank", "noopener,noreferrer");
  }

  async function viewPack(packId: number) {
    if (!packId) return;
    const existing = packs.find((row) => row.id === packId);
    if (existing) {
      setCurrent(existing);
      return;
    }
    try {
      const pack = await api.commsPack(packId);
      setCurrent(pack);
      setPacks((rows) => [pack, ...rows.filter((row) => row.id !== pack.id)]);
    } catch (err) {
      setError(String(err));
    }
  }

  const selected = FORMATS.find((row) => row.id === kind);
  const viewing = current ? kindOf(current) : kind;
  const needsFeatures = kind === "release_notes" && !angle.trim();
  const subtitle = [
    status?.indexed_at_label
      ? /^indexed\b/i.test(status.indexed_at_label)
        ? status.indexed_at_label
        : `Indexed ${status.indexed_at_label}`
      : "Needs a Codebase index",
    drive?.label || "Drive: not configured (approval stores locally)",
  ].join(" · ");

  return (
    <PageBody>
      <PageHeader title="Comms" subtitle={subtitle} />
      {error ? <Banner severity="error">{error}</Banner> : null}
      {pending.length ? (
        <Typography sx={{ mb: 1.5, fontSize: 15, color: apple.muted }}>
          {pending.length} release{pending.length === 1 ? "" : "s"} awaiting approval
        </Typography>
      ) : null}
      {stripJobs.map((job) => (
        <ReleaseApproval key={job.id} job={job} onChanged={load} onViewPack={viewPack} />
      ))}
      <BranchSync status={status} />

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3, alignItems: "start" }}>
        <Stack spacing={2}>
          <FrostCard>
            <Section title="Write from this ship">
              <Box component="form" onSubmit={generate}>
                <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" role="radiogroup" aria-label="Communication format" sx={{ mb: 2 }}>
                  {FORMATS.map((row) => {
                    const on = kind === row.id;
                    return (
                      <Box
                        key={row.id}
                        component="button"
                        type="button"
                        role="radio"
                        aria-checked={on}
                        onClick={() => setKind(row.id)}
                        sx={{
                          border: `1px solid ${on ? apple.ink : apple.hairline}`,
                          bgcolor: on ? apple.ink : apple.page,
                          color: on ? "#fff" : apple.text,
                          borderRadius: "16px",
                          px: 1.75,
                          py: 1,
                          cursor: "pointer",
                          fontFamily: "inherit",
                          textAlign: "left",
                          transition: `background-color 0.3s ${apple.smooth}, color 0.3s ${apple.smooth}, transform 0.38s ${apple.pop}`,
                          "&:active": { transform: "scale(0.985)" },
                        }}
                      >
                        <Typography component="b" sx={{ display: "block", fontSize: 14, fontWeight: 600, color: "inherit" }}>
                          {row.label}
                        </Typography>
                        <Typography component="span" sx={{ fontSize: 12, color: on ? "rgba(255,255,255,0.8)" : apple.muted }}>
                          {row.audience}
                        </Typography>
                      </Box>
                    );
                  })}
                </Stack>
                <Stack spacing={2}>
                  <TextField label="Feature title (optional)" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Billing Dashboard — All Tenants View" size="small" fullWidth />
                  <TextField
                    label={kind === "release_notes" ? "Features in short" : "Emphasis (optional)"}
                    value={angle}
                    onChange={(event) => setAngle(event.target.value)}
                    placeholder={
                      kind === "release_notes"
                        ? "All Tenants View KPI for leads\nTenant-wise usage charges table\nCampaign filter on connectivity"
                        : "Lead with the customer-facing change."
                    }
                    required={kind === "release_notes"}
                    multiline
                    minRows={4}
                    fullWidth
                  />
                  {kind === "release_notes" ? (
                    <FormControlLabel
                      control={<Checkbox checked={artifacts} onChange={(event) => setArtifacts(event.target.checked)} />}
                      label="Create artifact PDF (A4 brief) for each feature"
                    />
                  ) : null}
                  <PillButton type="submit" disabled={Boolean(busy) || !status?.indexed || needsFeatures}>
                    {busy === "write" ? "Writing…" : `Generate ${selected?.label || "draft"}`}
                  </PillButton>
                </Stack>
              </Box>
            </Section>
          </FrostCard>
          {packs.length ? (
            <Section title="History" count={packs.length}>
              <PagedList
                items={packs}
                getKey={(pack) => pack.id}
                renderItem={(pack) => (
                <ListRow selected={current?.id === pack.id} onClick={() => setCurrent(pack)}>
                    <Typography sx={{ fontSize: 15 }}>{pack.title}</Typography>
                    <Typography sx={{ fontSize: 13, color: apple.muted }}>
                      {kindLabel(kindOf(pack))} · {pack.branch}
                    </Typography>
                </ListRow>
                )}
              />
            </Section>
          ) : null}
        </Stack>

        <FrostCard>
          {current ? (
            <Section title={kindLabel(viewing)}>
              <Typography sx={{ mb: 1, fontSize: 13, color: apple.muted }}>
                {current.branch}@{current.commit_sha}
                {current.llm_used ? "" : " · draft from git until LLM is on"}
              </Typography>
              <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
                <PillButton variant="gray" type="button" onClick={copy}>
                  {copied ? "Copied" : "Copy"}
                </PillButton>
                <PillButton variant="gray" type="button" onClick={downloadPdf}>
                  Download PDF
                </PillButton>
              </Stack>
              {viewing === "newsletter" ? (
                <Stack spacing={1.5}>
                  {current.newsletter_intro ? <MarkdownBlock>{current.newsletter_intro}</MarkdownBlock> : null}
                  {(current.newsletter || []).map((item, index) => (
                    <FrostCard key={`${item.feature}-${index}`}>
                      <Typography sx={{ fontSize: 13, color: apple.muted }}>{item.feature}</Typography>
                      {item.headline ? <Typography sx={{ mt: 0.5 }}>{item.headline}</Typography> : null}
                      {item.body ? <Typography sx={{ mt: 0.5, fontSize: 15 }}>{item.body}</Typography> : null}
                      {item.cta ? <Typography sx={{ mt: 0.5, fontSize: 13, color: apple.ink }}>{item.cta}</Typography> : null}
                    </FrostCard>
                  ))}
                </Stack>
              ) : viewing === "pack" ? (
                <>
                  {current.internal_update || current.whatsapp ? <MarkdownBlock>{current.whatsapp || current.internal_update}</MarkdownBlock> : null}
                  {current.release_notes ? (
                    <Box sx={{ mt: 1.5 }}>
                      <MarkdownBlock>{current.release_notes}</MarkdownBlock>
                    </Box>
                  ) : null}
                </>
              ) : (
                <MarkdownBlock>{copyText(current)}</MarkdownBlock>
              )}
              {(current.artifacts || []).length ? (
                <Typography sx={{ mt: 1.5, fontSize: 13, color: apple.muted }}>
                  Feature artifacts:{" "}
                  {(current.artifacts || []).map((item, index) => (
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
            </Section>
          ) : (
            <Section title="Draft">
              <EmptyState>Index a branch, list the features in short, then generate.</EmptyState>
            </Section>
          )}
        </FrostCard>
      </Box>
    </PageBody>
  );
}
