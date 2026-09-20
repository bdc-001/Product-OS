"use client";

import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";
import { BranchSync } from "@/app/branch-sync";
import { api, type CodebaseStatus, type FeatureArtifact } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, EmptyState, FrostCard, ListRow, PageBody, PageHeader, PagedList, PillButton, Section, StatusChip, SubSection } from "@/app/ui";
import { apple } from "@/app/theme";

export default function ArtifactsPage() {
  const [status, setStatus] = useState<CodebaseStatus | null>(null);
  const [rows, setRows] = useState<FeatureArtifact[]>([]);
  const [drive, setDrive] = useState(false);
  const [feature, setFeature] = useState("");
  const [notes, setNotes] = useState("");
  const [format, setFormat] = useState<"brief" | "deck">("brief");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState("");
  const [error, setError] = useState("");
  const [current, setCurrent] = useState<FeatureArtifact | null>(null);
  const { tick } = useRefresh();

  async function load() {
    const data = await api.artifacts();
    setStatus(data.codebase);
    setRows(data.artifacts || []);
    setDrive(Boolean(data.drive_configured));
    if (!current && data.artifacts?.[0]) setCurrent(data.artifacts[0]);
  }

  useEffect(() => {
    load().catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!feature.trim()) return;
    setBusy(true);
    setError("");
    setStep("Starting…");
    try {
      const result = await api.createArtifact(
        { feature: feature.trim(), notes: notes.trim(), format },
        (job) => {
          const label = (job.steps as Record<string, { status?: string }> | undefined)?.artifact?.status;
          setStep(label === "running" ? "Writing artifact…" : label === "done" ? "Uploading…" : job.status || "Working…");
        },
      );
      const created = (result.artifacts || [])[0] || null;
      if (created) {
        setCurrent(created);
        setRows((existing) => [created, ...existing.filter((row) => row.filename !== created.filename)]);
      }
      await load().catch(() => null);
      setFeature("");
      setNotes("");
      setStep("");
    } catch (err) {
      setError(String(err));
      setStep("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageBody>
      <PageHeader
        title="Artifacts"
        subtitle={
          status?.indexed_branch
            ? `${status.indexed_branch} · ${drive ? "Drive ready" : "Drive not configured (PDF stored locally)"}`
            : "Needs a Codebase product branch"
        }
      />
      {error ? <Banner severity="error">{error}</Banner> : null}
      <BranchSync status={status} page="Artifacts" />

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3, alignItems: "start" }}>
        <FrostCard>
          <Section title="Create artifact">
            <Typography sx={{ mb: 2, fontSize: 15, color: apple.muted }}>
              Enter the feature name. The pipeline writes a client PDF and uploads it to Drive when configured.
            </Typography>
            <Box component="form" onSubmit={create}>
              <Stack spacing={2}>
                <TextField
                  label="Feature name"
                  value={feature}
                  onChange={(event) => setFeature(event.target.value)}
                  placeholder="Billing Dashboard — All Tenants View"
                  size="small"
                  fullWidth
                  required
                />
                <TextField
                  label="Notes (optional)"
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="What shipped, who it’s for, anything the brief must include."
                  multiline
                  minRows={3}
                  fullWidth
                />
                <TextField select label="Format" value={format} onChange={(event) => setFormat(event.target.value as "brief" | "deck")} size="small" fullWidth>
                  <MenuItem value="brief">Brief (A4)</MenuItem>
                  <MenuItem value="deck">Deck (16:9)</MenuItem>
                </TextField>
                <PillButton type="submit" disabled={busy || !feature.trim() || !status?.indexed}>
                  {busy ? step || "Creating…" : "Create & upload"}
                </PillButton>
              </Stack>
            </Box>
          </Section>
        </FrostCard>

        <Stack spacing={2}>
          <FrostCard>
            <Section title={current ? current.feature : "Latest"}>
              {current ? (
                <>
                  <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mb: 1.5 }}>
                    {current.format ? <StatusChip label={current.format} /> : null}
                    {current.branch ? <StatusChip label={current.branch} /> : null}
                    {current.url ? <StatusChip label="On Drive" tone="ink" /> : <StatusChip label="Local PDF" />}
                  </Stack>
                  <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                    {current.filename ? (
                      <PillButton variant="gray" href={api.artifactPdfUrl(current.filename)} target="_blank" rel="noreferrer">
                        Open PDF
                      </PillButton>
                    ) : null}
                    {current.url ? (
                      <PillButton variant="text" href={current.url} target="_blank" rel="noreferrer">
                        Open in Drive
                      </PillButton>
                    ) : null}
                  </Stack>
                </>
              ) : (
                <EmptyState>Create an artifact, or pick one from history.</EmptyState>
              )}
            </Section>
          </FrostCard>
          <Section title="History" count={rows.length}>
            <SubSection title="Recent PDFs">
              <PagedList
                items={rows}
                getKey={(row, index) => row.filename || `${row.feature}-${index}`}
                empty={<EmptyState>No artifacts yet.</EmptyState>}
                renderItem={(row) => (
                  <ListRow selected={current?.filename === row.filename} onClick={() => setCurrent(row)}>
                    <Typography sx={{ fontSize: 15 }}>{row.feature}</Typography>
                    <Typography sx={{ fontSize: 13, color: apple.muted }}>
                      {[row.format, row.branch, row.url ? "Drive" : "local"].filter(Boolean).join(" · ")}
                    </Typography>
                  </ListRow>
                )}
              />
            </SubSection>
          </Section>
        </Stack>
      </Box>
    </PageBody>
  );
}
