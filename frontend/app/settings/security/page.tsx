"use client";

import KeyRoundedIcon from "@mui/icons-material/KeyRounded";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState, type ElementType } from "react";
import { SettingsCard, SettingsPage } from "@/app/settings/shared";
import { Banner, EmptyState, LoadingBlock } from "@/app/ui";
import { absoluteTime, relativeTime } from "@/app/ui/platform";
import { apple } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { platform, type AuditEvent } from "@/lib/platform";

const ACTIONS: Record<string, string> = {
  "connection.saved": "Updated a connection",
  "connection.removed": "Disconnected",
  "connection.oauth": "Linked an account",
  "pipeline.updated": "Changed a pipeline",
  "repository.saved": "Saved a repository",
  "repository.removed": "Removed a repository",
  "profile.saved": "Edited the product profile",
  "brand.uploaded": "Uploaded a brand asset",
  "brand.removed": "Removed a brand asset",
  "person.added": "Added a person",
  "person.updated": "Edited a person",
  "person.archived": "Archived a person",
  "member.role": "Changed a role",
  "member.removed": "Removed a member",
  "member.invited": "Invited a member",
};

const FILTERS = [
  { id: "", label: "All" },
  { id: "connection", label: "Connections" },
  { id: "pipeline", label: "Pipelines" },
  { id: "repository", label: "Repositories" },
  { id: "member", label: "Access" },
  { id: "profile", label: "Profile & brand" },
  { id: "person", label: "People" },
];

function describe(event: AuditEvent): string {
  const detail = event.detail || {};
  const fields = Array.isArray(detail.fields) ? (detail.fields as string[]) : [];
  if (event.action === "member.role" && detail.role) return `→ ${String(detail.role)}`;
  if (event.action === "pipeline.updated") {
    const parts = Object.entries(detail).map(([key, value]) => (key === "settings" ? "settings" : `${key.replace(/_/g, " ")} ${typeof value === "boolean" ? (value ? "on" : "off") : String(value)}`));
    return parts.join(", ");
  }
  if (fields.length) return fields.map((f) => f.replace(/_/g, " ")).join(", ");
  return "";
}

function Fact({ Icon, title, body }: { Icon: ElementType; title: string; body: string }) {
  return (
    <Box sx={{ display: "flex", gap: 1.25, alignItems: "flex-start" }}>
      <Box sx={{ width: 32, height: 32, borderRadius: "9px", display: "grid", placeItems: "center", bgcolor: apple.hoverFill, flexShrink: 0 }}>
        <Icon sx={{ fontSize: 18, color: apple.muted }} />
      </Box>
      <Box>
        <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{title}</Typography>
        <Typography sx={{ fontSize: 12.5, color: apple.muted, lineHeight: 1.5, mt: 0.25 }}>{body}</Typography>
      </Box>
    </Box>
  );
}

export default function SecuritySettings() {
  const { me, can } = useWorkspace();
  const admin = can("admin");
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!admin) return;
    platform
      .audit(300)
      .then((data) => setEvents(data.events))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [admin]);

  const visible = useMemo(
    () => (events || []).filter((e) => !filter || e.action.startsWith(filter) || (filter === "profile" && e.action.startsWith("brand"))),
    [events, filter],
  );

  return (
    <SettingsPage subtitle="How this workspace protects credentials, and a record of who changed what.">
      <SettingsCard title="Credentials">
        <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0,1fr))" } }}>
          <Fact Icon={KeyRoundedIcon} title="A key per workspace" body="Secrets are encrypted with this workspace's own data key, which is itself encrypted by the server's master key." />
          <Fact Icon={VisibilityOffOutlinedIcon} title="Write-only in the browser" body="After saving, keys are never sent back. Connections show only that a value is set and its last few characters." />
          <Fact Icon={LockOutlinedIcon} title={me?.auth_mode === "clerk" ? "Clerk sign-in" : "Single-user mode"} body={me?.auth_mode === "clerk" ? "Every request carries a verified session, and each workspace only sees its own data." : "This server trusts whoever can reach it. Turn on Clerk before exposing it to the internet."} />
        </Box>
      </SettingsCard>

      <SettingsCard title="Activity" description={admin ? "Changes to connections, pipelines, repositories, the profile and access. Pipeline runs are in Run history." : undefined}>
        {!admin ? (
          <Typography sx={{ fontSize: 13.5, color: apple.muted }}>Only owners and admins can see workspace activity.</Typography>
        ) : (
          <>
            <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
              {FILTERS.map((item) => (
                <Chip key={item.id || "all"} label={item.label} onClick={() => setFilter(item.id)} variant={filter === item.id ? "filled" : "outlined"} color={filter === item.id ? "primary" : "default"} sx={{ borderRadius: "9px" }} />
              ))}
            </Box>
            {error ? <Banner severity="error">{error}</Banner> : null}
            {!events ? (
              <LoadingBlock rows={6} height={44} />
            ) : visible.length ? (
              <Box component="ol" sx={{ listStyle: "none", m: 0, p: 0, border: `1px solid ${apple.hairline}`, borderRadius: "12px", overflow: "hidden" }}>
                {visible.map((event, index) => {
                  const extra = describe(event);
                  return (
                    <Box component="li" key={event.id} sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "minmax(0,1fr) 140px" }, gap: { xs: 0.25, sm: 1.5 }, px: 1.75, py: 1.1, borderTop: index ? `1px solid ${apple.hairline}` : "none" }}>
                      <Box sx={{ minWidth: 0 }}>
                        <Typography sx={{ fontSize: 13.5 }}>
                          <Box component="span" sx={{ fontWeight: 600 }}>{event.actor || "System"}</Box> {(ACTIONS[event.action] || event.action).toLowerCase()}{" "}
                          <Box component="span" sx={{ fontFamily: "ui-monospace, Menlo, monospace", fontSize: 12.5 }}>{event.target}</Box>
                        </Typography>
                        {extra ? <Typography sx={{ fontSize: 12, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{extra}</Typography> : null}
                      </Box>
                      <Typography title={absoluteTime(event.at)} sx={{ fontSize: 12.5, color: apple.muted, textAlign: { sm: "right" } }}>
                        {relativeTime(event.at)}
                      </Typography>
                    </Box>
                  );
                })}
              </Box>
            ) : (
              <EmptyState>{events.length ? "Nothing in this category yet." : "No changes recorded yet."}</EmptyState>
            )}
          </>
        )}
      </SettingsCard>
    </SettingsPage>
  );
}
