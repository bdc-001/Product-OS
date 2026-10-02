"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import ReplayRoundedIcon from "@mui/icons-material/ReplayRounded";
import StopRoundedIcon from "@mui/icons-material/StopRounded";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import Typography from "@mui/material/Typography";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePlatform } from "@/app/platform-state";
import { Banner, LoadingBlock, PillButton, SideDrawer } from "@/app/ui";
import { PipelineIcon, STEP_LABELS, ToneChip, absoluteTime, formatDuration, relativeTime, runTone, stepTone } from "@/app/ui/platform";
import { apple, pmm } from "@/app/ui/tokens";
import { isActive, platform, type Run, type RunDetail, type RunStep } from "@/lib/platform";

const TRIGGERS: Record<string, string> = { manual: "Manual", schedule: "Scheduled", chained: "Part of a sync", retry: "Retry" };

export function triggerLabel(trigger: string) {
  return TRIGGERS[trigger] || trigger;
}

/** `?run=<id>` opens the drawer on any page that renders it. */
export function useRunParam(): [number | null, (id: number | null) => void] {
  const router = useRouter();
  const path = usePathname() || "/settings/pipelines";
  const params = useSearchParams();
  const raw = Number(params.get("run") || 0);
  const set = useCallback(
    (id: number | null) => {
      const next = new URLSearchParams(params.toString());
      if (id) next.set("run", String(id));
      else next.delete("run");
      router.replace(`${path}${next.toString() ? `?${next}` : ""}`, { scroll: false });
    },
    [params, path, router],
  );
  return [raw > 0 ? raw : null, set];
}

function stepFacts(step: RunStep): string {
  const facts: string[] = [];
  for (const [key, value] of Object.entries(step)) {
    if (["status", "ok", "error", "reason"].includes(key)) continue;
    if (typeof value === "number") facts.push(`${value.toLocaleString()} ${key.replace(/_/g, " ")}`);
    else if (typeof value === "boolean" && value) facts.push(key.replace(/_/g, " "));
  }
  return facts.slice(0, 4).join(" · ");
}

function resultFacts(result: Record<string, unknown>): [string, string][] {
  const out: [string, string][] = [];
  for (const [key, value] of Object.entries(result)) {
    if (value === null || value === undefined || value === "") continue;
    if (typeof value === "number" || typeof value === "boolean") out.push([key, String(value)]);
    else if (typeof value === "string" && value.length < 120) out.push([key, value]);
    else if (Array.isArray(value)) out.push([key, `${value.length} item${value.length === 1 ? "" : "s"}`]);
  }
  return out.slice(0, 12);
}

const LOG_COLOR: Record<string, string> = { error: apple.danger, critical: apple.danger, warning: pmm.amber };

function Logs({ run }: { run: RunDetail }) {
  const box = useRef<HTMLDivElement | null>(null);
  const live = isActive(run);
  useEffect(() => {
    if (live && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [run.logs.length, live]);
  if (!run.logs.length) return <Typography sx={{ fontSize: 13, color: apple.muted }}>{live ? "Waiting for output…" : "No log lines were recorded."}</Typography>;
  return (
    <Box
      ref={box}
      role="log"
      aria-live={live ? "polite" : "off"}
      sx={{ maxHeight: 320, overflow: "auto", p: 1.5, borderRadius: "12px", bgcolor: apple.wash, border: `1px solid ${apple.hairline}`, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 12, lineHeight: 1.6 }}
    >
      {run.logs.map((line, index) => (
        <Box key={`${line.at}-${index}`} sx={{ display: "flex", gap: 1.25, color: LOG_COLOR[line.level] || apple.text }}>
          <Box component="span" sx={{ color: apple.muted, flexShrink: 0 }}>
            {(line.at || "").slice(11, 19)}
          </Box>
          <Box component="span" sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {line.message}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography sx={{ fontSize: 11.5, color: apple.muted, fontWeight: 600 }}>{label}</Typography>
      <Typography sx={{ fontSize: 13.5, mt: 0.25, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{value}</Typography>
    </Box>
  );
}

function RunSheet({ runId, onClose, onOpenRun }: { runId: number; onClose: () => void; onOpenRun: (id: number) => void }) {
  const { byId, reloadPipelines, notify } = usePlatform();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"" | "cancel" | "retry">("");
  const [showRaw, setShowRaw] = useState(false);

  const load = useCallback(async () => {
    try {
      setRun(await platform.run(runId));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  const live = isActive(run);
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => void load(), 2_000);
    return () => window.clearInterval(timer);
  }, [live, load]);

  const pipeline = run ? byId[run.pipeline_id] : undefined;
  const steps = useMemo(() => {
    if (!run) return [] as [string, RunStep | undefined][];
    const order = pipeline?.steps || [];
    const seen = new Set<string>();
    const out: [string, RunStep | undefined][] = [];
    for (const id of order) {
      seen.add(id);
      out.push([id, run.steps[id]]);
    }
    for (const [id, step] of Object.entries(run.steps)) if (!seen.has(id)) out.push([id, step]);
    return out;
  }, [run, pipeline]);

  if (error && !run) return <Banner severity="error">{error}</Banner>;
  if (!run) return <LoadingBlock rows={4} height={48} label="Loading run" />;

  const tone = runTone(run.status, pipeline?.category);
  const facts = resultFacts(run.result);
  const canRetry = (run.status === "failed" || run.status === "cancelled") && Boolean(run.task) && pipeline?.runnable !== false;

  async function act(kind: "cancel" | "retry") {
    if (!run) return;
    setBusy(kind);
    try {
      if (kind === "cancel") {
        await platform.cancelRun(run.id);
        await load();
      } else {
        const next = await platform.retryRun(run.id);
        notify(`Retrying ${pipeline?.name || "run"}`, { tone: "info" });
        onOpenRun(next.id);
      }
      void reloadPipelines();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  return (
    <Box sx={{ display: "grid", gap: 2.5 }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5 }}>
        {pipeline ? <PipelineIcon icon={pipeline.icon} category={pipeline.category} size={44} /> : null}
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography component="h2" sx={{ fontSize: 19, fontWeight: 650, letterSpacing: "-0.02em" }}>
            {run.pipeline_name || pipeline?.name || run.kind}
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 0.5 }}>
            <ToneChip tone={tone} size="sm" />
            <Typography sx={{ fontSize: 12.5, color: apple.muted }}>Run #{run.id}</Typography>
          </Box>
        </Box>
        <IconButton onClick={onClose} aria-label="Close" size="small">
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </Box>

      <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: "repeat(2, minmax(0,1fr))", p: 1.75, borderRadius: "14px", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised }}>
        <Meta label="Trigger" value={triggerLabel(run.trigger)} />
        <Meta label="Started by" value={run.started_by || (run.trigger === "schedule" ? "Scheduler" : "")} />
        <Meta label={run.started_at ? "Started" : "Queued"} value={absoluteTime(run.started_at || run.created_at)} />
        <Meta label={live ? "Running for" : "Took"} value={formatDuration(run.duration_s)} />
        {run.attempts > 1 ? <Meta label="Attempts" value={String(run.attempts)} /> : null}
      </Box>

      {run.cancel_requested && live ? <Banner severity="info">Stopping after the current step…</Banner> : null}
      {run.error && run.status !== "completed" ? <Banner severity={run.status === "cancelled" ? "info" : "error"}>{run.error}</Banner> : null}
      {error ? <Banner severity="error">{error}</Banner> : null}

      {steps.length ? (
        <Box>
          <Typography sx={{ fontSize: 13, fontWeight: 650, mb: 1 }}>Steps</Typography>
          <Box component="ol" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: 0 }}>
            {steps.map(([id, step], index) => {
              const t = stepTone(step);
              const facts = step ? stepFacts(step) : "";
              return (
                <Box component="li" key={id} sx={{ display: "grid", gridTemplateColumns: "18px minmax(0,1fr) auto", gap: 1.25, alignItems: "start", position: "relative", pb: index === steps.length - 1 ? 0 : 1.5 }}>
                  <Box sx={{ position: "relative", height: "100%" }}>
                    <Box className={t.live ? "live-dot" : undefined} sx={{ width: 10, height: 10, mt: "5px", ml: "4px", borderRadius: "50%", bgcolor: t.color, boxShadow: `0 0 0 3px ${t.fill}` }} />
                    {index < steps.length - 1 ? <Box aria-hidden sx={{ position: "absolute", left: 8, top: 20, bottom: -4, width: 2, bgcolor: apple.hairline }} /> : null}
                  </Box>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{STEP_LABELS[id] || id}</Typography>
                    {facts ? <Typography sx={{ fontSize: 12.5, color: apple.muted }}>{facts}</Typography> : null}
                    {step?.error || step?.reason ? <Typography sx={{ fontSize: 12.5, color: step.ok === false ? apple.danger : apple.muted, wordBreak: "break-word" }}>{String(step.error || step.reason)}</Typography> : null}
                  </Box>
                  <ToneChip tone={t} size="sm" />
                </Box>
              );
            })}
          </Box>
        </Box>
      ) : null}

      {facts.length ? (
        <Box>
          <Typography sx={{ fontSize: 13, fontWeight: 650, mb: 1 }}>Result</Typography>
          <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: "repeat(2, minmax(0,1fr))" }}>
            {facts.map(([key, value]) => (
              <Meta key={key} label={key.replace(/_/g, " ")} value={value} />
            ))}
          </Box>
        </Box>
      ) : null}

      <Box>
        <Typography sx={{ fontSize: 13, fontWeight: 650, mb: 1 }}>Log</Typography>
        <Logs run={run} />
      </Box>

      {Object.keys(run.params).length || Object.keys(run.result).length ? (
        <Box>
          <ButtonBase onClick={() => setShowRaw((v) => !v)} sx={{ fontSize: 12.5, color: apple.muted, fontWeight: 600 }}>
            {showRaw ? "Hide" : "Show"} raw parameters and result
          </ButtonBase>
          <Collapse in={showRaw} unmountOnExit>
            <Box component="pre" sx={{ mt: 1, p: 1.5, borderRadius: "12px", bgcolor: apple.wash, fontSize: 11.5, overflow: "auto", maxHeight: 280 }}>
              {JSON.stringify({ params: run.params, result: run.result }, null, 2)}
            </Box>
          </Collapse>
        </Box>
      ) : null}

      {run.children.length ? (
        <Box>
          <Typography sx={{ fontSize: 13, fontWeight: 650, mb: 1 }}>Retries</Typography>
          <RunList runs={run.children} onOpen={onOpenRun} dense />
        </Box>
      ) : null}

      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", pt: 1, borderTop: `1px solid ${apple.hairline}` }}>
        {live ? (
          <PillButton variant="gray" startIcon={<StopRoundedIcon />} disabled={Boolean(busy) || run.cancel_requested} onClick={() => void act("cancel")}>
            {busy === "cancel" ? "Stopping…" : "Stop run"}
          </PillButton>
        ) : null}
        {canRetry ? (
          <PillButton startIcon={<ReplayRoundedIcon />} disabled={Boolean(busy)} onClick={() => void act("retry")}>
            {busy === "retry" ? "Starting…" : "Retry"}
          </PillButton>
        ) : null}
        {pipeline?.output && run.status === "completed" ? (
          <PillButton variant="gray" href={pipeline.output} endIcon={<ArrowForwardRoundedIcon />}>
            Open output
          </PillButton>
        ) : null}
        {pipeline ? (
          <PillButton variant="text" href={`/settings/pipelines/${pipeline.id}`} sx={{ color: apple.muted }}>
            Pipeline settings
          </PillButton>
        ) : null}
      </Box>
    </Box>
  );
}

export function RunDrawer({ runId, onClose, onOpenRun }: { runId: number | null; onClose: () => void; onOpenRun: (id: number) => void }) {
  return (
    <SideDrawer open={Boolean(runId)} onClose={onClose} width={{ xs: "100%", sm: 560 }}>
      {runId ? <RunSheet key={runId} runId={runId} onClose={onClose} onOpenRun={onOpenRun} /> : null}
    </SideDrawer>
  );
}

export function RunList({ runs, onOpen, showPipeline, dense, selected }: { runs: Run[]; onOpen: (id: number) => void; showPipeline?: boolean; dense?: boolean; selected?: number | null }) {
  const { byId } = usePlatform();
  if (!runs.length) return null;
  return (
    <Box sx={{ border: `1px solid ${apple.hairline}`, borderRadius: "14px", bgcolor: apple.raised, overflow: "hidden" }}>
      {runs.map((run, index) => {
        const pipeline = byId[run.pipeline_id];
        const tone = runTone(run.status, pipeline?.category);
        return (
          <ButtonBase
            key={run.id}
            onClick={() => onOpen(run.id)}
            aria-label={`Run ${run.id}, ${tone.label}`}
            sx={{
              width: "100%",
              display: "grid",
              gridTemplateColumns: showPipeline ? { xs: "minmax(0,1fr) auto", sm: "minmax(0,1.6fr) 120px 110px 80px" } : { xs: "minmax(0,1fr) auto", sm: "minmax(0,1fr) 110px auto" },
              alignItems: "center",
              gap: 1.5,
              px: 2,
              py: dense ? 1 : 1.35,
              textAlign: "left",
              borderTop: index ? `1px solid ${apple.hairline}` : "none",
              bgcolor: selected === run.id ? apple.selFill : "transparent",
              transition: `background-color 0.2s ${apple.smooth}`,
              "&:hover": { bgcolor: apple.hoverFill },
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, minWidth: 0 }}>
              {showPipeline && pipeline ? <PipelineIcon icon={pipeline.icon} category={pipeline.category} size={28} /> : null}
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: 14, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {showPipeline ? run.pipeline_name || pipeline?.name || run.kind : `Run #${run.id}`}
                </Typography>
                <Typography sx={{ fontSize: 12, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {triggerLabel(run.trigger)}
                  {run.started_by ? ` · ${run.started_by}` : ""}
                  {run.error && run.status === "failed" ? ` · ${run.error}` : ""}
                </Typography>
              </Box>
            </Box>
            {showPipeline ? (
              <Box sx={{ display: { xs: "none", sm: "block" } }}>
                <ToneChip tone={tone} size="sm" />
              </Box>
            ) : null}
            <Typography title={absoluteTime(run.created_at)} sx={{ display: { xs: "none", sm: "block" }, fontSize: 12.5, color: apple.muted }}>
              {relativeTime(run.created_at)}
            </Typography>
            <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
              {showPipeline ? (
                <Typography sx={{ fontSize: 12.5, color: apple.muted, display: { xs: "none", sm: "block" }, fontVariantNumeric: "tabular-nums" }}>{formatDuration(run.duration_s)}</Typography>
              ) : (
                <ToneChip tone={tone} size="sm" />
              )}
              {showPipeline ? (
                <Box sx={{ display: { xs: "block", sm: "none" } }}>
                  <ToneChip tone={tone} size="sm" />
                </Box>
              ) : null}
            </Box>
          </ButtonBase>
        );
      })}
    </Box>
  );
}
