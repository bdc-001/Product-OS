"use client";

import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Snackbar from "@mui/material/Snackbar";
import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRefresh } from "@/app/refresh";
import { useWorkspace } from "@/app/workspace";
import { peekGet } from "@/lib/http";
import { platform, type Pipeline, type PipelinesResponse, type Run } from "@/lib/platform";

type Toast = { id: number; message: string; tone: "success" | "error" | "info"; href?: string; action?: string };

type PlatformState = {
  pipelines: PipelinesResponse | null;
  byId: Record<string, Pipeline>;
  /** Pipeline id → enabled; null until the catalog loads. */
  enabled: Record<string, boolean> | null;
  running: Pipeline[];
  reloadPipelines: () => Promise<void>;
  runPipeline: (id: string, params?: Record<string, unknown>) => Promise<Run | null>;
  notify: (message: string, options?: { tone?: Toast["tone"]; href?: string; action?: string }) => void;
};

const PlatformContext = createContext<PlatformState>({
  pipelines: null,
  byId: {},
  enabled: null,
  running: [],
  reloadPipelines: async () => undefined,
  runPipeline: async () => null,
  notify: () => undefined,
});

export function usePlatform() {
  return useContext(PlatformContext);
}

const ACTIVE_POLL_MS = 5_000;
const IDLE_POLL_MS = 60_000;

export function PlatformProvider({ children }: { children: ReactNode }) {
  const path = usePathname() || "/";
  const quiet = /^\/sign-(in|up)(\/|$)/.test(path) || /\/embed\/?$/.test(path);
  const { me } = useWorkspace();
  const { tick } = useRefresh();
  const [pipelines, setPipelines] = useState<PipelinesResponse | null>(() => peekGet<PipelinesResponse>("/api/pipelines") || null);
  const [toast, setToast] = useState<Toast | null>(null);
  const timer = useRef<number | null>(null);
  const finished = useRef<Set<number>>(new Set());

  const notify = useCallback<PlatformState["notify"]>((message, options = {}) => {
    setToast({ id: Date.now(), message, tone: options.tone || "success", href: options.href, action: options.action });
  }, []);

  const reloadPipelines = useCallback(async () => {
    try {
      const next = await platform.pipelines();
      setPipelines((previous) => {
        if (previous) {
          for (const item of next.pipelines) {
            const before = previous.pipelines.find((p) => p.id === item.id);
            const run = item.last_run;
            const wasActive = before?.last_run && ["queued", "running"].includes(before.last_run.status);
            if (run && wasActive && before?.last_run?.id === run.id && !["queued", "running"].includes(run.status) && !finished.current.has(run.id)) {
              finished.current.add(run.id);
              const ok = run.status === "completed";
              window.setTimeout(
                () =>
                  notify(`${item.name} ${ok ? "finished" : run.status === "cancelled" ? "was cancelled" : "failed"}`, {
                    tone: ok ? "success" : "error",
                    href: ok ? item.output : `/settings/pipelines/${item.id}?run=${run.id}`,
                    action: ok ? "Open" : "View run",
                  }),
                0,
              );
            }
          }
        }
        return next;
      });
    } catch {
      /* the shell keeps working without the catalog */
    }
  }, [notify]);

  useEffect(() => {
    if (quiet || !me) return;
    void reloadPipelines();
  }, [quiet, me, tick, reloadPipelines]);

  const running = useMemo(
    () => (pipelines?.pipelines || []).filter((p) => p.status === "running" || p.status === "queued"),
    [pipelines],
  );

  useEffect(() => {
    if (quiet || !me) return;
    const delay = running.length ? ACTIVE_POLL_MS : IDLE_POLL_MS;
    timer.current = window.setTimeout(() => void reloadPipelines(), delay);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [quiet, me, running.length, pipelines, reloadPipelines]);

  const runPipeline = useCallback<PlatformState["runPipeline"]>(
    async (id, params = {}) => {
      const name = pipelines?.pipelines.find((p) => p.id === id)?.name || "Pipeline";
      try {
        const run = await platform.runPipeline(id, params);
        notify(`${name} started`, { tone: "info", href: `/settings/pipelines/${id}?run=${run.id}`, action: "Watch" });
        await reloadPipelines();
        return run;
      } catch (err) {
        notify(err instanceof Error ? err.message : `Could not start ${name}.`, { tone: "error", href: `/settings/pipelines/${id}`, action: "Details" });
        return null;
      }
    },
    [pipelines, notify, reloadPipelines],
  );

  const value = useMemo<PlatformState>(() => {
    const list = pipelines?.pipelines || [];
    return {
      pipelines,
      byId: Object.fromEntries(list.map((p) => [p.id, p])),
      enabled: pipelines ? Object.fromEntries(list.map((p) => [p.id, p.enabled])) : null,
      running,
      reloadPipelines,
      runPipeline,
      notify,
    };
  }, [pipelines, running, reloadPipelines, runPipeline, notify]);

  return (
    <PlatformContext.Provider value={value}>
      {children}
      <Snackbar
        key={toast?.id}
        open={Boolean(toast)}
        autoHideDuration={toast?.tone === "error" ? 9000 : 5000}
        onClose={(_, reason) => reason !== "clickaway" && setToast(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      >
        {toast ? (
          <Alert
            severity={toast.tone}
            variant="filled"
            onClose={() => setToast(null)}
            sx={{ alignItems: "center", borderRadius: "12px", minWidth: 280 }}
            action={
              toast.href ? (
                <Button component={NextLink} href={toast.href} color="inherit" size="small" onClick={() => setToast(null)} sx={{ fontWeight: 600 }}>
                  {toast.action || "Open"}
                </Button>
              ) : undefined
            }
          >
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </PlatformContext.Provider>
  );
}
