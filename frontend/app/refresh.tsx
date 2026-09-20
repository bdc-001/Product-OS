"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { api, type BackgroundJob } from "@/lib/api";
import { clearHttpCache } from "@/lib/http";

export type RefreshStep = {
  ok?: boolean;
  status?: string;
  error?: string;
  jira_count?: number;
  cliq_count?: number;
  branch?: string;
  pulled?: boolean;
  already_up_to_date?: boolean;
  count?: number;
  remote_blocked?: boolean;
};

type RefreshState = {
  tick: number;
  refreshing: boolean;
  message: string;
  refreshAll: (section?: string) => Promise<void>;
};

const RefreshContext = createContext<RefreshState>({
  tick: 0,
  refreshing: false,
  message: "",
  refreshAll: async () => undefined,
});

function stepLine(job: BackgroundJob) {
  const steps = job.steps || {};
  const order = ["jira", "cliq", "roadmap", "codebase", "branches", "releases", "marketing"];
  const labels: Record<string, string> = { jira: "Jira", cliq: "Cliq", roadmap: "Roadmap", codebase: "Git", branches: "Branches", releases: "Releases", marketing: "Marketing" };
  return order
    .filter((key) => steps[key])
    .map((key) => {
      const row = steps[key] || {};
      if (row.status === "running") return `${labels[key]}…`;
      if (row.ok === false) return `${labels[key]} ✕`;
      if (row.ok) return `${labels[key]} ✓`;
      return labels[key];
    })
    .join(" · ");
}

function countLabel(name: string, count: number | undefined, ok?: boolean, error?: string) {
  if (ok === false) return error ? `${name} failed` : `${name} failed`;
  if (typeof count !== "number") return "";
  return `${name} ${count}`;
}

export function summarize(result: { ok?: boolean; error?: string; steps?: Record<string, RefreshStep> }) {
  const steps = result.steps || {};
  const parts: string[] = [];
  const jira = steps.jira;
  const cliq = steps.cliq;
  const code = steps.codebase;
  const branches = steps.branches;
  if (jira?.status === "running") {
    /* still in flight — don't claim Jira 0 */
  } else {
    const line = countLabel("Jira", jira?.jira_count, jira?.ok, jira?.error);
    if (line) parts.push(line);
    else if (jira?.error) parts.push("Jira failed");
  }
  if (cliq?.status === "running") {
    /* skip */
  } else if (cliq?.ok === false || cliq?.error) {
    parts.push(cliq.error && /expired|login/i.test(cliq.error) ? "Cliq login expired" : "Cliq failed");
  } else {
    const line = countLabel("Cliq", cliq?.cliq_count, cliq?.ok, cliq?.error);
    if (line) parts.push(line);
  }
  if (code?.status === "running") {
    /* skip */
  } else if (code?.ok === false) {
    parts.push(code.error && /whitelist|VPN|lock/i.test(code.error) ? code.error : "git failed");
  } else if (code?.error && /whitelist|VPN|interrupted/i.test(code.error)) {
    parts.push(code.error.replace(/\s+/g, " ").slice(0, 80));
  } else if (code?.pulled && code.already_up_to_date) {
    parts.push(`${code.branch || "branch"} up to date`);
  } else if (code?.pulled) {
    parts.push(`pulled ${code.branch || "branch"}`);
  } else if (code?.branch) {
    parts.push(`indexed ${code.branch} (no fetch)`);
  } else if (code?.ok) {
    parts.push("code indexed");
  }
  if (branches?.remote_blocked) parts.push("branch fetch needs VPN");
  const marketing = steps.marketing;
  if (marketing?.ok === false) parts.push("marketing assessment failed");
  else if (marketing?.count) parts.push(`${marketing.count} features assessed for marketing`);
  const releases = steps.releases;
  if (releases?.status === "running") {
    /* skip */
  } else if (releases?.ok === false) {
    parts.push("release detect failed");
  } else if (typeof releases?.count === "number" && releases.count > 0) {
    parts.push(`${releases.count} release${releases.count === 1 ? "" : "s"} queued`);
  }
  if (!parts.length) return result.ok ? "Refreshed." : result.error || "Refresh finished with errors.";
  return `Updated ${parts.join(" · ")}.`;
}

export function RefreshProvider({ children }: { children: React.ReactNode }) {
  const [tick, setTick] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");

  const refreshAll = useCallback(async (section?: string) => {
    if (section === "local") { clearHttpCache(); setTick(value=>value+1); setMessage("View reloaded."); return; }
    setRefreshing(true);
    setMessage(section ? `Refreshing ${section}…` : "Jira…");
    try {
      clearHttpCache();
      const run = section ? (callback: (job: BackgroundJob) => void) => api.refreshSection(section, callback) : api.refreshAll;
      const result = await run((job) => {
        const line = stepLine(job);
        if (line) setMessage(line);
      });
      setMessage(summarize(result));
    } catch (err) {
      setMessage(String(err));
    } finally {
      clearHttpCache();
      setTick((value) => value + 1);
      setRefreshing(false);
    }
  }, []);

  const value = useMemo(() => ({ tick, refreshing, message, refreshAll }), [tick, refreshing, message, refreshAll]);
  return <RefreshContext.Provider value={value}>{children}</RefreshContext.Provider>;
}

export function useRefresh() {
  return useContext(RefreshContext);
}
