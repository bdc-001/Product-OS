"use client";

import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import LinearProgress from "@mui/material/LinearProgress";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useCommandPalette } from "@/app/command-palette";
import { pageTitle } from "@/app/navigation";
import { useRefresh } from "@/app/refresh";
import { Banner, PillButton } from "@/app/ui";
import { apple } from "@/app/ui/tokens";
import { api, peekGet } from "@/lib/api";

type Health = { last_run_age_seconds?: number | null; last_run_stale?: boolean; dead_letter?: boolean };

function formatAge(seconds: number | null | undefined) {
  if (seconds == null) return "";
  if (seconds < 60) return "just now";
  const hours = Math.floor(seconds / 3600);
  if (hours >= 24) return `${Math.floor(hours / 24)}d ago`;
  if (hours >= 1) return `${hours}h ago`;
  return `${Math.floor(seconds / 60)}m ago`;
}

/** Which refresh section a page reloads; pages without one manage their own runs. */
function refreshScope(path: string): string | null {
  if (path === "/") return "all";
  if (path.startsWith("/week")) return "overview";
  if (path.startsWith("/jira") || path.startsWith("/issues")) return "jira";
  if (path.startsWith("/cliq")) return "cliq";
  if (path.startsWith("/roadmap")) return "roadmap";
  if (path.startsWith("/codebase")) return "codebase";
  if (path.startsWith("/competitors")) return "competitors";
  if (path.startsWith("/marketing")) return "all";
  if (path.startsWith("/notes") || path.startsWith("/lms") || path.startsWith("/prd") || path.startsWith("/prototype") || path.startsWith("/comms") || path.startsWith("/artifacts") || path.startsWith("/releases")) return "local";
  return null;
}

export function PulseBar() {
  const cached = peekGet<Health>("/api/workspace/summary");
  const [health, setHealth] = useState<Health>(cached || {});
  const { tick, refreshing, message, refreshAll } = useRefresh();
  const { openPalette } = useCommandPalette();
  const path = usePathname() || "/";
  const router = useRouter();

  useEffect(() => {
    api.workspaceSummary().then(setHealth).catch(() => null);
  }, [tick]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      if (event.key !== "g" || event.metaKey || event.ctrlKey || event.altKey) return;
      const next = (second: KeyboardEvent) => {
        window.removeEventListener("keydown", next, true);
        const routes: Record<string, string> = { h: "/", w: "/week", s: "/week", u: "/week?view=uat", p: "/settings/pipelines", c: "/settings/connections", r: "/settings/repositories", j: "/jira" };
        const to = routes[second.key.toLowerCase()];
        if (to) {
          second.preventDefault();
          router.push(to);
        }
      };
      window.addEventListener("keydown", next, true);
      window.setTimeout(() => window.removeEventListener("keydown", next, true), 800);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  const scope = refreshScope(path);
  const stale = Boolean(health.last_run_stale);
  const age = formatAge(health.last_run_age_seconds);
  const label = scope === "local" ? "Reload" : scope === "all" ? "Sync all" : "Refresh";

  return (
    <>
      <Box
        component="header"
        className="pulse"
        sx={{
          px: { xs: 2, md: 3, xl: 4 },
          py: 1.25,
          minHeight: 56,
          display: "flex",
          alignItems: "center",
          gap: 2,
          borderBottom: `1px solid ${apple.hairline}`,
          bgcolor: apple.page,
          backdropFilter: "saturate(180%) blur(20px)",
          WebkitBackdropFilter: "saturate(180%) blur(20px)",
          position: "sticky",
          top: 0,
          zIndex: 8,
        }}
      >
        <Typography component="h1" sx={{ fontSize: 18, fontWeight: 650, letterSpacing: "-0.025em", m: 0, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {pageTitle(path)}
        </Typography>
        {scope ? (
          <Typography role="status" title={message || ""} sx={{ display: { xs: "none", sm: "block" }, maxWidth: 280, fontSize: 12, whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden", color: stale && !message ? apple.danger : apple.muted }}>
            {message || (age ? `Synced ${age}` : "Not synced yet")}
          </Typography>
        ) : null}
        <Tooltip title="Search (⌘K)">
          <IconButton onClick={() => openPalette()} aria-label="Search workspace" sx={{ display: { xs: "none", md: "inline-flex" }, color: apple.muted }}>
            <SearchRoundedIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        {scope ? (
          <PillButton
            variant="gray"
            type="button"
            startIcon={<RefreshRoundedIcon className={refreshing ? "sync-spinning" : undefined} />}
            onClick={() => refreshAll(scope === "all" ? undefined : scope)}
            disabled={refreshing}
            title={scope === "all" ? "Run every connected source" : `Refresh ${scope}`}
          >
            {refreshing ? "Syncing…" : label}
          </PillButton>
        ) : null}
        {refreshing ? <LinearProgress aria-label="Refreshing workspace" sx={{ position: "absolute", bottom: 0, left: 0, right: 0 }} /> : null}
      </Box>
      {health.dead_letter && scope ? (
        <Box sx={{ px: { xs: 2, md: 3, xl: 4 }, pt: 2 }}>
          <Banner severity="error">A scheduled briefing failed after retries. Open Pipelines to see the run, or use Refresh.</Banner>
        </Box>
      ) : null}
    </>
  );
}
