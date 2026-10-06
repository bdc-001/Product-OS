"use client";

import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMemo } from "react";
import { AdminNotice, SaveFooter, SettingsCard, SettingsPage, useProfileDraft } from "@/app/settings/shared";
import { LoadingBlock, PillButton } from "@/app/ui";
import { apple, pmm } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { AppearanceToggle, WorkspaceMark } from "@/app/workspace-switcher";

const NO_KEYS = [] as const;
const OWNER_KEYS = ["pm_display_name", "pm_cliq_user_id", "pm_cliq_mentions", "pm_personas"] as const;
const FALLBACK_ZONES = ["UTC", "Asia/Kolkata", "Asia/Singapore", "Asia/Dubai", "Europe/London", "Europe/Berlin", "America/New_York", "America/Chicago", "America/Los_Angeles", "Australia/Sydney"];

function timezones(): string[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  try {
    return intl.supportedValuesOf?.("timeZone") || FALLBACK_ZONES;
  } catch {
    return FALLBACK_ZONES;
  }
}

function WorkspaceCard({ canEdit }: { canEdit: boolean }) {
  const form = useProfileDraft(NO_KEYS, { name: true, timezone: true });
  const zones = useMemo(timezones, []);
  if (!form.detail) return <LoadingBlock rows={2} height={56} />;
  return (
    <SettingsCard
      title="Workspace"
      description="Schedules, briefing windows and timestamps all use this timezone."
      footer={<SaveFooter canEdit={canEdit} dirty={form.dirty} busy={form.busy} status={form.status} onSave={() => void form.save("Workspace saved.")} onReset={form.reset} />}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
        <WorkspaceMark name={form.draft.name || form.detail.name} slug={form.detail.slug} size={44} />
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 650 }}>{form.draft.name || form.detail.name}</Typography>
          <Typography sx={{ fontSize: 12.5, color: apple.muted }}>
            {form.detail.slug} · {form.detail.kind === "organization" ? "Organization" : "Personal"} workspace
          </Typography>
        </Box>
      </Box>
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
        <TextField size="small" label="Workspace name" value={form.draft.name || ""} onChange={(event) => form.set({ name: event.target.value })} disabled={!canEdit} />
        <Autocomplete
      size="small"
          options={zones}
          value={form.draft.timezone || null}
          onChange={(_, value) => value && form.set({ timezone: value })}
          disabled={!canEdit}
          renderInput={(params) => <TextField {...params} label="Timezone" />}
        />
      </Box>
    </SettingsCard>
  );
}

function OwnerCard({ canEdit }: { canEdit: boolean }) {
  const form = useProfileDraft(OWNER_KEYS);
  if (!form.detail) return null;
  return (
    <SettingsCard
      title="Briefing owner"
      description="The product manager briefings are written for. Mentions of these names and IDs in chat count as asks for them."
      footer={<SaveFooter canEdit={canEdit} dirty={form.dirty} busy={form.busy} status={form.status} onSave={() => void form.save("Briefing owner saved.")} onReset={form.reset} />}
    >
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
        <TextField size="small" label="Name in briefings" value={form.draft.pm_display_name || ""} onChange={(event) => form.set({ pm_display_name: event.target.value })} disabled={!canEdit} placeholder="Priya" />
        <TextField size="small" label="Cliq user ID" value={form.draft.pm_cliq_user_id || ""} onChange={(event) => form.set({ pm_cliq_user_id: event.target.value })} disabled={!canEdit} helperText="Used to spot when someone tags them." />
        <TextField size="small" label="Other names to match" value={form.draft.pm_cliq_mentions || ""} onChange={(event) => form.set({ pm_cliq_mentions: event.target.value })} disabled={!canEdit} helperText="Comma-separated nicknames or handles." />
        <TextField size="small" label="Personas" value={form.draft.pm_personas || ""} onChange={(event) => form.set({ pm_personas: event.target.value })} disabled={!canEdit} helperText="Roles they cover, e.g. PM, product support." />
      </Box>
    </SettingsCard>
  );
}

function SetupCard() {
  const form = useProfileDraft(NO_KEYS);
  if (!form.detail) return null;
  const steps = form.detail.onboarding.steps;
  const done = steps.filter((s) => s.done).length;
  return (
    <SettingsCard
      title="Setup"
      description={done === steps.length ? "Every setup step is complete." : `${done} of ${steps.length} setup steps done. The rest unlock more pipelines.`}
      footer={
        <PillButton size="small" variant="gray" href="/onboarding" endIcon={<ArrowForwardRoundedIcon />}>
          {done === steps.length ? "Review setup" : "Continue setup"}
                    </PillButton>
      }
    >
      <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
        {steps.map((step) => (
          <Box key={step.id} sx={{ display: "flex", alignItems: "center", gap: 1.25 }}>
            <Box sx={{ width: 20, height: 20, borderRadius: "50%", display: "grid", placeItems: "center", bgcolor: step.done ? pmm.green : "transparent", border: step.done ? "none" : `1.5px solid ${apple.hairline}` }}>
              {step.done ? <CheckRoundedIcon sx={{ fontSize: 14, color: "#fff" }} /> : null}
            </Box>
            <Typography sx={{ fontSize: 14, color: step.done ? apple.text : apple.muted }}>{step.label}</Typography>
          </Box>
        ))}
      </Box>
    </SettingsCard>
  );
}

export default function GeneralSettings() {
  const { can } = useWorkspace();
  const canEdit = can("admin");
  return (
    <SettingsPage subtitle="Workspace basics, who briefings are for, and how the app looks on this device.">
      <AdminNotice />
      <WorkspaceCard canEdit={canEdit} />
      <SettingsCard title="Appearance" description="Saved on this device. Match system follows your OS light or dark setting.">
        <Box>
          <AppearanceToggle />
        </Box>
      </SettingsCard>
      <OwnerCard canEdit={canEdit} />
      <SetupCard />
    </SettingsPage>
  );
}
