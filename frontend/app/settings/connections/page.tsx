"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Link from "@mui/material/Link";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { CliqConnect, ConnectionMeta, LlmForm, ProviderForm, ProviderMark, TestResult, connectionTone } from "@/app/settings/connections/provider-form";
import { usePlatform } from "@/app/platform-state";
import { Banner, LoadingBlock, PageBody, PageHeader, PillButton, SideDrawer } from "@/app/ui";
import { ToneChip, relativeTime } from "@/app/ui/platform";
import { apple, shadow } from "@/app/ui/tokens";
import { platform, type ConnectionView, type ConnectionsResponse, type Provider, type TestOutcome } from "@/lib/platform";

function primaryView(provider: Provider): ConnectionView | undefined {
  return provider.connections.find((c) => c.name === "default") || provider.connections[0];
}

function ProviderCard({ provider, onOpen }: { provider: Provider; onOpen: () => void }) {
  const connected = provider.connections.filter((c) => c.connected);
  const view = primaryView(provider);
  const tone = provider.multiple ? (connected.length ? { ...connectionTone(connected.find((c) => c.status === "error") || connected[0]), label: connected.some((c) => c.status === "error") ? "Needs attention" : `${connected.length} credential${connected.length === 1 ? "" : "s"}` } : connectionTone(undefined)) : connectionTone(view);
  return (
    <ButtonBase
      onClick={onOpen}
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "stretch",
        textAlign: "left",
        gap: 1.5,
        p: 2.25,
        borderRadius: "16px",
        border: `1px solid ${view?.status === "error" ? apple.dangerLine : apple.hairline}`,
        bgcolor: apple.raised,
        transition: `border-color 0.2s ${apple.smooth}, transform 0.35s ${apple.pop}, box-shadow 0.25s ${apple.smooth}`,
        "&:hover": { borderColor: apple.hairlineHover, transform: "translateY(-2px)", boxShadow: shadow.hover },
        "&:focus-visible": { outline: `2px solid ${apple.ink}`, outlineOffset: 2 },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
        <ProviderMark id={provider.id} name={provider.name} />
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography sx={{ fontSize: 15, fontWeight: 650, letterSpacing: "-0.01em" }}>{provider.name}</Typography>
          <Typography sx={{ fontSize: 12, color: apple.muted }}>{provider.category}</Typography>
        </Box>
        <ArrowForwardRoundedIcon sx={{ fontSize: 18, color: apple.muted }} />
      </Box>
      <Typography sx={{ fontSize: 13, color: apple.muted, lineHeight: 1.5, flex: 1 }}>{provider.description}</Typography>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
        <ToneChip tone={tone} size="sm" />
        {view?.last_verified_at && !provider.multiple ? <Typography sx={{ fontSize: 11.5, color: apple.muted }}>Verified {relativeTime(view.last_verified_at)}</Typography> : null}
      </Box>
      {provider.used_by.length ? (
        <Typography sx={{ fontSize: 11.5, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          Used by {provider.used_by.slice(0, 3).join(", ")}
          {provider.used_by.length > 3 ? ` +${provider.used_by.length - 3}` : ""}
        </Typography>
      ) : null}
    </ButtonBase>
  );
}

function ConnectionActions({ provider, view, canEdit, onChange }: { provider: Provider; view?: ConnectionView; canEdit: boolean; onChange: () => void }) {
  const [busy, setBusy] = useState<"" | "test" | "remove">("");
  const [outcome, setOutcome] = useState<TestOutcome | null>(null);
  const [error, setError] = useState("");
  if (!view?.connected || !canEdit) return null;
  return (
    <Box sx={{ display: "grid", gap: 1 }}>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
        <PillButton
          variant="gray"
          size="small"
          disabled={Boolean(busy)}
          onClick={async () => {
            setBusy("test");
            setError("");
            try {
              setOutcome(await platform.testConnection(provider.id, view.name));
              onChange();
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            } finally {
              setBusy("");
            }
          }}
        >
          {busy === "test" ? "Testing…" : "Test connection"}
        </PillButton>
        <PillButton
          variant="text"
          size="small"
          disabled={Boolean(busy)}
          sx={{ color: apple.danger }}
          onClick={async () => {
            if (!window.confirm(`Disconnect ${provider.name}${view.name !== "default" ? ` (${view.name})` : ""}? Pipelines that need it will pause.`)) return;
            setBusy("remove");
            setError("");
            try {
              await platform.disconnect(provider.id, view.name);
              onChange();
            } catch (err) {
              setError(err instanceof Error ? err.message : String(err));
            } finally {
              setBusy("");
            }
          }}
        >
          {busy === "remove" ? "Disconnecting…" : "Disconnect"}
        </PillButton>
      </Box>
      <TestResult outcome={outcome} />
      {error ? <Banner severity="error">{error}</Banner> : null}
      {view.status === "error" && view.last_error && !outcome ? <Banner severity="error">{view.last_error}</Banner> : null}
    </Box>
  );
}

function ProviderSheet({ provider, data, onClose, onChange }: { provider: Provider; data: ConnectionsResponse; onClose: () => void; onChange: () => void }) {
  const canEdit = data.can_edit;
  const view = primaryView(provider);
  const [adding, setAdding] = useState("");
  const [selected, setSelected] = useState<string>(() => (provider.multiple ? provider.connections.find((c) => c.connected)?.name || "" : "default"));
  const credentials = provider.connections.filter((c) => c.connected);
  const current = provider.multiple ? provider.connections.find((c) => c.name === selected && c.connected) : view;
  const formKey = `${provider.id}:${selected}:${current?.updated_at || "new"}`;

  return (
    <Box sx={{ display: "grid", gap: 2.5 }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5 }}>
        <ProviderMark id={provider.id} name={provider.name} size={44} />
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography component="h2" sx={{ fontSize: 19, fontWeight: 650, letterSpacing: "-0.02em" }}>
            {provider.name}
          </Typography>
          <Typography sx={{ fontSize: 13, color: apple.muted, mt: 0.25 }}>{provider.description}</Typography>
        </Box>
        <IconButton onClick={onClose} aria-label="Close" size="small">
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </Box>
      {provider.help_url ? (
        <Link href={provider.help_url} target="_blank" rel="noreferrer" sx={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 0.5, width: "fit-content" }}>
          Where to find these credentials <OpenInNewRoundedIcon sx={{ fontSize: 14 }} />
        </Link>
      ) : null}

      {provider.multiple ? (
        <Box sx={{ display: "grid", gap: 1 }}>
          <Typography sx={{ fontSize: 13, fontWeight: 650 }}>Credentials</Typography>
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            {credentials.map((c) => (
              <Chip key={c.name} label={c.name} onClick={() => setSelected(c.name)} variant={selected === c.name ? "filled" : "outlined"} color={selected === c.name ? "primary" : "default"} sx={{ borderRadius: "9px" }} />
            ))}
            {canEdit ? <Chip icon={<AddRoundedIcon />} label="Add credential" onClick={() => setSelected("")} variant={selected === "" ? "filled" : "outlined"} sx={{ borderRadius: "9px" }} /> : null}
          </Box>
          {selected === "" && canEdit ? (
            <TextField size="small" label="Credential name" value={adding} onChange={(event) => setAdding(event.target.value.replace(/[^a-zA-Z0-9_-]/g, "-").toLowerCase())} placeholder="e.g. main or deploy-key" helperText="Repositories pick a credential by this name." />
          ) : null}
        </Box>
      ) : null}

      {current ? <ConnectionMeta view={current} /> : null}
      {provider.id === "cliq" ? <CliqConnect view={view} redirectUri={data.cliq_redirect_uri} canEdit={canEdit} /> : null}

      {!canEdit ? (
        current?.connected ? null : <Banner severity="info">Ask a workspace admin to connect {provider.name}.</Banner>
      ) : provider.custom_ui === "llm" ? (
        <LlmForm key={formKey} view={view} canEdit onSaved={onChange} />
      ) : (
        <ProviderForm
          key={formKey}
          provider={provider}
          view={current}
          canEdit={!provider.multiple || selected !== "" || Boolean(adding.trim())}
          name={provider.multiple ? selected || adding.trim() || "default" : "default"}
          onSaved={(saved) => {
            if (provider.multiple) {
              setSelected(saved.name);
              setAdding("");
            }
            onChange();
          }}
        />
      )}

      <ConnectionActions key={`${formKey}:actions`} provider={provider} view={current} canEdit={canEdit} onChange={onChange} />

      {provider.used_by.length ? (
        <Box sx={{ pt: 1, borderTop: `1px solid ${apple.hairline}` }}>
          <Typography sx={{ fontSize: 12, fontWeight: 650, color: apple.muted, mb: 1, textTransform: "uppercase", letterSpacing: "0.06em" }}>Used by</Typography>
          <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
            {provider.used_by.map((name) => (
              <Chip key={name} size="small" label={name} variant="outlined" sx={{ borderRadius: "8px" }} />
            ))}
          </Box>
        </Box>
      ) : null}
      {provider.category === "Code" ? (
        <PillButton variant="gray" href="/settings/repositories" endIcon={<ArrowForwardRoundedIcon />} sx={{ justifySelf: "start" }}>
          Manage repositories
        </PillButton>
      ) : null}
    </Box>
  );
}

function ConnectionsHub() {
  const router = useRouter();
  const path = usePathname() || "/settings/connections";
  const params = useSearchParams();
  const { reloadPipelines } = usePlatform();
  const [data, setData] = useState<ConnectionsResponse | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const openId = params.get("provider") || "";
  const cliqResult = openId === "cliq" ? params.get("status") : null;
  const cliqMessage = params.get("message") || "";

  const load = useCallback(async () => {
    try {
      setData(await platform.connections());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const setOpen = (id: string) => {
    const next = new URLSearchParams(params.toString());
    if (id) next.set("provider", id);
    else next.delete("provider");
    next.delete("status");
    next.delete("message");
    router.replace(`${path}${next.toString() ? `?${next}` : ""}`, { scroll: false });
  };

  const categories = useMemo(() => ["All", ...Array.from(new Set((data?.providers || []).map((p) => p.category)))], [data]);
  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (data?.providers || []).filter((p) => (category === "All" || p.category === category) && (!needle || `${p.name} ${p.category} ${p.description} ${p.used_by.join(" ")}`.toLowerCase().includes(needle)));
  }, [data, query, category]);
  const connected = visible.filter((p) => p.connections.some((c) => c.connected));
  const available = visible.filter((p) => !p.connections.some((c) => c.connected));
  const open = data?.providers.find((p) => p.id === openId) || null;
  const failing = (data?.providers || []).filter((p) => p.connections.some((c) => c.status === "error"));

  async function changed() {
    await load();
    void reloadPipelines();
  }

  return (
    <PageBody>
      <PageHeader title="Connections" subtitle="Credentials are encrypted per workspace and never shown again after saving. Pipelines unlock as soon as the connections they need are verified." />
      {cliqResult === "connected" ? <Banner severity="success">Zoho Cliq is connected.</Banner> : null}
      {cliqResult === "error" ? <Banner severity="error">Zoho did not finish connecting{cliqMessage ? `: ${cliqMessage}` : "."}</Banner> : null}
      {error ? <Banner severity="error">{error}</Banner> : null}
      {failing.length ? (
        <Banner severity="warning">
          {failing.map((p) => p.name).join(", ")} {failing.length === 1 ? "needs" : "need"} attention. Pipelines that rely on {failing.length === 1 ? "it" : "them"} will fail until the credential is fixed.
        </Banner>
      ) : null}
      <Box sx={{ display: "flex", gap: 1.5, alignItems: "center", flexWrap: "wrap", mb: 3 }}>
        <TextField
          size="small"
          placeholder="Search services"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          sx={{ width: { xs: "100%", sm: 260 } }}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }, htmlInput: { "aria-label": "Search services" } }}
        />
        <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>
          {categories.map((name) => (
            <Chip key={name} label={name} onClick={() => setCategory(name)} variant={category === name ? "filled" : "outlined"} color={category === name ? "primary" : "default"} sx={{ borderRadius: "9px" }} />
          ))}
        </Box>
      </Box>
      {!data ? (
        <LoadingBlock rows={3} height={140} label="Loading connections" />
      ) : (
        <>
          {connected.length ? (
            <Box component="section" sx={{ mb: 4 }}>
              <Typography variant="h3" sx={{ mb: 1.5 }}>
                Connected <Box component="span" sx={{ color: apple.muted, fontWeight: 500 }}>· {connected.length}</Box>
              </Typography>
              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0,1fr))", xl: "repeat(3, minmax(0,1fr))" } }}>
                {connected.map((provider) => (
                  <ProviderCard key={provider.id} provider={provider} onOpen={() => setOpen(provider.id)} />
                ))}
              </Box>
            </Box>
          ) : null}
          {available.length ? (
            <Box component="section">
              <Typography variant="h3" sx={{ mb: 1.5 }}>
                Available <Box component="span" sx={{ color: apple.muted, fontWeight: 500 }}>· {available.length}</Box>
              </Typography>
              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0,1fr))", xl: "repeat(3, minmax(0,1fr))" } }}>
                {available.map((provider) => (
                  <ProviderCard key={provider.id} provider={provider} onOpen={() => setOpen(provider.id)} />
                ))}
              </Box>
            </Box>
          ) : null}
          {!visible.length ? <Typography sx={{ color: apple.muted, fontSize: 14 }}>No services match “{query}”.</Typography> : null}
        </>
      )}
      <SideDrawer open={Boolean(open)} onClose={() => setOpen("")} width={{ xs: "100%", sm: 520 }}>
        {open && data ? <ProviderSheet key={open.id} provider={open} data={data} onClose={() => setOpen("")} onChange={changed} /> : null}
      </SideDrawer>
    </PageBody>
  );
}

export default function ConnectionsPage() {
  return (
    <Suspense fallback={<PageBody><LoadingBlock rows={3} height={140} /></PageBody>}>
      <ConnectionsHub />
    </Suspense>
  );
}
