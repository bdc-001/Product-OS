"use client";

import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Banner, PillButton } from "@/app/ui";
import { apple } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { platform, type Profile, type WorkspaceDetail } from "@/lib/platform";

export function SettingsCard({ title, description, children, footer, tone }: { title: string; description?: ReactNode; children?: ReactNode; footer?: ReactNode; tone?: "danger" }) {
  return (
    <Box component="section" sx={{ borderRadius: "16px", border: `1px solid ${tone === "danger" ? apple.dangerLine : apple.hairline}`, bgcolor: apple.raised, overflow: "hidden", minWidth: 0 }}>
      <Box sx={{ p: { xs: 2, md: 2.5 }, display: "grid", gap: 2 }}>
        <Box>
          <Typography component="h2" sx={{ fontSize: 15.5, fontWeight: 650, letterSpacing: "-0.01em", color: tone === "danger" ? apple.danger : apple.text }}>
            {title}
          </Typography>
          {description ? <Typography sx={{ mt: 0.5, fontSize: 13, color: apple.muted, lineHeight: 1.55, maxWidth: 680 }}>{description}</Typography> : null}
        </Box>
        {children}
      </Box>
      {footer ? <Box sx={{ px: { xs: 2, md: 2.5 }, py: 1.5, borderTop: `1px solid ${apple.hairline}`, bgcolor: apple.hoverFill, display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>{footer}</Box> : null}
    </Box>
  );
}

export function SettingsPage({ subtitle, children }: { subtitle?: string; children: ReactNode }) {
  return (
    <Box sx={{ px: { xs: 2, md: 3, xl: 4 }, py: { xs: 2.5, md: 3 }, maxWidth: 920, minWidth: 0 }}>
      {subtitle ? <Typography sx={{ mb: 2.5, fontSize: 14, color: apple.muted, lineHeight: 1.55, maxWidth: 680 }}>{subtitle}</Typography> : null}
      <Box sx={{ display: "grid", gap: 2.5 }}>{children}</Box>
    </Box>
  );
}

export function AdminNotice() {
  const { can, me } = useWorkspace();
  if (!me || can("admin")) return null;
  return <Banner severity="info">You are a member of this workspace. Only owners and admins can change these settings.</Banner>;
}

/** Load the workspace once, edit a local draft of the fields a page owns, and save just those. */
export function useProfileDraft<K extends keyof Profile>(keys: readonly K[], extra: { name?: boolean; timezone?: boolean } = {}) {
  const { reload } = useWorkspace();
  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [draft, setDraft] = useState<Pick<Profile, K> & { name?: string; timezone?: string }>({} as Pick<Profile, K>);
  const [status, setStatus] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const apply = useCallback(
    (next: WorkspaceDetail) => {
      setDetail(next);
      const values = Object.fromEntries(keys.map((key) => [key, next.profile[key]])) as Pick<Profile, K>;
      setDraft({ ...values, ...(extra.name ? { name: next.name } : {}), ...(extra.timezone ? { timezone: next.timezone } : {}) });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [keys.join(","), extra.name, extra.timezone],
  );

  useEffect(() => {
    platform
      .workspace()
      .then(apply)
      .catch((err) => setStatus({ tone: "error", message: err instanceof Error ? err.message : String(err) }));
  }, [apply]);

  const dirty = Boolean(
    detail &&
      (keys.some((key) => JSON.stringify(draft[key]) !== JSON.stringify(detail.profile[key])) ||
        (extra.name && draft.name !== detail.name) ||
        (extra.timezone && draft.timezone !== detail.timezone)),
  );

  async function save(message = "Saved.") {
    setBusy(true);
    setStatus(null);
    try {
      const profile = Object.fromEntries(keys.map((key) => [key, draft[key]])) as Partial<Profile>;
      const next = await platform.saveWorkspace({ profile, ...(extra.name ? { name: draft.name } : {}), ...(extra.timezone ? { timezone: draft.timezone } : {}) });
      apply(next);
      setStatus({ tone: "success", message });
      if (extra.name || extra.timezone) void reload();
    } catch (err) {
      setStatus({ tone: "error", message: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  }

  const set = (patch: Partial<Pick<Profile, K> & { name: string; timezone: string }>) => {
    setStatus(null);
    setDraft((current) => ({ ...current, ...patch }));
  };

  const reset = () => detail && apply(detail);

  return { detail, draft, set, save, reset, dirty, busy, status };
}

export function SaveFooter({ dirty, busy, canEdit, onSave, onReset, status, label = "Save changes" }: { dirty: boolean; busy: boolean; canEdit: boolean; onSave: () => void; onReset: () => void; status: { tone: "success" | "error"; message: string } | null; label?: string }) {
  if (!canEdit) return null;
  return (
    <>
      <PillButton size="small" disabled={!dirty || busy} onClick={onSave}>
        {busy ? "Saving…" : label}
      </PillButton>
      {dirty && !busy ? (
        <PillButton size="small" variant="text" onClick={onReset} sx={{ color: apple.muted }}>
          Discard
        </PillButton>
      ) : null}
      {status ? <Typography sx={{ fontSize: 13, color: status.tone === "error" ? apple.danger : apple.muted }}>{status.message}</Typography> : null}
    </>
  );
}
