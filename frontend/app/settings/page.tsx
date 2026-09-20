"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";
import { api, type LlmProviderSettings, type WorkspaceSettings } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, FrostCard, PageBody, PageHeader, PillButton, QuietDot, Section, SubSection } from "@/app/ui";
import { apple } from "@/app/theme";

const ROUTE_ORDER = ["prototype", "copilot", "docs", "marketing", "default"] as const;

type YouForm = {
  pm_display_name: string;
  pm_cliq_user_id: string;
  pm_cliq_mentions: string;
  timezone: string;
};

type JiraForm = { base_url: string; email: string; projects: string; api_token: string };
type CliqForm = {
  client_id: string;
  client_secret: string;
  refresh_token: string;
  access_token: string;
  api_domain: string;
  accounts_url: string;
  pm_email: string;
  pm_chat_id: string;
};
type MailForm = {
  release_notes_email: string;
  smtp_host: string;
  smtp_port: string;
  smtp_user: string;
  smtp_from: string;
  smtp_password: string;
};
type WorkspaceForm = {
  codebase_path: string;
  product_internal_chat_id: string;
  marketing_sheet_id: string;
  gdrive_folder_id: string;
  cartesia_voice_id: string;
  cartesia_api_key: string;
  gdrive_key_json: string;
};

function peopleToText(people?: Record<string, string>) {
  return Object.entries(people || {})
    .map(([id, name]) => `${id}=${name}`)
    .join("\n");
}

function peopleFromText(text: string) {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const sep = trimmed.includes("=") ? "=" : trimmed.includes("\t") ? "\t" : " ";
    const [id, ...rest] = trimmed.split(sep);
    const name = rest.join(sep).trim();
    if (id?.trim() && name) out[id.trim()] = name;
  }
  return out;
}

const SECRET_MASK = "********";

function isMaskedSecret(value?: string) {
  const text = (value || "").trim();
  if (!text) return true;
  return /^\*+$/.test(text) || /^•+$/.test(text) || text.includes("…");
}

function maskedIfSaved(saved?: boolean) {
  return saved ? SECRET_MASK : "";
}

function secretUpdate(value: string) {
  const text = value.trim();
  return text && !isMaskedSecret(text) ? text : undefined;
}

function SecretField({
  label,
  value,
  onChange,
  hint,
  saved,
  helper,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  saved?: boolean;
  helper?: string;
}) {
  const editing = Boolean(value) && !/^\*+$/.test(value.trim());
  return (
    <TextField
      label={label}
      type={editing ? "password" : "text"}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onFocus={() => {
        if (/^\*+$/.test((value || "").trim())) onChange("");
      }}
      onBlur={() => {
        if (!value.trim() && saved) onChange(SECRET_MASK);
      }}
      size="small"
      fullWidth
      autoComplete="new-password"
      placeholder={saved ? SECRET_MASK : ""}
      helperText={helper || (saved ? `Saved${hint ? ` · ${hint}` : ""}. Focus and paste to replace.` : "Not connected")}
    />
  );
}

export default function SettingsPage() {
  const [you, setYou] = useState<YouForm>({
    pm_display_name: "",
    pm_cliq_user_id: "",
    pm_cliq_mentions: "",
    timezone: "Asia/Kolkata",
  });
  const [jira, setJira] = useState<JiraForm>({ base_url: "", email: "", projects: "AC,PS", api_token: "" });
  const [cliq, setCliq] = useState<CliqForm>({
    client_id: "",
    client_secret: "",
    refresh_token: "",
    access_token: "",
    api_domain: "https://cliq.zoho.in",
    accounts_url: "https://accounts.zoho.in",
    pm_email: "",
    pm_chat_id: "",
  });
  const [providers, setProviders] = useState<LlmProviderSettings[]>([]);
  const [routes, setRoutes] = useState<Record<string, { provider: string; model: string }>>({});
  const [routeLabels, setRouteLabels] = useState<Record<string, string>>({});
  const [mail, setMail] = useState<MailForm>({
    release_notes_email: "",
    smtp_host: "",
    smtp_port: "587",
    smtp_user: "",
    smtp_from: "",
    smtp_password: "",
  });
  const [workspace, setWorkspace] = useState<WorkspaceForm>({
    codebase_path: "",
    product_internal_chat_id: "",
    marketing_sheet_id: "",
    gdrive_folder_id: "",
    cartesia_voice_id: "",
    cartesia_api_key: "",
    gdrive_key_json: "",
  });
  const [peopleText, setPeopleText] = useState("");
  const [snapshot, setSnapshot] = useState<WorkspaceSettings | null>(null);
  const [platform, setPlatform] = useState<{
    boards?: { AC: number; PS: number };
    connections?: { jira?: boolean; cliq?: boolean; llm?: boolean };
    hidden_count?: number;
  } | null>(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const { tick } = useRefresh();

  function applySettings(next: WorkspaceSettings) {
    setSnapshot(next);
    setYou({
      pm_display_name: next.pm_display_name || "",
      pm_cliq_user_id: next.pm_cliq_user_id || "",
      pm_cliq_mentions: next.pm_cliq_mentions || "",
      timezone: next.timezone || "Asia/Kolkata",
    });
    setJira({
      base_url: next.jira?.base_url || "",
      email: next.jira?.email || "",
      projects: next.jira?.projects || "AC,PS",
      api_token: maskedIfSaved(next.jira?.token_set),
    });
    setCliq({
      client_id: next.cliq?.client_id || "",
      client_secret: maskedIfSaved(next.cliq?.client_secret_set),
      refresh_token: maskedIfSaved(next.cliq?.refresh_token_set),
      access_token: maskedIfSaved(next.cliq?.access_token_set),
      api_domain: next.cliq?.api_domain || "https://cliq.zoho.in",
      accounts_url: next.cliq?.accounts_url || "https://accounts.zoho.in",
      pm_email: next.cliq?.pm_email || "",
      pm_chat_id: next.cliq?.pm_chat_id || "",
    });
    setProviders((next.llm?.providers || []).map((row) => ({ ...row, api_key: maskedIfSaved(row.api_key_set) })));
    setRoutes(next.llm?.routes || {});
    setRouteLabels(next.llm?.route_labels || {});
    setMail({
      release_notes_email: next.mail?.release_notes_email || "",
      smtp_host: next.mail?.smtp_host || "",
      smtp_port: String(next.mail?.smtp_port || 587),
      smtp_user: next.mail?.smtp_user || "",
      smtp_from: next.mail?.smtp_from || "",
      smtp_password: maskedIfSaved(next.mail?.password_set),
    });
    setWorkspace({
      codebase_path: next.workspace?.codebase_path || "",
      product_internal_chat_id: next.workspace?.product_internal_chat_id || "",
      marketing_sheet_id: next.workspace?.marketing_sheet_id || "",
      gdrive_folder_id: next.workspace?.gdrive_folder_id || "",
      cartesia_voice_id: next.workspace?.cartesia_voice_id || "",
      cartesia_api_key: maskedIfSaved(next.workspace?.cartesia_key_set),
      gdrive_key_json: maskedIfSaved(next.workspace?.gdrive_key_set),
    });
    setPeopleText(peopleToText(next.people));
  }

  useEffect(() => {
    Promise.all([api.settings(), api.platform()])
      .then(([next, overview]) => {
        applySettings(next);
        setPlatform(overview);
      })
      .catch((err) => setError(String(err)));
  }, [tick]);

  async function persist(body: Parameters<typeof api.saveSettings>[0], message: string) {
    setError("");
    setSaved("");
    try {
      const next = await api.saveSettings(body);
      applySettings(next);
      setSaved(message);
    } catch (err) {
      setError(String(err));
    }
  }

  async function capture() {
    setError("");
    setSaved("");
    try {
      const next = await api.captureSettings();
      applySettings(next);
      setSaved("Your keys are encrypted on this Mac. Change them here from now on — no terminal needed.");
    } catch (err) {
      setError(String(err));
    }
  }

  function updateProvider(index: number, patch: Partial<LlmProviderSettings>) {
    setProviders((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  return (
    <PageBody>
      <PageHeader title="Settings" subtitle="Connect your Jira, Cliq, and model APIs. Secrets are encrypted on this Mac and never written back to .env." />
      {error ? <Banner severity="error">{error}</Banner> : null}
      {saved ? (
        <Typography sx={{ mb: 2, fontSize: 15, color: apple.muted }}>{saved}</Typography>
      ) : null}
      <FrostCard sx={{ mb: 3 }}>
        <Section title="Encrypted vault">
          <Stack spacing={1.5}>
            <Typography sx={{ fontSize: 15, color: apple.muted }}>
              {snapshot?.security?.encrypted
                ? "Jira, Cliq, model keys, mail, and Drive are stored encrypted. Edit a field and save that section to rotate a key."
                : "Lock your current connections into Settings so you can change them here later without the terminal."}
            </Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              {["jira", "cliq", "llm", "mail", "marketing"].map((name) => (
                <QuietDot
                  key={name}
                  on={snapshot?.security?.segments?.[name]?.set && snapshot?.security?.segments?.[name]?.encrypted}
                  label={name === "llm" ? "Models" : name === "marketing" ? "Drive / Cartesia" : name[0].toUpperCase() + name.slice(1)}
                />
              ))}
            </Stack>
            <PillButton type="button" onClick={capture}>
              {snapshot?.security?.encrypted ? "Re-encrypt what is in use" : "Encrypt and save what is in use"}
            </PillButton>
          </Stack>
        </Section>
      </FrostCard>

      <Stack spacing={3}>
        <Stack sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3 }}>
          <FrostCard>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                persist(you, "Identity saved.");
              }}
            >
              <Section title="You">
                <Stack spacing={2}>
                  <TextField label="Display name" value={you.pm_display_name} onChange={(event) => setYou({ ...you, pm_display_name: event.target.value })} size="small" fullWidth />
                  <TextField
                    label="Cliq user ID"
                    value={you.pm_cliq_user_id}
                    onChange={(event) => setYou({ ...you, pm_cliq_user_id: event.target.value })}
                    size="small"
                    fullWidth
                    helperText="Used when someone tags you in Cliq."
                  />
                  <TextField label="Also treat these as you" value={you.pm_cliq_mentions} onChange={(event) => setYou({ ...you, pm_cliq_mentions: event.target.value })} size="small" fullWidth />
                  <TextField label="Timezone" value={you.timezone} onChange={(event) => setYou({ ...you, timezone: event.target.value })} size="small" fullWidth />
                  <PillButton type="submit">Save identity</PillButton>
                </Stack>
              </Section>
            </form>
          </FrostCard>
          <Stack spacing={2}>
            <FrostCard>
              <Section title="Boards">
                <Typography sx={{ mb: 1 }}>Sense · AC — {platform?.boards?.AC ?? "—"} open tickets in scope</Typography>
                <Typography>Product Support · PS — {platform?.boards?.PS ?? "—"} open tickets in scope</Typography>
                <Typography sx={{ mt: 1, fontSize: 13, color: apple.muted }}>
                  Jira only pulls tickets where you are assignee, Product Manager, Developer, or tagged in comments. Aborted tickets are excluded.
                </Typography>
              </Section>
            </FrostCard>
            <FrostCard>
              <Section title="Connections">
                <Stack spacing={1}>
                  <QuietDot on={snapshot?.connections?.jira ?? platform?.connections?.jira} label={`Jira ${snapshot?.jira?.email || ""}`} />
                  <QuietDot on={snapshot?.connections?.cliq ?? platform?.connections?.cliq} label={`Cliq ${you.pm_cliq_user_id || ""}`} />
                  <QuietDot on={snapshot?.connections?.llm ?? platform?.connections?.llm} label="LLM" />
                  <Typography sx={{ fontSize: 13, color: apple.muted }}>{platform?.hidden_count || 0} cards removed from your view</Typography>
                </Stack>
              </Section>
            </FrostCard>
          </Stack>
        </Stack>

        <FrostCard>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              persist(
                {
                  jira: {
                    base_url: jira.base_url,
                    email: jira.email,
                    projects: jira.projects,
                    ...(secretUpdate(jira.api_token) ? { api_token: secretUpdate(jira.api_token) } : {}),
                  },
                },
                "Jira saved. Refresh to pull your tickets.",
              );
            }}
          >
            <Section title="Jira">
              <Stack spacing={2}>
                <TextField label="Site URL" value={jira.base_url} onChange={(event) => setJira({ ...jira, base_url: event.target.value })} size="small" fullWidth placeholder="https://your-org.atlassian.net" />
                <TextField label="Email" value={jira.email} onChange={(event) => setJira({ ...jira, email: event.target.value })} size="small" fullWidth />
                <SecretField label="API token" value={jira.api_token} onChange={(value) => setJira({ ...jira, api_token: value })} saved={snapshot?.jira?.token_set} hint={snapshot?.jira?.token_hint} helper="Atlassian account API token for this email." />
                <TextField label="Projects" value={jira.projects} onChange={(event) => setJira({ ...jira, projects: event.target.value })} size="small" fullWidth helperText="Comma-separated keys. Sense stays AC; Product Support is PS." />
                <Stack direction="row" spacing={1}>
                  <PillButton type="submit">Save Jira</PillButton>
                  {snapshot?.jira?.token_set ? (
                    <PillButton
                      type="button"
                      variant="gray"
                      onClick={() => persist({ jira: { clear_api_token: true } }, "Jira token disconnected.")}
                    >
                      Disconnect
                    </PillButton>
                  ) : null}
                </Stack>
              </Stack>
            </Section>
          </form>
        </FrostCard>

        <FrostCard>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              persist(
                {
                  cliq: {
                    client_id: cliq.client_id,
                    api_domain: cliq.api_domain,
                    accounts_url: cliq.accounts_url,
                    pm_email: cliq.pm_email,
                    pm_chat_id: cliq.pm_chat_id,
                    ...(secretUpdate(cliq.client_secret) ? { client_secret: secretUpdate(cliq.client_secret) } : {}),
                    ...(secretUpdate(cliq.refresh_token) ? { refresh_token: secretUpdate(cliq.refresh_token) } : {}),
                    ...(secretUpdate(cliq.access_token) ? { access_token: secretUpdate(cliq.access_token) } : {}),
                  },
                },
                "Cliq saved. Refresh so chats use this login.",
              );
            }}
          >
            <Section title="Cliq">
              <Stack spacing={2}>
                <TextField label="Client ID" value={cliq.client_id} onChange={(event) => setCliq({ ...cliq, client_id: event.target.value })} size="small" fullWidth />
                <SecretField label="Client secret" value={cliq.client_secret} onChange={(value) => setCliq({ ...cliq, client_secret: value })} saved={snapshot?.cliq?.client_secret_set} hint={snapshot?.cliq?.client_secret_hint} />
                <SecretField label="Refresh token" value={cliq.refresh_token} onChange={(value) => setCliq({ ...cliq, refresh_token: value })} saved={snapshot?.cliq?.refresh_token_set} hint={snapshot?.cliq?.refresh_token_hint} helper="From the Zoho API console. Paste yours — do not reuse another person’s token." />
                <SecretField label="Access token (optional)" value={cliq.access_token} onChange={(value) => setCliq({ ...cliq, access_token: value })} saved={snapshot?.cliq?.access_token_set} hint={snapshot?.cliq?.access_token_hint} />
                <TextField label="API domain" value={cliq.api_domain} onChange={(event) => setCliq({ ...cliq, api_domain: event.target.value })} size="small" fullWidth />
                <TextField label="Accounts URL" value={cliq.accounts_url} onChange={(event) => setCliq({ ...cliq, accounts_url: event.target.value })} size="small" fullWidth />
                <TextField label="Your Cliq email" value={cliq.pm_email} onChange={(event) => setCliq({ ...cliq, pm_email: event.target.value })} size="small" fullWidth />
                <TextField label="Personal chat ID (optional)" value={cliq.pm_chat_id} onChange={(event) => setCliq({ ...cliq, pm_chat_id: event.target.value })} size="small" fullWidth />
                <Stack direction="row" spacing={1}>
                  <PillButton type="submit">Save Cliq</PillButton>
                  {snapshot?.cliq?.configured ? (
                    <PillButton
                      type="button"
                      variant="gray"
                      onClick={() =>
                        persist(
                          { cliq: { clear_client_secret: true, clear_refresh_token: true, clear_access_token: true } },
                          "Cliq disconnected.",
                        )
                      }
                    >
                      Disconnect
                    </PillButton>
                  ) : null}
                </Stack>
              </Stack>
            </Section>
          </form>
        </FrostCard>

        <FrostCard>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              persist(
                {
                  llm: {
                    providers: providers.map((row) => ({
                      id: row.id,
                      label: row.label,
                      protocol: row.protocol,
                      base_url: row.base_url,
                      project: row.project || "",
                      ...(secretUpdate(row.api_key || "") ? { api_key: secretUpdate(row.api_key || "") } : {}),
                    })),
                    routes,
                  },
                },
                "Model mapping saved. New prototype and Copilot turns use it immediately.",
              );
            }}
          >
            <Section title="Models and APIs">
              <Typography sx={{ mb: 2, fontSize: 15, color: apple.muted }}>
                Add each API once, then map surfaces to a provider and model. Prototype uses the Prototype row.
              </Typography>
              <SubSection title="Providers">
                <Stack spacing={2}>
                  {providers.map((row, index) => (
                    <Stack key={row.id} spacing={1.5} sx={{ p: 1.5, border: `1px solid ${apple.hairline}`, borderRadius: "14px" }}>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <TextField label="ID" value={row.id} onChange={(event) => updateProvider(index, { id: event.target.value })} size="small" sx={{ width: 140 }} />
                        <TextField label="Label" value={row.label} onChange={(event) => updateProvider(index, { label: event.target.value })} size="small" fullWidth />
                        <IconButton
                          aria-label="Remove provider"
                          onClick={() => setProviders((current) => current.filter((_, i) => i !== index))}
                          disabled={providers.length <= 1}
                        >
                          <DeleteOutlineRoundedIcon fontSize="small" />
                        </IconButton>
                      </Stack>
                      <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                        <TextField select label="Protocol" value={row.protocol || "openai"} onChange={(event) => updateProvider(index, { protocol: event.target.value })} size="small" sx={{ minWidth: 160 }}>
                          <MenuItem value="openai">OpenAI-compatible</MenuItem>
                          <MenuItem value="anthropic">Anthropic</MenuItem>
                        </TextField>
                        <TextField label="Base URL" value={row.base_url} onChange={(event) => updateProvider(index, { base_url: event.target.value })} size="small" fullWidth />
                      </Stack>
                      <TextField label="Project (optional)" value={row.project || ""} onChange={(event) => updateProvider(index, { project: event.target.value })} size="small" fullWidth />
                      <SecretField label="API key" value={row.api_key || ""} onChange={(value) => updateProvider(index, { api_key: value })} saved={row.api_key_set} hint={row.api_key_hint} />
                    </Stack>
                  ))}
                  <PillButton
                    type="button"
                    variant="gray"
                    onClick={() =>
                      setProviders((current) => [
                        ...current,
                        {
                          id: `provider-${current.length + 1}`,
                          label: "New API",
                          protocol: "openai",
                          base_url: "https://api.openai.com/v1",
                          project: "",
                          api_key: "",
                        },
                      ])
                    }
                  >
                    <AddRoundedIcon sx={{ mr: 0.5, fontSize: 18 }} />
                    Add API
                  </PillButton>
                </Stack>
              </SubSection>
              <SubSection title="Which model each surface uses">
                <Stack spacing={1.5}>
                  {ROUTE_ORDER.map((key) => (
                    <Stack key={key} direction={{ xs: "column", md: "row" }} spacing={1}>
                      <TextField
                        select
                        label={routeLabels[key] || key}
                        value={routes[key]?.provider || providers[0]?.id || ""}
                        onChange={(event) => setRoutes((current) => ({ ...current, [key]: { ...(current[key] || { model: "" }), provider: event.target.value } }))}
                        size="small"
                        sx={{ minWidth: 220 }}
                      >
                        {providers.map((row) => (
                          <MenuItem key={row.id} value={row.id}>
                            {row.label || row.id}
                          </MenuItem>
                        ))}
                      </TextField>
                      <TextField
                        label="Model"
                        value={routes[key]?.model || ""}
                        onChange={(event) => setRoutes((current) => ({ ...current, [key]: { ...(current[key] || { provider: providers[0]?.id || "" }), model: event.target.value } }))}
                        size="small"
                        fullWidth
                        placeholder="gpt-4o-mini"
                      />
                    </Stack>
                  ))}
                </Stack>
              </SubSection>
              <PillButton type="submit">Save models</PillButton>
            </Section>
          </form>
        </FrostCard>

        <Stack sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3 }}>
          <FrostCard>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                persist(
                  {
                    workspace: {
                      codebase_path: workspace.codebase_path,
                      product_internal_chat_id: workspace.product_internal_chat_id,
                      marketing_sheet_id: workspace.marketing_sheet_id,
                      gdrive_folder_id: workspace.gdrive_folder_id,
                      cartesia_voice_id: workspace.cartesia_voice_id,
                      cartesia_api_key: secretUpdate(workspace.cartesia_api_key),
                      gdrive_key_json: secretUpdate(workspace.gdrive_key_json),
                    },
                    people: peopleFromText(peopleText),
                  },
                  "Workspace saved.",
                );
              }}
            >
              <Section title="Workspace">
                <Stack spacing={2}>
                  <TextField label="Codebase path" value={workspace.codebase_path} onChange={(event) => setWorkspace({ ...workspace, codebase_path: event.target.value })} size="small" fullWidth helperText="Local clone used for Copilot and indexing." />
                  <TextField label="Product-internal Cliq chat ID" value={workspace.product_internal_chat_id} onChange={(event) => setWorkspace({ ...workspace, product_internal_chat_id: event.target.value })} size="small" fullWidth />
                  <TextField
                    label="People directory"
                    value={peopleText}
                    onChange={(event) => setPeopleText(event.target.value)}
                    size="small"
                    fullWidth
                    multiline
                    minRows={4}
                    helperText="One person per line: cliqId=Name. Overrides the built-in directory for this install."
                  />
                  <TextField label="Marketing sheet ID" value={workspace.marketing_sheet_id} onChange={(event) => setWorkspace({ ...workspace, marketing_sheet_id: event.target.value })} size="small" fullWidth />
                  <TextField label="Drive folder ID" value={workspace.gdrive_folder_id} onChange={(event) => setWorkspace({ ...workspace, gdrive_folder_id: event.target.value })} size="small" fullWidth />
                  <TextField label="Cartesia voice ID" value={workspace.cartesia_voice_id} onChange={(event) => setWorkspace({ ...workspace, cartesia_voice_id: event.target.value })} size="small" fullWidth />
                  <SecretField label="Cartesia API key" value={workspace.cartesia_api_key} onChange={(value) => setWorkspace({ ...workspace, cartesia_api_key: value })} saved={snapshot?.workspace?.cartesia_key_set} hint={snapshot?.workspace?.cartesia_key_hint} />
                  <SecretField
                    label="Google Drive service account JSON"
                    value={workspace.gdrive_key_json}
                    onChange={(value) => setWorkspace({ ...workspace, gdrive_key_json: value })}
                    saved={snapshot?.workspace?.gdrive_key_set}
                    hint={snapshot?.workspace?.gdrive_key_hint}
                    helper="Paste the JSON to rotate it. The original key file is not rewritten."
                  />
                  <PillButton type="submit">Save workspace</PillButton>
                </Stack>
              </Section>
            </form>
          </FrostCard>
          <FrostCard>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                persist(
                  {
                    mail: {
                      release_notes_email: mail.release_notes_email,
                      smtp_host: mail.smtp_host,
                      smtp_port: Number(mail.smtp_port) || 587,
                      smtp_user: mail.smtp_user,
                      smtp_from: mail.smtp_from,
                      ...(secretUpdate(mail.smtp_password) ? { smtp_password: secretUpdate(mail.smtp_password) } : {}),
                    },
                  },
                  "Mail saved.",
                );
              }}
            >
              <Section title="Mail">
                <Stack spacing={2}>
                  <TextField label="Release notes to" value={mail.release_notes_email} onChange={(event) => setMail({ ...mail, release_notes_email: event.target.value })} size="small" fullWidth />
                  <TextField label="SMTP host" value={mail.smtp_host} onChange={(event) => setMail({ ...mail, smtp_host: event.target.value })} size="small" fullWidth />
                  <TextField label="SMTP port" value={mail.smtp_port} onChange={(event) => setMail({ ...mail, smtp_port: event.target.value })} size="small" fullWidth />
                  <TextField label="SMTP user" value={mail.smtp_user} onChange={(event) => setMail({ ...mail, smtp_user: event.target.value })} size="small" fullWidth />
                  <TextField label="From address" value={mail.smtp_from} onChange={(event) => setMail({ ...mail, smtp_from: event.target.value })} size="small" fullWidth />
                  <SecretField label="SMTP password" value={mail.smtp_password} onChange={(value) => setMail({ ...mail, smtp_password: value })} saved={snapshot?.mail?.password_set} hint={snapshot?.mail?.password_hint} />
                  <PillButton type="submit">Save mail</PillButton>
                </Stack>
              </Section>
            </form>
          </FrostCard>
        </Stack>
      </Stack>
    </PageBody>
  );
}
