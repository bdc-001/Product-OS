"use client";

import Box from "@mui/material/Box";
import FormControlLabel from "@mui/material/FormControlLabel";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useMemo, useState } from "react";
import { Banner, PillButton } from "@/app/ui";
import { WEEKDAYS, describeSchedule, relativeTime } from "@/app/ui/platform";
import { apple } from "@/app/ui/tokens";
import { platform, type Pipeline } from "@/lib/platform";

type Mode = "daily" | "weekdays" | "weekly" | "hourly" | "custom";
type Draft = { mode: Mode; time: string; day: number; minute: number; cron: string };

const MODES: { id: Mode; label: string }[] = [
  { id: "daily", label: "Every day" },
  { id: "weekdays", label: "Weekdays" },
  { id: "weekly", label: "Once a week" },
  { id: "hourly", label: "Every hour" },
  { id: "custom", label: "Custom (cron)" },
];

const pad = (n: number) => String(n).padStart(2, "0");

function parse(expr: string): Draft {
  const base: Draft = { mode: "daily", time: "08:00", day: 1, minute: 0, cron: expr };
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return expr.trim() ? { ...base, mode: "custom" } : base;
  const [m, h, dom, mon, dow] = parts;
  const isNum = (v: string) => /^\d+$/.test(v);
  if (dom !== "*" || mon !== "*") return { ...base, mode: "custom" };
  if (isNum(m) && isNum(h)) {
    const time = `${pad(Number(h))}:${pad(Number(m))}`;
    if (dow === "*") return { ...base, mode: "daily", time };
    if (dow === "1-5") return { ...base, mode: "weekdays", time };
    if (isNum(dow) && Number(dow) <= 7) return { ...base, mode: "weekly", time, day: Number(dow) % 7 };
  }
  if (isNum(m) && h === "*" && dow === "*") return { ...base, mode: "hourly", minute: Number(m) };
  return { ...base, mode: "custom" };
}

function build(draft: Draft): string {
  const [h, m] = (draft.time || "08:00").split(":").map((v) => Number(v) || 0);
  switch (draft.mode) {
    case "daily":
      return `${m} ${h} * * *`;
    case "weekdays":
      return `${m} ${h} * * 1-5`;
    case "weekly":
      return `${m} ${h} * * ${draft.day}`;
    case "hourly":
      return `${draft.minute} * * * *`;
    default:
      return draft.cron.trim();
  }
}

export function ScheduleEditor({ pipeline, timezone, canEdit, onSaved }: { pipeline: Pipeline; timezone: string; canEdit: boolean; onSaved: (next: Pipeline) => void }) {
  const [enabled, setEnabled] = useState(pipeline.schedule_enabled);
  const [draft, setDraft] = useState<Draft>(() => parse(pipeline.schedule || pipeline.default_schedule || "0 8 * * *"));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const cron = build(draft);
  const dirty = enabled !== pipeline.schedule_enabled || cron !== (pipeline.schedule || "");
  const set = (patch: Partial<Draft>) => setDraft((current) => ({ ...current, ...patch, cron: patch.mode === "custom" && current.mode !== "custom" ? build(current) : patch.cron ?? current.cron }));

  async function save() {
    setBusy(true);
    setError("");
    try {
      onSaved(await platform.updatePipeline(pipeline.id, { schedule: cron, schedule_enabled: enabled }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box sx={{ display: "grid", gap: 1.75 }}>
      <FormControlLabel
        control={<Switch checked={enabled} onChange={(event) => setEnabled(event.target.checked)} disabled={!canEdit || !pipeline.enabled} />}
        label={<Typography sx={{ fontSize: 14, fontWeight: 600 }}>Run on a schedule</Typography>}
        sx={{ m: 0, justifyContent: "space-between", flexDirection: "row-reverse" }}
      />
      <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: draft.mode === "custom" ? "1fr" : "1fr 1fr", opacity: enabled ? 1 : 0.6 }}>
        <TextField select size="small" label="Repeat" value={draft.mode} onChange={(event) => set({ mode: event.target.value as Mode })} disabled={!canEdit}>
          {MODES.map((mode) => (
            <MenuItem key={mode.id} value={mode.id}>
              {mode.label}
            </MenuItem>
          ))}
        </TextField>
        {draft.mode === "hourly" ? (
          <TextField select size="small" label="At minute" value={draft.minute} onChange={(event) => set({ minute: Number(event.target.value) })} disabled={!canEdit}>
            {[0, 5, 10, 15, 20, 30, 45].map((m) => (
              <MenuItem key={m} value={m}>
                :{pad(m)}
              </MenuItem>
            ))}
          </TextField>
        ) : draft.mode === "custom" ? (
          <TextField size="small" label="Cron expression" value={draft.cron} onChange={(event) => set({ cron: event.target.value })} disabled={!canEdit} helperText="Five fields: minute hour day month weekday. E.g. 30 7 * * 1-5" slotProps={{ htmlInput: { spellCheck: false, style: { fontFamily: "ui-monospace, Menlo, monospace" } } }} />
        ) : (
          <TextField size="small" type="time" label="At" value={draft.time} onChange={(event) => set({ time: event.target.value })} disabled={!canEdit} slotProps={{ inputLabel: { shrink: true } }} />
        )}
        {draft.mode === "weekly" ? (
          <TextField select size="small" label="On" value={draft.day} onChange={(event) => set({ day: Number(event.target.value) })} disabled={!canEdit} sx={{ gridColumn: "1 / -1" }}>
            {WEEKDAYS.map((name, index) => (
              <MenuItem key={name} value={index}>
                {name}
              </MenuItem>
            ))}
          </TextField>
        ) : null}
      </Box>
      <Typography sx={{ fontSize: 12.5, color: apple.muted, lineHeight: 1.5 }}>
        {describeSchedule(cron)} · {timezone}
        {pipeline.schedule_enabled && pipeline.next_run_at && !dirty ? ` · next run ${relativeTime(pipeline.next_run_at)}` : ""}
        {pipeline.default_schedule && cron !== pipeline.default_schedule && canEdit ? (
          <>
            {" · "}
            <Link component="button" type="button" onClick={() => setDraft(parse(pipeline.default_schedule))} sx={{ fontSize: "inherit", verticalAlign: "baseline" }}>
              Use default ({describeSchedule(pipeline.default_schedule)})
            </Link>
          </>
        ) : null}
      </Typography>
      {!pipeline.enabled ? <Typography sx={{ fontSize: 12.5, color: apple.muted }}>Turn the pipeline on to schedule it.</Typography> : null}
      {error ? <Banner severity="error">{error}</Banner> : null}
      {canEdit ? (
        <Box>
          <PillButton size="small" disabled={!dirty || busy || !cron} onClick={() => void save()}>
            {busy ? "Saving…" : "Save schedule"}
          </PillButton>
        </Box>
      ) : null}
    </Box>
  );
}

export function SettingsEditor({ pipeline, canEdit, onSaved }: { pipeline: Pipeline; canEdit: boolean; onSaved: (next: Pipeline) => void }) {
  const [values, setValues] = useState<Record<string, unknown>>(() => ({ ...pipeline.settings }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty = useMemo(() => pipeline.settings_schema.some((field) => values[field.key] !== pipeline.settings[field.key]), [values, pipeline]);

  async function save() {
    setBusy(true);
    setError("");
    try {
      onSaved(await platform.updatePipeline(pipeline.id, { settings: values }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box sx={{ display: "grid", gap: 1.5 }}>
      {pipeline.settings_schema.map((field) => {
        const value = values[field.key] ?? field.default;
        const update = (next: unknown) => setValues((current) => ({ ...current, [field.key]: next }));
        if (field.kind === "bool") {
          return (
            <Box key={field.key}>
              <FormControlLabel
                control={<Switch checked={Boolean(value)} onChange={(event) => update(event.target.checked)} disabled={!canEdit} />}
                label={<Typography sx={{ fontSize: 14 }}>{field.label}</Typography>}
                sx={{ m: 0, justifyContent: "space-between", flexDirection: "row-reverse", width: "100%" }}
              />
              {field.help ? <Typography sx={{ fontSize: 12, color: apple.muted, mt: -0.25 }}>{field.help}</Typography> : null}
            </Box>
          );
        }
        if (field.kind === "select") {
          return (
            <TextField key={field.key} select size="small" label={field.label} value={String(value ?? "")} onChange={(event) => update(event.target.value)} disabled={!canEdit} helperText={field.help || undefined}>
              {field.options.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </TextField>
          );
        }
        return (
          <TextField
            key={field.key}
            size="small"
            label={field.label}
            type={field.kind === "number" ? "number" : "text"}
            multiline={field.kind === "textarea"}
            minRows={field.kind === "textarea" ? 3 : undefined}
            value={String(value ?? "")}
            onChange={(event) => update(field.kind === "number" ? Number(event.target.value) : event.target.value)}
            disabled={!canEdit}
            helperText={field.help || undefined}
          />
        );
      })}
      {error ? <Banner severity="error">{error}</Banner> : null}
      {canEdit ? (
        <Box>
          <PillButton size="small" disabled={!dirty || busy} onClick={() => void save()}>
            {busy ? "Saving…" : "Save settings"}
          </PillButton>
        </Box>
      ) : null}
    </Box>
  );
}
