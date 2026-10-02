"use client";

import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import BoltOutlinedIcon from "@mui/icons-material/BoltOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import ChatBubbleOutlineRoundedIcon from "@mui/icons-material/ChatBubbleOutlineRounded";
import CodeOutlinedIcon from "@mui/icons-material/CodeOutlined";
import ConfirmationNumberOutlinedIcon from "@mui/icons-material/ConfirmationNumberOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import ExploreOutlinedIcon from "@mui/icons-material/ExploreOutlined";
import Inventory2OutlinedIcon from "@mui/icons-material/Inventory2Outlined";
import MailOutlineRoundedIcon from "@mui/icons-material/MailOutlineRounded";
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import MenuBookOutlinedIcon from "@mui/icons-material/MenuBookOutlined";
import MovieCreationOutlinedIcon from "@mui/icons-material/MovieCreationOutlined";
import NewReleasesOutlinedIcon from "@mui/icons-material/NewReleasesOutlined";
import NotesOutlinedIcon from "@mui/icons-material/NotesOutlined";
import RadarOutlinedIcon from "@mui/icons-material/RadarOutlined";
import SummarizeOutlinedIcon from "@mui/icons-material/SummarizeOutlined";
import SyncRoundedIcon from "@mui/icons-material/SyncRounded";
import VideoCameraFrontOutlinedIcon from "@mui/icons-material/VideoCameraFrontOutlined";
import ViewQuiltOutlinedIcon from "@mui/icons-material/ViewQuiltOutlined";
import Box from "@mui/material/Box";
import Tooltip from "@mui/material/Tooltip";
import type { ElementType, ReactNode } from "react";
import { apple, categoryAccent, pmm } from "@/app/ui/tokens";
import type { Pipeline } from "@/lib/platform";

export const PIPELINE_ICONS: Record<string, ElementType> = {
  sync: SyncRoundedIcon,
  jira: ConfirmationNumberOutlinedIcon,
  chat: ChatBubbleOutlineRoundedIcon,
  briefing: SummarizeOutlinedIcon,
  roadmap: MapOutlinedIcon,
  code: CodeOutlinedIcon,
  release: NewReleasesOutlinedIcon,
  doc: DescriptionOutlinedIcon,
  prototype: ViewQuiltOutlinedIcon,
  copilot: AutoAwesomeOutlinedIcon,
  discover: ExploreOutlinedIcon,
  campaign: CampaignOutlinedIcon,
  film: MovieCreationOutlinedIcon,
  avatar: VideoCameraFrontOutlinedIcon,
  artifact: Inventory2OutlinedIcon,
  comms: MailOutlineRoundedIcon,
  radar: RadarOutlinedIcon,
  notes: NotesOutlinedIcon,
  library: MenuBookOutlinedIcon,
  bolt: BoltOutlinedIcon,
  pipeline: AccountTreeOutlinedIcon,
};

export const REQUIREMENT_LABELS: Record<string, string> = {
  jira: "Jira",
  cliq: "Zoho Cliq",
  llm: "AI models",
  repository: "a repository",
  google: "Google Drive",
  smtp: "Email",
  heygen: "HeyGen",
  cartesia: "Cartesia",
  elevenlabs: "ElevenLabs",
  bitbucket: "Bitbucket",
  github: "GitHub",
  gitlab: "GitLab",
};

export function requirementLabel(id: string) {
  return REQUIREMENT_LABELS[id] || id;
}

/** Where to fix a missing requirement. */
export function requirementHref(id: string) {
  return id === "repository" ? "/settings/repositories" : `/settings/connections?provider=${encodeURIComponent(id)}`;
}

export function PipelineIcon({ icon, category, size = 36 }: { icon: string; category: string; size?: number }) {
  const Icon = PIPELINE_ICONS[icon] || BoltOutlinedIcon;
  const tone = categoryAccent(category);
  return (
    <Box
      aria-hidden
      sx={{
        width: size,
        height: size,
        borderRadius: `${Math.round(size * 0.28)}px`,
        display: "grid",
        placeItems: "center",
        flexShrink: 0,
        bgcolor: tone.fill,
        color: tone.main,
      }}
    >
      <Icon sx={{ fontSize: Math.round(size * 0.55) }} />
    </Box>
  );
}

/** Backend timestamps are naive UTC. */
export function parseUtc(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const text = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`;
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function relativeTime(iso: string | null | undefined, now = Date.now()): string {
  const date = parseUtc(iso);
  if (!date) return "";
  const diff = Math.round((date.getTime() - now) / 1000);
  const abs = Math.abs(diff);
  const future = diff > 0;
  const fmt = (value: number, unit: string) => (future ? `in ${value}${unit}` : `${value}${unit} ago`);
  if (abs < 45) return future ? "in a moment" : "just now";
  if (abs < 3600) return fmt(Math.round(abs / 60), "m");
  if (abs < 86400) return fmt(Math.round(abs / 3600), "h");
  if (abs < 86400 * 7) return fmt(Math.round(abs / 86400), "d");
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function absoluteTime(iso: string | null | undefined): string {
  const date = parseUtc(iso);
  return date ? date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "";
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

export type Tone = { label: string; color: string; fill: string; live?: boolean };

export function runTone(status: string, category = "product"): Tone {
  const accent = categoryAccent(category);
  switch (status) {
    case "queued":
      return { label: "Queued", color: apple.muted, fill: apple.hoverFill, live: true };
    case "running":
      return { label: "Running", color: accent.main, fill: accent.fill, live: true };
    case "completed":
      return { label: "Completed", color: pmm.green, fill: pmm.greenFill };
    case "failed":
      return { label: "Failed", color: apple.danger, fill: apple.dangerFill };
    case "cancelled":
      return { label: "Cancelled", color: apple.muted, fill: apple.hoverFill };
    default:
      return { label: status ? status[0].toUpperCase() + status.slice(1) : "Unknown", color: apple.muted, fill: apple.hoverFill };
  }
}

export function pipelineTone(pipeline: Pick<Pipeline, "status" | "enabled" | "readiness" | "category" | "runnable">): Tone {
  if (!pipeline.enabled) return { label: "Off", color: apple.muted, fill: apple.hoverFill };
  if (pipeline.status === "needs_connection") {
    const first = pipeline.readiness.missing[0];
    return { label: first ? `Needs ${requirementLabel(first)}` : "Needs setup", color: pmm.amber, fill: pmm.amberFill };
  }
  if (pipeline.status === "connection_error") return { label: "Connection error", color: apple.danger, fill: apple.dangerFill };
  if (pipeline.status === "running" || pipeline.status === "queued") return runTone(pipeline.status, pipeline.category);
  return { label: pipeline.runnable ? "Ready" : "Interactive", color: pmm.green, fill: pmm.greenFill };
}

export function ToneChip({ tone, size = "md", title }: { tone: Tone; size?: "sm" | "md"; title?: string }) {
  const chip = (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 0.75,
        px: size === "sm" ? 0.9 : 1.1,
        py: size === "sm" ? 0.2 : 0.35,
        borderRadius: 999,
        bgcolor: tone.fill,
        color: tone.color,
        fontSize: size === "sm" ? 11.5 : 12.5,
        fontWeight: 600,
        whiteSpace: "nowrap",
        lineHeight: 1.5,
      }}
    >
      <Box component="span" className={tone.live ? "live-dot" : undefined} sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: tone.color, flexShrink: 0 }} />
      {tone.label}
    </Box>
  );
  return title ? <Tooltip title={title}>{chip}</Tooltip> : chip;
}

export function StatTile({ label, value, hint, accent, children }: { label: string; value: ReactNode; hint?: ReactNode; accent?: string; children?: ReactNode }) {
  return (
    <Box
      sx={{
        position: "relative",
        p: 2.25,
        borderRadius: "14px",
        border: `1px solid ${apple.hairline}`,
        bgcolor: apple.raised,
        overflow: "hidden",
        minWidth: 0,
      }}
    >
      {accent ? <Box aria-hidden sx={{ position: "absolute", inset: "0 auto 0 0", width: 3, bgcolor: accent }} /> : null}
      <Box sx={{ fontSize: 12, fontWeight: 600, color: apple.muted, letterSpacing: "0.02em" }}>{label}</Box>
      <Box sx={{ mt: 0.75, fontSize: 26, fontWeight: 650, letterSpacing: "-0.03em", fontVariantNumeric: "tabular-nums", color: apple.text, lineHeight: 1.1 }}>{value}</Box>
      {hint ? <Box sx={{ mt: 0.75, fontSize: 12.5, color: apple.muted, minHeight: 18 }}>{hint}</Box> : null}
      {children}
    </Box>
  );
}

export const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function clockLabel(hour: number, minute: number) {
  return new Date(2000, 0, 1, hour, minute).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/** Plain-English reading of the 5-field cron shapes the schedule editor writes; anything else is shown as-is. */
export function describeSchedule(expr: string): string {
  const parts = expr.trim().split(/\s+/);
  if (!expr.trim()) return "No schedule";
  if (parts.length !== 5) return expr;
  const [m, h, dom, mon, dow] = parts;
  const num = (value: string) => (/^\d+$/.test(value) ? Number(value) : null);
  const minute = num(m);
  const hour = num(h);
  if (dom !== "*" || mon !== "*") return expr;
  if (minute !== null && hour !== null) {
    const at = clockLabel(hour, minute);
    if (dow === "*") return `Every day at ${at}`;
    if (dow === "1-5") return `Weekdays at ${at}`;
    if (dow === "0,6" || dow === "6,0") return `Weekends at ${at}`;
    const day = num(dow);
    if (day !== null && day <= 7) return `Every ${WEEKDAYS[day % 7]} at ${at}`;
    if (/^[0-7](,[0-7])+$/.test(dow)) return `${dow.split(",").map((d) => WEEKDAYS[Number(d) % 7].slice(0, 3)).join(", ")} at ${at}`;
  }
  if (dow !== "*") return expr;
  if (minute !== null && h === "*") return minute === 0 ? "Every hour" : `Every hour at :${String(minute).padStart(2, "0")}`;
  const everyHours = /^\*\/(\d+)$/.exec(h);
  if (minute !== null && everyHours) return `Every ${everyHours[1]} hours`;
  const everyMinutes = /^\*\/(\d+)$/.exec(m);
  if (everyMinutes && h === "*") return `Every ${everyMinutes[1]} minutes`;
  return expr;
}

/** Step names written by refresh pipelines, in the order they run. */
export const STEP_LABELS: Record<string, string> = {
  jira: "Jira",
  cliq: "Cliq",
  roadmap: "Roadmap",
  codebase: "Codebase",
  branches: "Branches",
  releases: "Releases",
  competitors: "Market watch",
  marketing: "Feature discovery",
  briefing: "Briefing",
  fetch: "Fetch",
  index: "Index",
  "source-index": "Source index",
  detect: "Detect",
};

export function stepTone(step: { status?: string; ok?: boolean } | undefined): Tone {
  if (!step) return { label: "Pending", color: apple.muted, fill: apple.hoverFill };
  if (step.status === "running") return { label: "Running", color: apple.text, fill: apple.hoverFill, live: true };
  if (step.ok === false || step.status === "failed") return { label: "Failed", color: apple.danger, fill: apple.dangerFill };
  if (step.status === "skipped") return { label: "Skipped", color: apple.muted, fill: apple.hoverFill };
  if (step.ok || step.status === "completed" || step.status === "ok") return { label: "Done", color: pmm.green, fill: pmm.greenFill };
  return { label: step.status || "Pending", color: apple.muted, fill: apple.hoverFill };
}
