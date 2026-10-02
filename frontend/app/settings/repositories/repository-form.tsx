"use client";

import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import Box from "@mui/material/Box";
import Collapse from "@mui/material/Collapse";
import FormControlLabel from "@mui/material/FormControlLabel";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { useMemo, useState } from "react";
import { Banner, PillButton, Segmented } from "@/app/ui";
import { apple } from "@/app/ui/tokens";
import { platform, type RepositoriesResponse, type Repository, type RepositoryInput } from "@/lib/platform";

const PROVIDER_NAMES: Record<string, string> = { bitbucket: "Bitbucket", github: "GitHub", gitlab: "GitLab", other: "Other Git host" };

function guessProvider(url: string): string {
  if (/bitbucket\./i.test(url)) return "bitbucket";
  if (/github\./i.test(url)) return "github";
  if (/gitlab\./i.test(url)) return "gitlab";
  return "";
}

export function RepositoryForm({
  options,
  repo,
  onSaved,
  onCancel,
  submitLabel,
}: {
  options: Pick<RepositoriesResponse, "credentials" | "providers" | "merge_formats" | "local_allowed" | "egress_ip">;
  repo?: Repository;
  onSaved: (repo: Repository) => void;
  onCancel?: () => void;
  submitLabel?: string;
}) {
  const [form, setForm] = useState<RepositoryInput & { path_scopes: string }>(() => ({
    name: repo?.name || "",
    provider: repo?.provider || "github",
    remote_url: repo?.remote_url || "",
    connection_id: repo?.connection_id ?? null,
    mode: repo?.mode || "managed",
    local_path: repo?.local_path || "",
    default_branch: repo?.default_branch || "",
    product_branch: repo?.product_branch || "",
    release_pattern: repo?.release_pattern || "release/YYYY-MM-DD",
    merge_format: repo?.merge_format || "any",
    path_scopes: (repo?.path_scopes || []).join(", "),
    ui_path: repo?.ui_path || "",
    is_primary: repo?.is_primary ?? false,
  }));
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (patch: Partial<typeof form>) => setForm((current) => ({ ...current, ...patch }));
  const credentials = useMemo(() => options.credentials.filter((c) => form.provider === "other" || c.provider === form.provider), [options.credentials, form.provider]);
  const local = form.mode === "local";
  const valid = local ? Boolean(form.local_path?.trim()) : Boolean(form.remote_url?.trim());

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body: RepositoryInput = { ...form, connection_id: form.connection_id || null };
      const saved = repo ? await platform.editRepository(repo.id, body) : await platform.addRepository(body);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box component="form" onSubmit={submit} sx={{ display: "grid", gap: 2 }}>
      {options.local_allowed ? (
        <Segmented
          value={form.mode || "managed"}
          onChange={(mode) => set({ mode: mode as Repository["mode"] })}
          options={[
            { id: "managed", label: "Remote (mirrored)" },
            { id: "local", label: "Local clone" },
          ]}
        />
      ) : null}
      {local ? (
        <TextField size="small" label="Path to the clone" value={form.local_path} onChange={(event) => set({ local_path: event.target.value })} placeholder="/Users/you/code/product" helperText="An existing git checkout on this machine. Only available on self-hosted installs." required />
      ) : (
        <>
          <TextField
            size="small"
            label="Remote URL"
            value={form.remote_url}
            onChange={(event) => {
              const url = event.target.value;
              const guess = guessProvider(url);
              set({ remote_url: url, ...(guess && !repo ? { provider: guess } : {}) });
            }}
            placeholder="https://github.com/acme/product.git or git@github.com:acme/product.git"
            required
            slotProps={{ htmlInput: { spellCheck: false } }}
          />
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
            <TextField select size="small" label="Host" value={form.provider} onChange={(event) => set({ provider: event.target.value, connection_id: null })}>
              {options.providers.map((id) => (
                <MenuItem key={id} value={id}>
                  {PROVIDER_NAMES[id] || id}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label="Credential"
              value={form.connection_id ?? ""}
              onChange={(event) => set({ connection_id: event.target.value ? Number(event.target.value) : null })}
              helperText={
                credentials.length ? undefined : (
                  <>
                    None yet.{" "}
                    <Link component={NextLink} href={`/settings/connections?provider=${form.provider === "other" ? "github" : form.provider}`}>
                      Add a {PROVIDER_NAMES[form.provider || "github"] || "Git"} credential
                    </Link>
                  </>
                )
              }
            >
              <MenuItem value="">Public repository (no credential)</MenuItem>
              {credentials.map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {PROVIDER_NAMES[c.provider] || c.provider} · {c.name}
                  {c.status === "error" ? " (failing)" : ""}
                </MenuItem>
              ))}
            </TextField>
          </Box>
        </>
      )}
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
        <TextField size="small" label="Product branch" value={form.product_branch} onChange={(event) => set({ product_branch: event.target.value })} placeholder="main" helperText="What shipped code looks like. Defaults to the remote's default branch." />
        <TextField size="small" label="Release branches" value={form.release_pattern} onChange={(event) => set({ release_pattern: event.target.value })} placeholder="release/YYYY-MM-DD" helperText="Pattern used to detect releases. YYYY-MM-DD becomes a date." />
      </Box>
      <Box>
        <Link component="button" type="button" underline="none" onClick={() => setAdvanced((value) => !value)} sx={{ display: "inline-flex", alignItems: "center", gap: 0.5, fontSize: 13, color: apple.muted, fontWeight: 500 }}>
          <ExpandMoreRoundedIcon sx={{ fontSize: 18, transform: advanced ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
          {advanced ? "Hide advanced" : "Advanced"}
        </Link>
        <Collapse in={advanced} unmountOnExit>
          <Box sx={{ display: "grid", gap: 2, mt: 2 }}>
            <TextField size="small" label="Display name" value={form.name} onChange={(event) => set({ name: event.target.value })} placeholder="Taken from the URL when empty" />
            <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
              <TextField size="small" label="Default branch" value={form.default_branch} onChange={(event) => set({ default_branch: event.target.value })} placeholder="Detected from the remote" />
              <TextField select size="small" label="Merge commit format" value={form.merge_format} onChange={(event) => set({ merge_format: event.target.value })} helperText="How merged PR titles are parsed for release notes.">
                {options.merge_formats.map((id) => (
                  <MenuItem key={id} value={id}>
                    {id === "any" ? "Detect automatically" : PROVIDER_NAMES[id] || id}
                  </MenuItem>
                ))}
              </TextField>
            </Box>
            <TextField size="small" label="Paths to index" value={form.path_scopes} onChange={(event) => set({ path_scopes: event.target.value })} placeholder="services/api, web/src" helperText="Comma separated. Empty indexes the whole repository." />
            <TextField size="small" label="UI source path" value={form.ui_path} onChange={(event) => set({ ui_path: event.target.value })} placeholder="frontend/src" helperText="Where screens live; release screenshots and prototypes read from here." />
            <FormControlLabel control={<Switch checked={Boolean(form.is_primary)} onChange={(event) => set({ is_primary: event.target.checked })} />} label={<Typography sx={{ fontSize: 14 }}>Primary repository for releases, codebase Q&A and discovery</Typography>} />
          </Box>
        </Collapse>
      </Box>
      {options.egress_ip && !local ? (
        <Typography sx={{ fontSize: 12.5, color: apple.muted }}>
          If your Git host restricts access by IP, allow <Box component="code" sx={{ px: 0.5, borderRadius: "4px", bgcolor: apple.hoverFill }}>{options.egress_ip}</Box>.
        </Typography>
      ) : null}
      {error ? <Banner severity="error">{error}</Banner> : null}
      <Box sx={{ display: "flex", gap: 1 }}>
        <PillButton type="submit" disabled={busy || !valid}>
          {busy ? "Saving…" : submitLabel || (repo ? "Save changes" : "Add and sync")}
        </PillButton>
        {onCancel ? (
          <PillButton variant="text" onClick={onCancel} disabled={busy}>
            Cancel
          </PillButton>
        ) : null}
      </Box>
    </Box>
  );
}
