"use client";

import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ErrorRoundedIcon from "@mui/icons-material/ErrorRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import RadioButtonUncheckedRoundedIcon from "@mui/icons-material/RadioButtonUncheckedRounded";
import Box from "@mui/material/Box";
import FormControlLabel from "@mui/material/FormControlLabel";
import Link from "@mui/material/Link";
import Switch from "@mui/material/Switch";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { useParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState, type ReactNode } from "react";
import { ScheduleEditor, SettingsEditor } from "@/app/settings/pipelines/pipeline-config";
import { RunDrawer, RunList, useRunParam } from "@/app/settings/pipelines/run-view";
import { usePlatform } from "@/app/platform-state";
import { Banner, EmptyState, LoadingBlock, PageBody, PillButton } from "@/app/ui";
import { PipelineIcon, STEP_LABELS, ToneChip, absoluteTime, pipelineTone, relativeTime, requirementHref, requirementLabel } from "@/app/ui/platform";
import { apple, categoryAccent, pmm } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { isActive, platform, type Pipeline, type Run } from "@/lib/platform";

type Detail = Pipeline & { runs: Run[] };

function Panel({ title, children, hint }: { title: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <Box component="section" sx={{ p: 2.25, borderRadius: "16px", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised, display: "grid", gap: 1.5, minWidth: 0 }}>
      <Box>
        <Typography component="h2" sx={{ fontSize: 14.5, fontWeight: 650 }}>
          {title}
        </Typography>
        {hint ? <Typography sx={{ fontSize: 12.5, color: apple.muted, mt: 0.25, lineHeight: 1.5 }}>{hint}</Typography> : null}
      </Box>
      {children}
    </Box>
  );
}

function Requirement({ id, state, optional }: { id: string; state: "ok" | "missing" | "error"; optional?: boolean }) {
  const icon =
    state === "ok" ? <CheckCircleRoundedIcon sx={{ fontSize: 18, color: pmm.green }} /> : state === "error" ? <ErrorRoundedIcon sx={{ fontSize: 18, color: apple.danger }} /> : <RadioButtonUncheckedRoundedIcon sx={{ fontSize: 18, color: optional ? apple.muted : pmm.amber }} />;
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.25 }}>
      {icon}
      <Typography sx={{ fontSize: 14, flex: 1, minWidth: 0 }}>
        {requirementLabel(id).replace(/^a /, "").replace(/^./, (c) => c.toUpperCase())}
        {optional ? <Box component="span" sx={{ color: apple.muted, fontSize: 12.5 }}> · optional</Box> : null}
      </Typography>
      {state === "ok" ? (
        <Typography sx={{ fontSize: 12.5, color: apple.muted }}>Connected</Typography>
      ) : (
        <Link component={NextLink} href={requirementHref(id)} sx={{ fontSize: 12.5, fontWeight: 600 }}>
          {state === "error" ? "Fix" : "Connect"}
        </Link>
      )}
    </Box>
  );
}

function PipelineDetail() {
  const params = useParams<{ id: string }>();
  const id = String(params?.id || "");
  const { can } = useWorkspace();
  const { runPipeline, reloadPipelines, byId, pipelines } = usePlatform();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [runId, setRunId] = useRunParam();
  const canEdit = can("admin");
  const timezone = pipelines?.timezone || "UTC";

  const load = useCallback(async () => {
    try {
      setDetail(await platform.pipeline(id));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const active = Boolean(detail?.runs.some((run) => isActive(run)));
  const shellRun = byId[id]?.last_run;
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => void load(), 4_000);
    return () => window.clearInterval(timer);
  }, [active, load]);
  useEffect(() => {
    if (shellRun && detail && shellRun.id !== detail.runs[0]?.id) void load();
  }, [shellRun, detail, load]);

  const saved = (next: Pipeline) => {
    setDetail((current) => (current ? { ...current, ...next } : current));
    void reloadPipelines();
  };

  if (error && !detail) {
    return (
      <PageBody>
        <Banner severity="error">{error}</Banner>
        <PillButton variant="gray" href="/settings/pipelines" startIcon={<ArrowBackRoundedIcon />}>
          All pipelines
        </PillButton>
      </PageBody>
    );
  }
  if (!detail) {
    return (
      <PageBody>
        <LoadingBlock rows={4} height={80} label="Loading pipeline" />
      </PageBody>
    );
  }

  const tone = pipelineTone(detail);
  const tint = categoryAccent(detail.category);
  const { missing, failing, optional_missing } = detail.readiness;
  const running = detail.status === "running" || detail.status === "queued";

  async function start() {
    setStarting(true);
    const run = await runPipeline(detail!.id);
    setStarting(false);
    if (run) {
      setRunId(run.id);
      void load();
    }
  }

  async function toggle(enabled: boolean) {
    setToggling(true);
    try {
      saved(await platform.updatePipeline(detail!.id, { enabled }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setToggling(false);
    }
  }

  return (
    <PageBody>
      <Link component={NextLink} href="/settings/pipelines" underline="none" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, fontSize: 13, color: apple.muted, mb: 2, "&:hover": { color: apple.text } }}>
        <ArrowBackRoundedIcon sx={{ fontSize: 16 }} /> Pipelines
      </Link>

      <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start", flexWrap: "wrap", mb: 3 }}>
        <PipelineIcon icon={detail.icon} category={detail.category} size={56} />
        <Box sx={{ minWidth: 0, flex: "1 1 360px" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
            <Typography component="h1" sx={{ fontSize: { xs: 24, md: 28 }, fontWeight: 650, letterSpacing: "-0.03em", lineHeight: 1.15 }}>
              {detail.name}
            </Typography>
            <ToneChip tone={tone} />
          </Box>
          <Typography sx={{ mt: 0.25, fontSize: 12.5, fontWeight: 600, color: tint.main }}>{detail.category_label}</Typography>
          <Typography sx={{ mt: 1, fontSize: 14.5, color: apple.muted, lineHeight: 1.55, maxWidth: 680 }}>{detail.description}</Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
          {detail.output ? (
            <PillButton variant="gray" href={detail.output} endIcon={<ArrowForwardRoundedIcon />}>
              {detail.runnable ? "Open output" : "Open"}
            </PillButton>
          ) : null}
          {detail.runnable ? (
            <PillButton startIcon={<PlayArrowRoundedIcon />} disabled={starting || running || Boolean(missing.length) || !detail.enabled} onClick={() => void start()}>
              {running ? "Running…" : starting ? "Starting…" : "Run now"}
            </PillButton>
          ) : null}
        </Box>
      </Box>

      {error ? <Banner severity="error">{error}</Banner> : null}
      {missing.length ? (
        <Banner severity="warning">
          Connect {missing.map(requirementLabel).join(" and ")} to {detail.runnable ? "run" : "use"} this pipeline.{" "}
          <Link component={NextLink} href={requirementHref(missing[0])} sx={{ fontWeight: 600 }}>
            Set up {requirementLabel(missing[0])}
          </Link>
        </Banner>
      ) : failing.length ? (
        <Banner severity="error">
          {failing.map(requirementLabel).join(", ")} failed its last check. Runs may fail until it is fixed.{" "}
          <Link component={NextLink} href={requirementHref(failing[0])} sx={{ fontWeight: 600 }}>
            Review connection
          </Link>
        </Banner>
      ) : null}
      {!detail.enabled ? <Banner severity="info">This pipeline is off. Its schedule is paused and its page is hidden from the sidebar.</Banner> : null}

      <Box sx={{ display: "grid", gap: 2.5, gridTemplateColumns: { xs: "1fr", lg: "minmax(0,1fr) 360px" }, alignItems: "start" }}>
        <Box sx={{ display: "grid", gap: 2.5, minWidth: 0 }}>
          {detail.chain.length ? (
            <Panel title="What it runs" hint="Each step runs in order. A step that fails is recorded and the rest still run.">
              <Box component="ol" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: 0.75 }}>
                {detail.chain.map((step, index) => {
                  const item = byId[step];
                  if (!item) return null;
                  return (
                    <Box component="li" key={step}>
                      <Box component={NextLink} href={`/settings/pipelines/${step}`} sx={{ display: "flex", alignItems: "center", gap: 1.25, p: 1, borderRadius: "12px", textDecoration: "none", color: "inherit", "&:hover": { bgcolor: apple.hoverFill } }}>
                        <Typography sx={{ width: 20, fontSize: 12, color: apple.muted, fontVariantNumeric: "tabular-nums", textAlign: "right" }}>{index + 1}</Typography>
                        <PipelineIcon icon={item.icon} category={item.category} size={30} />
                        <Typography sx={{ fontSize: 14, fontWeight: 600, flex: 1, minWidth: 0 }}>{item.name}</Typography>
                        <ToneChip tone={pipelineTone(item)} size="sm" />
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            </Panel>
          ) : null}

          {detail.runnable ? (
            <Panel title="Recent runs" hint={detail.last_run ? `Last run ${relativeTime(detail.last_run.created_at)} · ${absoluteTime(detail.last_run.created_at)}` : undefined}>
              {detail.runs.length ? <RunList runs={detail.runs} onOpen={setRunId} selected={runId} /> : <EmptyState>No runs yet. {missing.length ? "Connect what it needs first." : "Run it now to see steps and logs here."}</EmptyState>}
            </Panel>
          ) : (
            <Panel title="How it runs">
              <Typography sx={{ fontSize: 14, color: apple.muted, lineHeight: 1.6 }}>
                {detail.name} is interactive: you start each piece of work from its page, and it uses this workspace&apos;s connections as you go. There is nothing to schedule.
              </Typography>
              <Box>
                <PillButton href={detail.output} endIcon={<ArrowForwardRoundedIcon />} disabled={Boolean(missing.length) || !detail.enabled}>
                  Open {detail.name}
                </PillButton>
              </Box>
            </Panel>
          )}

          {detail.steps.length > 1 && !detail.chain.length ? (
            <Panel title="Steps">
              <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
                {detail.steps.map((step, index) => (
                  <Box key={step} sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, px: 1.1, py: 0.5, borderRadius: 999, border: `1px solid ${apple.hairline}`, fontSize: 12.5, fontWeight: 600 }}>
                    <Box component="span" sx={{ color: apple.muted, fontVariantNumeric: "tabular-nums" }}>{index + 1}</Box>
                    {STEP_LABELS[step] || step}
                  </Box>
                ))}
              </Box>
            </Panel>
          ) : null}
        </Box>

        <Box sx={{ display: "grid", gap: 2.5, minWidth: 0 }}>
          <Panel title="Connections" hint={detail.requires.length || detail.optional.length ? undefined : "This pipeline works without any connections."}>
            {detail.requires.length || detail.optional.length ? (
              <Box sx={{ display: "grid", gap: 1 }}>
                {detail.requires.map((req) => (
                  <Requirement key={req} id={req} state={missing.includes(req) ? "missing" : failing.includes(req) ? "error" : "ok"} />
                ))}
                {detail.optional.map((opt) => (
                  <Requirement key={opt} id={opt} optional state={optional_missing.includes(opt) ? "missing" : "ok"} />
                ))}
              </Box>
            ) : null}
          </Panel>

          {detail.runnable ? (
            <Panel title="Schedule" hint={canEdit ? undefined : "Only workspace admins can change schedules."}>
              <ScheduleEditor key={`${detail.schedule}:${detail.schedule_enabled}:${detail.enabled}`} pipeline={detail} timezone={timezone} canEdit={canEdit} onSaved={saved} />
            </Panel>
          ) : null}

          {detail.settings_schema.length ? (
            <Panel title="Settings" hint="Used by scheduled runs and by Run now.">
              <SettingsEditor key={JSON.stringify(detail.settings)} pipeline={detail} canEdit={canEdit} onSaved={saved} />
            </Panel>
          ) : null}

          {canEdit ? (
            <Panel title="Availability">
              <FormControlLabel
                control={<Switch checked={detail.enabled} disabled={toggling} onChange={(event) => void toggle(event.target.checked)} />}
                label={<Typography sx={{ fontSize: 14 }}>{detail.enabled ? "On for this workspace" : "Off for this workspace"}</Typography>}
                sx={{ m: 0, justifyContent: "space-between", flexDirection: "row-reverse" }}
              />
              <Typography sx={{ fontSize: 12.5, color: apple.muted, lineHeight: 1.5 }}>Turning a pipeline off hides its page from the sidebar and stops its own schedule. Existing output is kept.</Typography>
            </Panel>
          ) : null}
        </Box>
      </Box>

      <RunDrawer runId={runId} onClose={() => setRunId(null)} onOpenRun={setRunId} />
    </PageBody>
  );
}

export default function PipelineDetailPage() {
  return (
    <Suspense fallback={<PageBody><LoadingBlock rows={4} height={80} /></PageBody>}>
      <PipelineDetail />
    </Suspense>
  );
}
