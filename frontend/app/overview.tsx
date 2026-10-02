"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import RadioButtonUncheckedRoundedIcon from "@mui/icons-material/RadioButtonUncheckedRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import Link from "@mui/material/Link";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useCommandPalette } from "@/app/command-palette";
import { usePlatform } from "@/app/platform-state";
import { useRefresh } from "@/app/refresh";
import { EmptyState, LoadingBlock, PageBody, PillButton } from "@/app/ui";
import { PipelineIcon, ToneChip, StatTile, formatDuration, pipelineTone, relativeTime, runTone, parseUtc, requirementHref, requirementLabel } from "@/app/ui/platform";
import { accent, apple, categoryAccent, pmm, type Category } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { platform, type ConnectionsResponse, type Pipeline, type Run, type WorkspaceDetail } from "@/lib/platform";

const STEP_LINKS: Record<string, { href: string; body: string }> = {
  profile: { href: "/settings/profile", body: "Name your product and describe who it is for. Every prompt reads this." },
  connections: { href: "/settings/connections", body: "Add Jira and an AI model at minimum. Everything is encrypted per workspace." },
  repository: { href: "/settings/repositories", body: "Point at a Git remote so releases, codebase Q&A and discovery have code to read." },
  people: { href: "/settings/people", body: "List your PMs, developers and QA so briefings resolve names correctly." },
};

function greeting() {
  const hour = new Date().getHours();
  if (hour < 5) return "Working late";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function Onboarding({ detail, onDismiss, canEdit }: { detail: WorkspaceDetail; onDismiss: () => void; canEdit: boolean }) {
  const steps = detail.onboarding.steps;
  const done = steps.filter((step) => step.done).length;
  const next = steps.find((step) => !step.done);
  return (
    <Box
      sx={{
        position: "relative",
        p: { xs: 2.5, md: 3 },
        mb: 3,
        borderRadius: "18px",
        border: `1px solid ${apple.hairline}`,
        overflow: "hidden",
        background: `radial-gradient(120% 140% at 0% 0%, ${accent.system.fill} 0%, transparent 55%), radial-gradient(100% 120% at 100% 100%, ${accent.knowledge.fill} 0%, transparent 60%), ${apple.raised}`,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: accent.system.main }}>Set up · {done} of {steps.length}</Typography>
          <Typography sx={{ mt: 0.5, fontSize: 20, fontWeight: 650, letterSpacing: "-0.02em" }}>Finish setting up {detail.name}</Typography>
          <Typography sx={{ mt: 0.5, fontSize: 14, color: apple.muted, maxWidth: 560 }}>Pipelines unlock as their connections land. You can come back to any step later.</Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1 }}>
          {canEdit ? (
            <PillButton variant="text" onClick={onDismiss} sx={{ color: apple.muted }}>
              Hide
            </PillButton>
          ) : null}
          <PillButton href={next ? "/onboarding" : "/settings/pipelines"} endIcon={<ArrowForwardRoundedIcon />}>
            {next ? "Continue setup" : "Explore pipelines"}
          </PillButton>
        </Box>
      </Box>
      <LinearProgress variant="determinate" value={(done / Math.max(1, steps.length)) * 100} aria-label="Setup progress" sx={{ mt: 2.5, height: 6, borderRadius: 3, bgcolor: apple.hoverFill, "& .MuiLinearProgress-bar": { borderRadius: 3, bgcolor: accent.system.main } }} />
      <Box sx={{ mt: 2.5, display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", lg: "repeat(4, 1fr)" } }}>
        {steps.map((step) => (
          <ButtonBase
            key={step.id}
            component={NextLink}
            href={STEP_LINKS[step.id]?.href || "/onboarding"}
            sx={{
              display: "block",
              textAlign: "left",
              p: 1.75,
              borderRadius: "12px",
              border: `1px solid ${step.done ? "transparent" : apple.hairline}`,
              bgcolor: step.done ? apple.hoverFill : apple.raised,
              transition: `border-color 0.2s ${apple.smooth}, transform 0.3s ${apple.pop}`,
              "&:hover": { borderColor: apple.hairlineHover, transform: "translateY(-1px)" },
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              {step.done ? <CheckCircleRoundedIcon sx={{ fontSize: 18, color: pmm.green }} /> : <RadioButtonUncheckedRoundedIcon sx={{ fontSize: 18, color: apple.muted }} />}
              <Typography sx={{ fontSize: 14, fontWeight: 600, textDecoration: step.done ? "line-through" : "none", color: step.done ? apple.muted : apple.text }}>{step.label}</Typography>
            </Box>
            {!step.done ? <Typography sx={{ mt: 0.75, fontSize: 12.5, color: apple.muted, lineHeight: 1.45 }}>{STEP_LINKS[step.id]?.body}</Typography> : null}
          </ButtonBase>
        ))}
      </Box>
    </Box>
  );
}

function PipelineRow({ pipeline, onRun }: { pipeline: Pipeline; onRun: () => void }) {
  const tone = pipelineTone(pipeline);
  const busy = pipeline.status === "running" || pipeline.status === "queued";
  const canRun = pipeline.runnable && pipeline.enabled && pipeline.status === "ready";
  const last = pipeline.last_run;
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        px: 1.5,
        py: 1.25,
        borderRadius: "12px",
        transition: `background-color 0.2s ${apple.smooth}`,
        "&:hover": { bgcolor: apple.hoverFill },
        "&:hover .row-run": { opacity: 1 },
      }}
    >
      <PipelineIcon icon={pipeline.icon} category={pipeline.category} size={32} />
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Link component={NextLink} href={`/settings/pipelines/${pipeline.id}`} underline="none" sx={{ fontSize: 14, fontWeight: 600, color: apple.text, "&:hover": { textDecoration: "underline" } }}>
          {pipeline.name}
        </Link>
        <Typography sx={{ fontSize: 12, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {last ? `${runTone(last.status).label} ${relativeTime(last.finished_at || last.created_at)}` : pipeline.runnable ? "Never run" : "Opens from its page"}
          {pipeline.schedule_enabled && pipeline.next_run_at ? ` · next ${relativeTime(pipeline.next_run_at)}` : ""}
        </Typography>
      </Box>
      <ToneChip tone={tone} size="sm" />
      {pipeline.runnable ? (
        <Tooltip title={canRun ? "Run now" : busy ? "Running" : "Not ready"}>
          <span>
            <IconButton className="row-run" size="small" onClick={onRun} disabled={!canRun} aria-label={`Run ${pipeline.name}`} sx={{ opacity: { md: busy ? 1 : 0.55 }, transition: "opacity 0.2s", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised }}>
              <PlayArrowRoundedIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      ) : (
        <IconButton component={NextLink} href={pipeline.output} size="small" aria-label={`Open ${pipeline.name}`} sx={{ opacity: 0.55, border: `1px solid ${apple.hairline}`, bgcolor: apple.raised }}>
          <ArrowForwardRoundedIcon fontSize="small" />
        </IconButton>
      )}
    </Box>
  );
}

function RunRow({ run, category }: { run: Run; category: string }) {
  const tone = runTone(run.status, category);
  return (
    <ButtonBase
      component={NextLink}
      href={`/settings/pipelines/${run.pipeline_id || "daily-sync"}?run=${run.id}`}
      sx={{ width: "100%", display: "flex", alignItems: "center", gap: 1.5, px: 1.5, py: 1.1, borderRadius: "10px", textAlign: "left", "&:hover": { bgcolor: apple.hoverFill } }}
    >
      <Box className={tone.live ? "live-dot" : undefined} sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: tone.color, flexShrink: 0 }} />
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography sx={{ fontSize: 13.5, fontWeight: 550, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{run.pipeline_name || run.kind}</Typography>
        <Typography sx={{ fontSize: 12, color: run.status === "failed" ? apple.danger : apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {run.status === "failed" && run.error ? run.error : `${tone.label}${run.duration_s != null && !tone.live ? ` in ${formatDuration(run.duration_s)}` : ""} · ${run.trigger === "schedule" ? "scheduled" : run.trigger === "chained" ? "chained" : run.started_by || "manual"}`}
        </Typography>
      </Box>
      <Typography sx={{ fontSize: 12, color: apple.muted, whiteSpace: "nowrap" }}>{relativeTime(run.created_at)}</Typography>
    </ButtonBase>
  );
}

export function Overview() {
  const { me, can } = useWorkspace();
  const { pipelines, runPipeline, running } = usePlatform();
  const { openPalette } = useCommandPalette();
  const { tick } = useRefresh();
  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [connections, setConnections] = useState<ConnectionsResponse | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let alive = true;
    platform.workspace().then((data) => alive && setDetail(data)).catch(() => null);
    platform.connections().then((data) => alive && setConnections(data)).catch(() => null);
    return () => {
      alive = false;
    };
  }, [tick]);

  const runningKey = running.map((p) => `${p.id}:${p.last_run?.id}:${p.status}`).join(",");
  useEffect(() => {
    let alive = true;
    platform
      .runs({ limit: 12 })
      .then((data) => alive && setRuns(data.runs))
      .catch(() => alive && setRuns([]));
    return () => {
      alive = false;
    };
  }, [tick, runningKey]);

  const list = useMemo(() => pipelines?.pipelines || [], [pipelines]);
  const byCategory = useMemo(() => {
    const order: Category[] = ["system", "product", "marketing", "knowledge"];
    return order.map((category) => ({ category, items: list.filter((p) => p.category === category && p.enabled) })).filter((group) => group.items.length);
  }, [list]);

  const connectionStats = useMemo(() => {
    const providers = connections?.providers || [];
    const views = providers.flatMap((p) => p.connections.filter((c) => c.connected));
    return {
      connected: views.filter((c) => c.status === "connected" || c.status === "untested").length,
      failing: views.filter((c) => c.status === "error").length,
      total: providers.filter((p) => p.category !== "Code").length,
    };
  }, [connections]);

  const ready = list.filter((p) => p.enabled && (p.status === "ready" || p.status === "running" || p.status === "queued")).length;
  const blocked = list.filter((p) => p.enabled && p.status === "needs_connection");
  const dayAgo = Date.now() - 86_400_000;
  const recent = (runs || []).filter((run) => (parseUtc(run.created_at)?.getTime() || 0) > dayAgo);
  const failed = recent.filter((run) => run.status === "failed").length;
  const nextScheduled = list
    .filter((p) => p.schedule_enabled && p.next_run_at)
    .sort((a, b) => (parseUtc(a.next_run_at)?.getTime() || 0) - (parseUtc(b.next_run_at)?.getTime() || 0))[0];
  const daily = list.find((p) => p.id === "daily-sync");
  const firstName = (me?.user.name || detail?.profile.pm_display_name || "").split(" ")[0];
  const showOnboarding = detail && !detail.onboarding.complete && !detail.onboarding.dismissed && !hidden;
  const categoryOf = (id: string) => list.find((p) => p.id === id)?.category || "system";

  return (
    <PageBody>
      <Box sx={{ display: "flex", alignItems: { xs: "flex-start", md: "flex-end" }, justifyContent: "space-between", gap: 2, flexWrap: "wrap", mb: 3 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography component="h2" sx={{ fontSize: { xs: 26, md: 32 }, fontWeight: 650, letterSpacing: "-0.035em", lineHeight: 1.1 }}>
            {greeting()}
            {firstName ? `, ${firstName}` : ""}.
          </Typography>
          <Typography sx={{ mt: 0.75, fontSize: 15, color: apple.muted }}>
            {me?.workspace.name || "Your workspace"}
            {detail?.profile.product_name ? ` · ${detail.profile.product_name}` : ""}
            {running.length ? ` · ${running.length} pipeline${running.length === 1 ? "" : "s"} running` : ""}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          <PillButton variant="gray" startIcon={<SearchRoundedIcon />} onClick={() => openPalette()}>
            Search
          </PillButton>
          {daily?.enabled && daily.runnable ? (
            <PillButton
              startIcon={<PlayArrowRoundedIcon />}
              disabled={daily.status !== "ready"}
              onClick={() => void runPipeline("daily-sync")}
              title={daily.status === "ready" ? daily.description : pipelineTone(daily).label}
            >
              {daily.status === "running" || daily.status === "queued" ? "Daily sync running…" : "Run daily sync"}
            </PillButton>
          ) : null}
        </Box>
      </Box>

      {showOnboarding ? (
        <Onboarding
          detail={detail}
          canEdit={can("admin")}
          onDismiss={() => {
            setHidden(true);
            void platform.dismissOnboarding().catch(() => null);
          }}
        />
      ) : null}

      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr 1fr", lg: "repeat(4, 1fr)" }, mb: 3 }}>
        <StatTile
          label="Connections"
          value={connections ? connectionStats.connected : "–"}
          accent={accent.system.main}
          hint={
            connectionStats.failing ? (
              <Link component={NextLink} href="/settings/connections" sx={{ color: apple.danger, fontWeight: 600 }}>
                {connectionStats.failing} need attention
              </Link>
            ) : connections ? (
              `of ${connectionStats.total} services`
            ) : (
              " "
            )
          }
        />
        <StatTile label="Pipelines ready" value={pipelines ? ready : "–"} accent={accent.product.main} hint={blocked.length ? `${blocked.length} waiting on a connection` : pipelines ? "All set" : " "} />
        <StatTile label="Runs, last 24h" value={runs ? recent.length : "–"} accent={accent.marketing.main} hint={failed ? <Box component="span" sx={{ color: apple.danger, fontWeight: 600 }}>{failed} failed</Box> : runs ? "No failures" : " "} />
        <StatTile label="Next scheduled" value={nextScheduled ? relativeTime(nextScheduled.next_run_at) : "None"} accent={accent.knowledge.main} hint={nextScheduled ? nextScheduled.name : <Link component={NextLink} href="/settings/pipelines">Set a schedule</Link>} />
      </Box>

      <Box sx={{ display: "grid", gap: 3, gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.6fr) minmax(0, 1fr)" }, alignItems: "start" }}>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="h3">Pipelines</Typography>
            <PillButton variant="text" href="/settings/pipelines" endIcon={<ArrowForwardRoundedIcon />} sx={{ fontSize: 13 }}>
              All pipelines
            </PillButton>
          </Box>
          {!pipelines ? (
            <LoadingBlock rows={4} height={56} label="Loading pipelines" />
          ) : (
            <Box sx={{ display: "grid", gap: 2 }}>
              {byCategory.map((group) => (
                <Box key={group.category} sx={{ border: `1px solid ${apple.hairline}`, borderRadius: "16px", bgcolor: apple.raised, p: 1 }}>
                  <Typography sx={{ display: "flex", alignItems: "center", gap: 0.75, px: 1.5, pt: 0.75, pb: 0.5, fontSize: 11.5, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: categoryAccent(group.category).main }}>
                    {pipelines.categories[group.category] || categoryAccent(group.category).label}
                  </Typography>
                  {group.items.map((pipeline) => (
                    <PipelineRow key={pipeline.id} pipeline={pipeline} onRun={() => void runPipeline(pipeline.id)} />
                  ))}
                </Box>
              ))}
            </Box>
          )}
        </Box>
        <Box sx={{ minWidth: 0, display: "grid", gap: 3 }}>
          {blocked.length ? (
            <Box>
              <Typography variant="h3" sx={{ mb: 1 }}>
                Waiting on you
              </Typography>
              <Box sx={{ border: `1px solid ${apple.hairline}`, borderRadius: "16px", bgcolor: apple.raised, p: 1 }}>
                {Array.from(new Set(blocked.flatMap((p) => p.readiness.missing))).map((req) => {
                  const unlocks = blocked.filter((p) => p.readiness.missing.includes(req));
                  return (
                    <ButtonBase key={req} component={NextLink} href={requirementHref(req)} sx={{ width: "100%", display: "flex", alignItems: "center", gap: 1.5, px: 1.5, py: 1.1, borderRadius: "10px", textAlign: "left", "&:hover": { bgcolor: apple.hoverFill } }}>
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography sx={{ fontSize: 13.5, fontWeight: 600 }}>Connect {requirementLabel(req)}</Typography>
                        <Typography sx={{ fontSize: 12, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Unlocks {unlocks.map((p) => p.name).join(", ")}</Typography>
                      </Box>
                      <ArrowForwardRoundedIcon sx={{ fontSize: 18, color: apple.muted }} />
                    </ButtonBase>
                  );
                })}
              </Box>
            </Box>
          ) : null}
          <Box>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
              <Typography variant="h3">Recent activity</Typography>
              <PillButton variant="text" href="/settings/pipelines?tab=runs" endIcon={<ArrowForwardRoundedIcon />} sx={{ fontSize: 13 }}>
                All runs
              </PillButton>
            </Box>
            <Box sx={{ border: `1px solid ${apple.hairline}`, borderRadius: "16px", bgcolor: apple.raised, p: 1 }}>
              {runs === null ? (
                <LoadingBlock rows={4} height={40} label="Loading runs" />
              ) : runs.length ? (
                runs.slice(0, 10).map((run) => <RunRow key={run.id} run={run} category={categoryOf(run.pipeline_id)} />)
              ) : (
                <EmptyState>No runs yet. Start one from a pipeline or press ⌘K.</EmptyState>
              )}
            </Box>
          </Box>
        </Box>
      </Box>
    </PageBody>
  );
}
