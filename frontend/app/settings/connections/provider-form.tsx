"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import ContentCopyRoundedIcon from "@mui/icons-material/ContentCopyRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import Box from "@mui/material/Box";
import Collapse from "@mui/material/Collapse";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useMemo, useState } from "react";
import { Banner, PillButton } from "@/app/ui";
import { ToneChip, absoluteTime, relativeTime } from "@/app/ui/platform";
import { apple, pmm } from "@/app/ui/tokens";
import { platform, type ConnectionView, type Provider, type ProviderField, type TestOutcome } from "@/lib/platform";

/** Brand tint for the provider mark. Brand colours are identity, not theme. */
export const PROVIDER_BRANDS: Record<string, { bg: string; mark: string }> = {
  jira: { bg: "linear-gradient(135deg,#2684ff,#0052cc)", mark: "J" },
  cliq: { bg: "linear-gradient(135deg,#0fb57e,#08805a)", mark: "C" },
  llm: { bg: "linear-gradient(135deg,#8b5cf6,#4f46e5)", mark: "AI" },
  google: { bg: "linear-gradient(135deg,#34a853,#4285f4)", mark: "G" },
  smtp: { bg: "linear-gradient(135deg,#64748b,#334155)", mark: "@" },
  cartesia: { bg: "linear-gradient(135deg,#f97316,#c2410c)", mark: "Ca" },
  heygen: { bg: "linear-gradient(135deg,#7c5cff,#3b2bb5)", mark: "H" },
  elevenlabs: { bg: "linear-gradient(135deg,#3f3f46,#09090b)", mark: "11" },
  bitbucket: { bg: "linear-gradient(135deg,#2684ff,#0747a6)", mark: "Bb" },
  github: { bg: "linear-gradient(135deg,#4b5563,#111827)", mark: "GH" },
  gitlab: { bg: "linear-gradient(135deg,#fc6d26,#e24329)", mark: "GL" },
};

export function ProviderMark({ id, name, size = 40 }: { id: string; name: string; size?: number }) {
  const brand = PROVIDER_BRANDS[id] || { bg: "linear-gradient(135deg,#94a3b8,#475569)", mark: name.slice(0, 2) };
  return (
    <Box
      aria-hidden
      sx={{
        width: size,
        height: size,
        borderRadius: `${Math.round(size * 0.28)}px`,
        background: brand.bg,
        color: "#fff",
        display: "grid",
        placeItems: "center",
        fontSize: Math.round(size * (brand.mark.length > 1 ? 0.34 : 0.44)),
        fontWeight: 700,
        letterSpacing: "-0.02em",
        flexShrink: 0,
        boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.16)",
      }}
    >
      {brand.mark}
    </Box>
  );
}

export function connectionTone(view: ConnectionView | undefined) {
  const status = view?.connected ? view.status : "disconnected";
  switch (status) {
    case "connected":
      return { label: "Connected", color: pmm.green, fill: pmm.greenFill };
    case "error":
      return { label: "Needs attention", color: apple.danger, fill: apple.dangerFill };
    case "untested":
      return { label: "Saved, not verified", color: pmm.amber, fill: pmm.amberFill };
    case "incomplete":
      return { label: "Incomplete", color: pmm.amber, fill: pmm.amberFill };
    default:
      return { label: "Not connected", color: apple.muted, fill: apple.hoverFill };
  }
}

type SecretState = { set: boolean; hint: string };

function secretState(view: ConnectionView | undefined, key: string): SecretState {
  const raw = (view?.secrets as Record<string, SecretState> | undefined)?.[key];
  return raw && typeof raw === "object" && "set" in raw ? raw : { set: false, hint: "" };
}

function initialValue(field: ProviderField, view: ConnectionView | undefined): unknown {
  if (field.secret) return "";
  const saved = view?.config?.[field.key];
  if (saved !== undefined && saved !== null && saved !== "") return saved;
  return field.default ?? (field.kind === "bool" ? false : "");
}

function FieldInput({ field, value, onChange, secret, onClear, disabled }: { field: ProviderField; value: unknown; onChange: (value: unknown) => void; secret?: SecretState; onClear?: () => void; disabled?: boolean }) {
  const help = field.help || undefined;
  if (field.kind === "bool") {
    return (
      <Box>
        <FormControlLabel control={<Switch checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} disabled={disabled} />} label={<Typography sx={{ fontSize: 14 }}>{field.label}</Typography>} />
        {help ? <Typography sx={{ fontSize: 12, color: apple.muted, ml: 6, mt: -0.5 }}>{help}</Typography> : null}
      </Box>
    );
  }
  if (field.kind === "select") {
    return (
      <TextField select size="small" fullWidth label={field.label} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} helperText={help} disabled={disabled} required={field.required}>
        {field.options.map((option) => (
          <MenuItem key={option} value={option}>
            {option === "ssh_key" ? "SSH deploy key" : option === "token" ? "Access token" : option}
          </MenuItem>
        ))}
      </TextField>
    );
  }
  if (field.secret) {
    const multiline = field.kind === "json" || field.kind === "textarea";
    const saved = secret?.set;
    return (
      <Box sx={{ position: "relative" }}>
        <TextField
          size="small"
          fullWidth
          label={field.label}
          type={multiline ? "text" : "password"}
          multiline={multiline}
          minRows={multiline ? 4 : undefined}
          maxRows={multiline ? 10 : undefined}
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
          placeholder={saved ? `Saved ${secret?.hint ? `· ${secret.hint}` : ""} — paste to replace` : field.placeholder}
          helperText={help}
          disabled={disabled}
          required={field.required && !saved}
          autoComplete="new-password"
          slotProps={{ htmlInput: { spellCheck: false, style: multiline ? { fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 12 } : undefined } }}
        />
        {saved && onClear ? (
          <Tooltip title="Remove saved value">
            <IconButton size="small" onClick={onClear} disabled={disabled} aria-label={`Remove saved ${field.label}`} sx={{ position: "absolute", right: 6, top: 6 }}>
              <DeleteOutlineRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : null}
      </Box>
    );
  }
  return (
    <TextField
      size="small"
      fullWidth
      label={field.label}
      type={field.kind === "number" ? "number" : field.kind === "email" ? "email" : field.kind === "url" ? "url" : "text"}
      multiline={field.kind === "textarea"}
      minRows={field.kind === "textarea" ? 3 : undefined}
      value={String(value ?? "")}
      onChange={(event) => onChange(field.kind === "number" ? (event.target.value === "" ? "" : Number(event.target.value)) : event.target.value)}
      placeholder={field.placeholder}
      helperText={help}
      disabled={disabled}
      required={field.required}
    />
  );
}

function visibleFor(field: ProviderField, values: Record<string, unknown>) {
  if (field.key === "access_token" || field.key === "username") return String(values.auth_type || "token") !== "ssh_key";
  if (field.key === "ssh_private_key") return String(values.auth_type || "token") === "ssh_key";
  return true;
}

export function TestResult({ outcome }: { outcome: TestOutcome | null }) {
  if (!outcome) return null;
  return <Banner severity={outcome.ok ? "success" : "error"}>{outcome.message}</Banner>;
}

/** The generic credential form every provider without a custom UI uses. */
export function ProviderForm({
  provider,
  view,
  canEdit,
  name = "default",
  onSaved,
  compact,
}: {
  provider: Provider;
  view?: ConnectionView;
  canEdit: boolean;
  name?: string;
  onSaved?: (view: ConnectionView, test: TestOutcome | null) => void;
  compact?: boolean;
}) {
  const [values, setValues] = useState<Record<string, unknown>>(() => Object.fromEntries(provider.fields.map((field) => [field.key, initialValue(field, view)])));
  const [clear, setClear] = useState<string[]>([]);
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [outcome, setOutcome] = useState<TestOutcome | null>(null);
  const basic = provider.fields.filter((field) => !field.advanced && visibleFor(field, values));
  const extra = provider.fields.filter((field) => field.advanced && visibleFor(field, values));

  const changed = useMemo(() => {
    const out: Record<string, unknown> = {};
    for (const field of provider.fields) {
      const value = values[field.key];
      if (field.secret) {
        if (typeof value === "string" && value.trim()) out[field.key] = value.trim();
      } else if (value !== initialValue(field, view) || !view?.connected) {
        out[field.key] = value;
      }
    }
    return out;
  }, [values, provider.fields, view]);

  const missing = provider.fields.filter((field) => field.required && visibleFor(field, values) && !(field.secret ? secretState(view, field.key).set && !clear.includes(field.key) : false) && !String(values[field.key] ?? "").trim());

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setOutcome(null);
    try {
      const result = await platform.saveConnection(provider.id, changed, { clear, name });
      setOutcome(result.test);
      setClear([]);
      setValues((previous) => Object.fromEntries(provider.fields.map((field) => [field.key, field.secret ? "" : previous[field.key]])));
      onSaved?.(result.connection, result.test);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const render = (field: ProviderField) => (
    <FieldInput
      key={field.key}
      field={field}
      value={values[field.key]}
      secret={clear.includes(field.key) ? { set: false, hint: "" } : secretState(view, field.key)}
      disabled={!canEdit || busy}
      onChange={(value) => setValues((previous) => ({ ...previous, [field.key]: value }))}
      onClear={() => setClear((previous) => [...previous, field.key])}
    />
  );

  return (
    <Box component="form" onSubmit={save} sx={{ display: "grid", gap: compact ? 1.75 : 2 }}>
      {basic.map(render)}
      {extra.length ? (
        <Box>
          <Link component="button" type="button" underline="none" onClick={() => setAdvanced((value) => !value)} sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, fontSize: 13, color: apple.muted, fontWeight: 500 }}>
            <ExpandMoreRoundedIcon sx={{ fontSize: 18, transform: advanced ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
            {advanced ? "Hide advanced" : `Advanced (${extra.length})`}
          </Link>
          <Collapse in={advanced} unmountOnExit>
            <Box sx={{ display: "grid", gap: 2, mt: 2 }}>{extra.map(render)}</Box>
          </Collapse>
        </Box>
      ) : null}
      {error ? <Banner severity="error">{error}</Banner> : null}
      <TestResult outcome={outcome} />
      {canEdit ? (
        <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
          <PillButton type="submit" disabled={busy || (!Object.keys(changed).length && !clear.length) || missing.length > 0} title={missing.length ? `Fill in ${missing.map((f) => f.label).join(", ")}` : undefined}>
            {busy ? "Saving and testing…" : view?.connected ? "Save and test" : "Connect"}
          </PillButton>
          {missing.length && !busy ? <Typography sx={{ fontSize: 12, color: apple.muted }}>Needs {missing.map((f) => f.label).join(", ")}</Typography> : null}
        </Box>
      ) : (
        <Typography sx={{ fontSize: 13, color: apple.muted }}>Only workspace admins can change connections.</Typography>
      )}
    </Box>
  );
}

type LlmProvider = { id: string; label: string; protocol: string; base_url: string; project: string; api_key: string; hint: string; clear_api_key?: boolean };
const ROUTES: { key: string; label: string; help: string }[] = [
  { key: "default", label: "Default", help: "Briefings, summaries and anything without its own route." },
  { key: "copilot", label: "Copilot", help: "Plans Jira changes; benefits from a strong reasoning model." },
  { key: "prototype", label: "Prototypes", help: "Writes React code; use a strong coding model." },
  { key: "docs", label: "Docs and PRDs", help: "Long-form writing." },
  { key: "marketing", label: "Marketing", help: "Campaigns, scripts and films." },
];
const PRESETS: Record<string, { label: string; protocol: string; base_url: string }> = {
  openai: { label: "OpenAI", protocol: "openai", base_url: "https://api.openai.com/v1" },
  anthropic: { label: "Anthropic", protocol: "anthropic", base_url: "https://api.anthropic.com/v1" },
  openrouter: { label: "OpenRouter", protocol: "openai", base_url: "https://openrouter.ai/api/v1" },
  custom: { label: "Custom (OpenAI-compatible)", protocol: "openai", base_url: "" },
};

/** Model providers plus per-task routing. */
export function LlmForm({ view, canEdit, onSaved }: { view?: ConnectionView; canEdit: boolean; onSaved?: (view: ConnectionView, test: TestOutcome | null) => void }) {
  const config = (view?.config || {}) as { providers?: Record<string, { label: string; protocol: string; base_url: string; project?: string }>; routes?: Record<string, { provider: string; model: string }> };
  const hints = ((view?.secrets as { provider_keys?: Record<string, string> } | undefined)?.provider_keys || {}) as Record<string, string>;
  const [providers, setProviders] = useState<LlmProvider[]>(() =>
    Object.entries(config.providers || {}).map(([id, meta]) => ({ id, label: meta.label, protocol: meta.protocol, base_url: meta.base_url, project: meta.project || "", api_key: "", hint: hints[id] || "" })),
  );
  const [routes, setRoutes] = useState<Record<string, { provider: string; model: string }>>(() => Object.fromEntries(ROUTES.map((route) => [route.key, config.routes?.[route.key] || { provider: "", model: "" }])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [outcome, setOutcome] = useState<TestOutcome | null>(null);

  function add(preset: keyof typeof PRESETS) {
    const base = PRESETS[preset];
    let id = preset === "custom" ? "custom" : preset;
    let n = 2;
    while (providers.some((p) => p.id === id)) id = `${preset}-${n++}`;
    setProviders((list) => [...list, { id, label: base.label, protocol: base.protocol, base_url: base.base_url, project: "", api_key: "", hint: "" }]);
    if (!providers.length) setRoutes((current) => Object.fromEntries(Object.entries(current).map(([key, route]) => [key, { ...route, provider: route.provider || id }])));
  }

  function update(index: number, patch: Partial<LlmProvider>) {
    setProviders((list) => list.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setOutcome(null);
    try {
      const payload = {
        providers: providers.map((p) => ({ id: p.id, label: p.label, protocol: p.protocol, base_url: p.base_url, project: p.project, ...(p.api_key.trim() ? { api_key: p.api_key.trim() } : {}), ...(p.clear_api_key ? { clear_api_key: true } : {}) })),
        routes,
      };
      const result = await platform.saveConnection("llm", payload);
      setOutcome(result.test);
      const nextHints = ((result.connection.secrets as { provider_keys?: Record<string, string> } | undefined)?.provider_keys || {}) as Record<string, string>;
      setProviders((list) => list.map((p) => ({ ...p, api_key: "", clear_api_key: false, hint: nextHints[p.id] || "" })));
      onSaved?.(result.connection, result.test);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const disabled = !canEdit || busy;
  return (
    <Box component="form" onSubmit={save} sx={{ display: "grid", gap: 2.5 }}>
      <Box>
        <Typography sx={{ fontSize: 13, fontWeight: 650, mb: 1 }}>Providers</Typography>
        <Box sx={{ display: "grid", gap: 1.5 }}>
          {providers.map((item, index) => (
            <Box key={item.id} sx={{ p: 1.75, borderRadius: "12px", border: `1px solid ${apple.hairline}`, display: "grid", gap: 1.5 }}>
              <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                <TextField size="small" label="Name" value={item.label} onChange={(event) => update(index, { label: event.target.value })} disabled={disabled} sx={{ flex: 1 }} />
                <TextField select size="small" label="Protocol" value={item.protocol} onChange={(event) => update(index, { protocol: event.target.value })} disabled={disabled} sx={{ width: 150 }}>
                  <MenuItem value="openai">OpenAI API</MenuItem>
                  <MenuItem value="anthropic">Anthropic API</MenuItem>
                </TextField>
                {canEdit ? (
                  <Tooltip title="Remove provider">
                    <IconButton size="small" onClick={() => setProviders((list) => list.filter((_, i) => i !== index))} disabled={busy} aria-label={`Remove ${item.label}`}>
                      <DeleteOutlineRoundedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                ) : null}
              </Box>
              <TextField size="small" label="Base URL" value={item.base_url} onChange={(event) => update(index, { base_url: event.target.value })} disabled={disabled} placeholder={item.protocol === "anthropic" ? "https://api.anthropic.com/v1" : "https://api.openai.com/v1"} />
              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: item.protocol === "openai" ? "2fr 1fr" : "1fr" } }}>
                <TextField
                  size="small"
                  type="password"
                  label="API key"
                  value={item.api_key}
                  onChange={(event) => update(index, { api_key: event.target.value, clear_api_key: false })}
                  disabled={disabled}
                  autoComplete="new-password"
                  placeholder={item.hint && !item.clear_api_key ? `Saved · ${item.hint} — paste to replace` : "Paste key"}
                />
                {item.protocol === "openai" ? <TextField size="small" label="Project (optional)" value={item.project} onChange={(event) => update(index, { project: event.target.value })} disabled={disabled} /> : null}
              </Box>
            </Box>
          ))}
          {canEdit ? (
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              {(Object.keys(PRESETS) as (keyof typeof PRESETS)[]).map((preset) => (
                <PillButton key={preset} variant="gray" size="small" startIcon={<AddRoundedIcon />} onClick={() => add(preset)} disabled={busy}>
                  {PRESETS[preset].label}
                </PillButton>
              ))}
            </Box>
          ) : null}
        </Box>
      </Box>
      {providers.length ? (
        <Box>
          <Typography sx={{ fontSize: 13, fontWeight: 650, mb: 0.5 }}>Routing</Typography>
          <Typography sx={{ fontSize: 12.5, color: apple.muted, mb: 1.5 }}>Pick a provider and model for each kind of work. Leave a model empty to use the provider default.</Typography>
          <Box sx={{ display: "grid", gap: 1.25 }}>
            {ROUTES.map((route) => (
              <Box key={route.key} sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", sm: "130px 1fr 1.3fr" }, alignItems: "center" }}>
                <Tooltip title={route.help} placement="left">
                  <Typography sx={{ fontSize: 13.5, fontWeight: 550 }}>{route.label}</Typography>
                </Tooltip>
                <TextField select size="small" value={routes[route.key]?.provider || providers[0]?.id || ""} onChange={(event) => setRoutes((current) => ({ ...current, [route.key]: { ...current[route.key], provider: event.target.value } }))} disabled={disabled} slotProps={{ htmlInput: { "aria-label": `${route.label} provider` } }}>
                  {providers.map((p) => (
                    <MenuItem key={p.id} value={p.id}>
                      {p.label}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField size="small" placeholder="Model, e.g. gpt-5 or claude-opus-4" value={routes[route.key]?.model || ""} onChange={(event) => setRoutes((current) => ({ ...current, [route.key]: { ...current[route.key], model: event.target.value } }))} disabled={disabled} slotProps={{ htmlInput: { "aria-label": `${route.label} model` } }} />
              </Box>
            ))}
          </Box>
        </Box>
      ) : null}
      {error ? <Banner severity="error">{error}</Banner> : null}
      <TestResult outcome={outcome} />
      {canEdit ? (
        <Box>
          <PillButton type="submit" disabled={busy || !providers.length}>
            {busy ? "Saving and testing…" : "Save and test"}
          </PillButton>
        </Box>
      ) : null}
    </Box>
  );
}

/** Zoho needs an OAuth round trip after the client ID and secret are saved. */
export function CliqConnect({ view, redirectUri, canEdit }: { view?: ConnectionView; redirectUri: string; canEdit: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const ready = Boolean(view?.config?.client_id) && secretState(view, "client_secret").set;
  const authorized = secretState(view, "refresh_token").set;
  async function connect() {
    setBusy(true);
    setError("");
    try {
      const { url } = await platform.cliqAuthorize();
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }
  return (
    <Box sx={{ p: 1.75, borderRadius: "12px", bgcolor: apple.hoverFill, display: "grid", gap: 1.25 }}>
      <Typography sx={{ fontSize: 13, fontWeight: 650 }}>{authorized ? "Zoho account linked" : "Link your Zoho account"}</Typography>
      <Typography sx={{ fontSize: 12.5, color: apple.muted }}>
        Add this redirect URI to your Zoho server-based app, save the client ID and secret below, then connect.
      </Typography>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, p: 1, borderRadius: "8px", bgcolor: apple.raised, border: `1px solid ${apple.hairline}` }}>
        <Typography sx={{ fontSize: 12, fontFamily: "ui-monospace, monospace", flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>{redirectUri}</Typography>
        <Tooltip title={copied ? "Copied" : "Copy"}>
          <IconButton
            size="small"
            aria-label="Copy redirect URI"
            onClick={() => {
              void navigator.clipboard?.writeText(redirectUri);
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1500);
            }}
          >
            <ContentCopyRoundedIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </Box>
      {error ? <Banner severity="error">{error}</Banner> : null}
      {canEdit ? (
        <Box>
          <PillButton variant={authorized ? "gray" : "filled"} onClick={connect} disabled={!ready || busy} endIcon={<OpenInNewRoundedIcon />}>
            {busy ? "Opening Zoho…" : authorized ? "Reconnect with Zoho" : "Connect with Zoho"}
          </PillButton>
        </Box>
      ) : null}
    </Box>
  );
}

export function ConnectionMeta({ view }: { view?: ConnectionView }) {
  if (!view?.connected) return null;
  return (
    <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", flexWrap: "wrap", fontSize: 12.5, color: apple.muted }}>
      <ToneChip tone={connectionTone(view)} size="sm" />
      {view.last_verified_at ? <Tooltip title={absoluteTime(view.last_verified_at)}><span>Verified {relativeTime(view.last_verified_at)}</span></Tooltip> : <span>Never verified</span>}
      {view.updated_by ? <span>Updated by {view.updated_by}</span> : null}
    </Box>
  );
}
