"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import LinkRoundedIcon from "@mui/icons-material/LinkRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import ScheduleRoundedIcon from "@mui/icons-material/ScheduleRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import TouchAppOutlinedIcon from "@mui/icons-material/TouchAppOutlined";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import InputAdornment from "@mui/material/InputAdornment";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { RunDrawer, RunList, useRunParam } from "@/app/settings/pipelines/run-view";
import { usePlatform } from "@/app/platform-state";
import { Banner, EmptyState, LoadingBlock, PageBody, PageHeader, PillButton, Segmented } from "@/app/ui";
import { PipelineIcon, ToneChip, describeSchedule, pipelineTone, relativeTime, requirementHref, requirementLabel, runTone } from "@/app/ui/platform";
import { accent, apple, categoryAccent, shadow } from "@/app/ui/tokens";
import { platform, type Pipeline, type Run } from "@/lib/platform";

const CATEGORY_ORDER = ["product", "marketing", "knowledge", "system"] as const;

function busy(pipeline: Pipeline) {
  return pipeline.status === "running" || pipeline.status === "queued";
}

function PipelineAction({ pipeline }: { pipeline: Pipeline }) {
  const { runPipeline } = usePlatform();
  const [starting, setStarting] = useState(false);
  const missing = pipeline.readiness.missing[0];
  if (!pipeline.enabled) return null;
  if (missing) {
    return (
      <PillButton size="small" variant="gray" href={requirementHref(missing)} startIcon={<LinkRoundedIcon />}>
        Connect {requirementLabel(missing)}
      </PillButton>
    );
  }
  if (!pipeline.runnable) {
    return (
      <PillButton size="small" variant="gray" href={pipeline.output} endIcon={<ArrowForwardRoundedIcon />}>
        Open
      </PillButton>
    );
  }
  return (
    <PillButton
      size="small"
      startIcon={<PlayArrowRoundedIcon />}
      disabled={starting || busy(pipeline)}
      onClick={async () => {
        setStarting(true);
        await runPipeline(pipeline.id);
        setStarting(false);
      }}
    >
      {busy(pipeline) ? "Running…" : starting ? "Starting…" : "Run"}
    </PillButton>
  );
}

function PipelineCard({ pipeline }: { pipeline: Pipeline }) {
  const tone = pipelineTone(pipeline);
  const last = pipeline.last_run;
  const tint = categoryAccent(pipeline.category);
  return (
    <Box
      sx={{
        position: "relative",
        display: "flex",
        flexDirection: "column",
        gap: 1.25,
        p: 2.25,
        borderRadius: "16px",
        border: `1px solid ${pipeline.status === "connection_error" ? apple.dangerLine : apple.hairline}`,
        bgcolor: apple.raised,
        opacity: pipeline.enabled ? 1 : 0.65,
        transition: `border-color 0.2s ${apple.smooth}, transform 0.35s ${apple.pop}, box-shadow 0.25s ${apple.smooth}`,
        "&:hover": { borderColor: apple.hairlineHover, transform: "translateY(-2px)", boxShadow: shadow.hover },
        "&:focus-within": { borderColor: apple.hairlineHover },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
        <PipelineIcon icon={pipeline.icon} category={pipeline.category} size={40} />
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Link
            component={NextLink}
            href={`/settings/pipelines/${pipeline.id}`}
            underline="none"
            sx={{
              fontSize: 15,
              fontWeight: 650,
              letterSpacing: "-0.01em",
              color: apple.text,
              "&::after": { content: '""', position: "absolute", inset: 0, borderRadius: "16px" },
              "&:focus-visible": { outline: "none" },
              "&:focus-visible::after": { outline: `2px solid ${apple.ink}`, outlineOffset: 2 },
            }}
          >
            {pipeline.name}
          </Link>
          <Typography sx={{ fontSize: 12, color: tint.main, fontWeight: 600 }}>{pipeline.category_label}</Typography>
        </Box>
        <ToneChip tone={tone} size="sm" title={pipeline.readiness.failing.length ? `${pipeline.readiness.failing.map(requirementLabel).join(", ")} failed its last check` : undefined} />
      </Box>
      <Typography sx={{ fontSize: 13, color: apple.muted, lineHeight: 1.5, flex: 1 }}>{pipeline.description}</Typography>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, minHeight: 32 }}>
        <Typography sx={{ display: "flex", alignItems: "center", gap: 0.5, fontSize: 12, color: apple.muted, flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {pipeline.interactive ? (
            <>
              <TouchAppOutlinedIcon sx={{ fontSize: 15 }} /> Runs from its page
            </>
          ) : pipeline.schedule_enabled && pipeline.schedule ? (
            <>
              <ScheduleRoundedIcon sx={{ fontSize: 15 }} /> {describeSchedule(pipeline.schedule)}
            </>
          ) : last ? (
            <>Last run {relativeTime(last.created_at)} · {runTone(last.status).label.toLowerCase()}</>
          ) : (
            <>Not run yet</>
          )}
        </Typography>
        <Box sx={{ position: "relative", zIndex: 1 }}>
          <PipelineAction pipeline={pipeline} />
        </Box>
      </Box>
    </Box>
  );
}

function FeaturedSync({ pipeline }: { pipeline: Pipeline }) {
  const { byId } = usePlatform();
  const tone = pipelineTone(pipeline);
  const last = pipeline.last_run;
  return (
    <Box
      component="section"
      aria-label={pipeline.name}
      sx={{
        position: "relative",
        overflow: "hidden",
        mb: 4,
        p: { xs: 2.5, md: 3 },
        borderRadius: "20px",
        border: `1px solid ${apple.hairline}`,
        background: `radial-gradient(120% 140% at 0% 0%, ${accent.system.fill} 0%, transparent 55%), radial-gradient(90% 120% at 100% 100%, ${accent.product.fill} 0%, transparent 60%), ${apple.raised}`,
      }}
    >
      <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start", flexWrap: "wrap" }}>
        <PipelineIcon icon={pipeline.icon} category={pipeline.category} size={52} />
        <Box sx={{ minWidth: 0, flex: "1 1 320px" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
            <Typography component="h2" sx={{ fontSize: 21, fontWeight: 650, letterSpacing: "-0.02em" }}>
              {pipeline.name}
            </Typography>
            <ToneChip tone={tone} size="sm" />
          </Box>
          <Typography sx={{ mt: 0.75, fontSize: 14, color: apple.muted, lineHeight: 1.55, maxWidth: 640 }}>{pipeline.description}</Typography>
          <Typography sx={{ mt: 1, fontSize: 12.5, color: apple.muted }}>
            {pipeline.schedule_enabled && pipeline.schedule ? `${describeSchedule(pipeline.schedule)}${pipeline.next_run_at ? ` · next ${relativeTime(pipeline.next_run_at)}` : ""}` : "Not scheduled"}
            {last ? ` · last run ${relativeTime(last.created_at)} (${runTone(last.status).label.toLowerCase()})` : ""}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          <PillButton variant="gray" size="small" href={`/settings/pipelines/${pipeline.id}`}>
            Configure
          </PillButton>
          <PipelineAction pipeline={pipeline} />
        </Box>
      </Box>
      {pipeline.chain.length ? (
        <Box sx={{ mt: 2.5, display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap" }}>
          {pipeline.chain.map((id, index) => {
            const step = byId[id];
            if (!step) return null;
            const ready = step.status !== "needs_connection" && step.enabled;
            return (
              <Box key={id} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                {index ? <Box aria-hidden sx={{ width: 14, height: 1.5, bgcolor: apple.hairline, borderRadius: 1 }} /> : null}
                <Box
                  component={NextLink}
                  href={`/settings/pipelines/${id}`}
                  title={step.readiness.missing.length ? `${step.name} needs ${step.readiness.missing.map(requirementLabel).join(" and ")}` : `${step.name} runs in this sync`}
                  sx={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 0.75,
                    px: 1.1,
                    py: 0.5,
                    borderRadius: 999,
                    fontSize: 12.5,
                    fontWeight: 600,
                    textDecoration: "none",
                    color: ready ? apple.text : apple.muted,
                    bgcolor: ready ? apple.raised : "transparent",
                    border: `1px ${ready ? "solid" : "dashed"} ${apple.hairline}`,
                    "&:hover": { borderColor: apple.hairlineHover },
                  }}
                >
                  <Box component="span" sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: ready ? categoryAccent(step.category).main : apple.hairline }} />
                  {step.name}
                </Box>
              </Box>
            );
          })}
        </Box>
      ) : null}
    </Box>
  );
}

function Catalog() {
  const { pipelines } = usePlatform();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [readyOnly, setReadyOnly] = useState(false);
  const list = pipelines?.pipelines || [];
  const featured = list.find((p) => p.id === "daily-sync");
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return list.filter(
      (p) =>
        p.id !== "daily-sync" &&
        (category === "all" || p.category === category) &&
        (!readyOnly || (p.enabled && p.status !== "needs_connection")) &&
        (!needle || `${p.name} ${p.description} ${p.category_label}`.toLowerCase().includes(needle)),
    );
  }, [list, query, category, readyOnly]);
  const groups = CATEGORY_ORDER.map((id) => ({ id, label: pipelines?.categories[id] || id, items: filtered.filter((p) => p.category === id) })).filter((g) => g.items.length);
  const waiting = list.filter((p) => p.status === "needs_connection").length;

  if (!pipelines) return <LoadingBlock rows={3} height={150} label="Loading pipelines" />;

  return (
    <>
      {featured && !query && (category === "all" || category === "system") ? <FeaturedSync pipeline={featured} /> : null}
      <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", flexWrap: "wrap", mb: 3 }}>
        <TextField
          size="small"
          placeholder="Search pipelines"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          sx={{ width: { xs: "100%", sm: 260 } }}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }, htmlInput: { "aria-label": "Search pipelines" } }}
        />
        <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
          {[{ id: "all", label: "All" }, ...CATEGORY_ORDER.filter((id) => id !== "system").map((id) => ({ id, label: pipelines.categories[id] || id }))].map((item) => (
            <Chip key={item.id} label={item.label} onClick={() => setCategory(item.id)} variant={category === item.id ? "filled" : "outlined"} color={category === item.id ? "primary" : "default"} sx={{ borderRadius: "9px" }} />
          ))}
          <Chip label="Ready to run" onClick={() => setReadyOnly((v) => !v)} variant={readyOnly ? "filled" : "outlined"} color={readyOnly ? "primary" : "default"} sx={{ borderRadius: "9px" }} />
        </Box>
        {waiting ? (
          <Typography sx={{ ml: { sm: "auto" }, fontSize: 12.5, color: apple.muted }}>
            {waiting} waiting on a connection ·{" "}
            <Link component={NextLink} href="/settings/connections" sx={{ fontWeight: 600 }}>
              Connections
            </Link>
          </Typography>
        ) : null}
      </Box>
      {groups.map((group) => (
        <Box component="section" key={group.id} sx={{ mb: 4 }}>
          <Typography variant="h3" sx={{ mb: 1.5, display: "flex", alignItems: "center", gap: 1 }}>
            <Box component="span" sx={{ width: 8, height: 8, borderRadius: "3px", bgcolor: categoryAccent(group.id).main }} />
            {group.label} <Box component="span" sx={{ color: apple.muted, fontWeight: 500 }}>· {group.items.length}</Box>
          </Typography>
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0,1fr))", xl: "repeat(3, minmax(0,1fr))" } }}>
            {group.items.map((pipeline) => (
              <PipelineCard key={pipeline.id} pipeline={pipeline} />
            ))}
          </Box>
        </Box>
      ))}
      {!groups.length ? <EmptyState>No pipelines match{query ? ` “${query}”` : " these filters"}.</EmptyState> : null}
    </>
  );
}

const STATUS_FILTERS = [
  { id: "", label: "All" },
  { id: "queued,running", label: "Active" },
  { id: "failed", label: "Failed" },
  { id: "completed", label: "Completed" },
];

function History({ onOpen, selected }: { onOpen: (id: number) => void; selected: number | null }) {
  const { pipelines, running } = usePlatform();
  const [status, setStatus] = useState("");
  const [pipeline, setPipeline] = useState("");
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [next, setNext] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await platform.runs({ status, pipeline, limit: 30 });
      setRuns(data.runs);
      setNext(data.next_before);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [status, pipeline]);

  useEffect(() => {
    setRuns(null);
    void load();
  }, [load]);

  const activeCount = running.length;
  useEffect(() => {
    if (!activeCount) return;
    const timer = window.setInterval(() => void load(), 5_000);
    return () => window.clearInterval(timer);
  }, [activeCount, load]);

  async function loadMore() {
    if (!next) return;
    setMore(true);
    try {
      const data = await platform.runs({ status, pipeline, limit: 30, before: next });
      setRuns((current) => [...(current || []), ...data.runs]);
      setNext(data.next_before);
    } finally {
      setMore(false);
    }
  }

  const runnable = (pipelines?.pipelines || []).filter((p) => p.runnable);
  return (
    <>
      <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", flexWrap: "wrap", mb: 2 }}>
        <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
          {STATUS_FILTERS.map((item) => (
            <Chip key={item.id || "all"} label={item.label} onClick={() => setStatus(item.id)} variant={status === item.id ? "filled" : "outlined"} color={status === item.id ? "primary" : "default"} sx={{ borderRadius: "9px" }} />
          ))}
        </Box>
        <TextField select size="small" label="Pipeline" value={pipeline} onChange={(event) => setPipeline(event.target.value)} sx={{ minWidth: 220 }}>
          <MenuItem value="">All pipelines</MenuItem>
          {runnable.map((p) => (
            <MenuItem key={p.id} value={p.id}>
              {p.name}
            </MenuItem>
          ))}
        </TextField>
      </Box>
      {error ? <Banner severity="error">{error}</Banner> : null}
      {!runs ? (
        <LoadingBlock rows={6} height={52} label="Loading runs" />
      ) : runs.length ? (
        <>
          <RunList runs={runs} onOpen={onOpen} showPipeline selected={selected} />
          {next ? (
            <Box sx={{ mt: 2, display: "flex", justifyContent: "center" }}>
              <PillButton variant="gray" size="small" disabled={more} onClick={() => void loadMore()}>
                {more ? "Loading…" : "Load older runs"}
              </PillButton>
            </Box>
          ) : null}
        </>
      ) : (
        <EmptyState>{status || pipeline ? "No runs match these filters." : "Nothing has run yet. Start a pipeline from the catalog and it will show up here."}</EmptyState>
      )}
    </>
  );
}

function PipelinesHub() {
  const router = useRouter();
  const path = usePathname() || "/settings/pipelines";
  const params = useSearchParams();
  const tab = params.get("tab") === "runs" ? "runs" : "catalog";
  const [runId, setRunId] = useRunParam();
  const { running } = usePlatform();

  const setTab = (next: string) => {
    const query = new URLSearchParams(params.toString());
    if (next === "runs") query.set("tab", "runs");
    else query.delete("tab");
    router.replace(`${path}${query.toString() ? `?${query}` : ""}`, { scroll: false });
  };

  return (
    <PageBody>
      <PageHeader
        title="Pipelines"
        subtitle="Everything this workspace can produce. Connect what a pipeline needs, then run it now or put it on a schedule."
        tabs={
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { id: "catalog", label: "Catalog" },
              { id: "runs", label: running.length ? `Run history · ${running.length} active` : "Run history" },
            ]}
          />
        }
      />
      {tab === "runs" ? <History onOpen={setRunId} selected={runId} /> : <Catalog />}
      <RunDrawer runId={runId} onClose={() => setRunId(null)} onOpenRun={setRunId} />
    </PageBody>
  );
}

export default function PipelinesPage() {
  return (
    <Suspense fallback={<PageBody><LoadingBlock rows={3} height={150} /></PageBody>}>
      <PipelinesHub />
    </Suspense>
  );
}
