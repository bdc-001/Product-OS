"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import MoreHorizRoundedIcon from "@mui/icons-material/MoreHorizRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import StarRoundedIcon from "@mui/icons-material/StarRounded";
import SyncRoundedIcon from "@mui/icons-material/SyncRounded";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import LinearProgress from "@mui/material/LinearProgress";
import ListItemText from "@mui/material/ListItemText";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ProviderMark } from "@/app/settings/connections/provider-form";
import { RepositoryForm } from "@/app/settings/repositories/repository-form";
import { usePlatform } from "@/app/platform-state";
import { Banner, EmptyState, LoadingBlock, PageBody, PageHeader, PillButton, Segmented, SideDrawer } from "@/app/ui";
import { ToneChip, absoluteTime, relativeTime, runTone } from "@/app/ui/platform";
import { apple, pmm } from "@/app/ui/tokens";
import { platform, type Branch, type RepositoriesResponse, type Repository } from "@/lib/platform";

const FETCH_TONES: Record<string, { label: string; color: string; fill: string }> = {
  ok: { label: "Fetched", color: pmm.green, fill: pmm.greenFill },
  never: { label: "Not fetched yet", color: apple.muted, fill: apple.hoverFill },
  auth_failed: { label: "Credentials rejected", color: apple.danger, fill: apple.dangerFill },
  remote_blocked: { label: "IP not allowed", color: pmm.amber, fill: pmm.amberFill },
  not_found: { label: "Not found", color: apple.danger, fill: apple.dangerFill },
  unreachable: { label: "Unreachable", color: pmm.amber, fill: pmm.amberFill },
  error: { label: "Fetch failed", color: apple.danger, fill: apple.dangerFill },
};

function fetchTone(repo: Pick<Repository, "last_fetch_status" | "mode">) {
  if (repo.mode === "local") return { label: "Local clone", color: apple.text, fill: apple.hoverFill };
  return FETCH_TONES[repo.last_fetch_status] || FETCH_TONES.error;
}

function Fact({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography sx={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase", color: apple.muted }}>{label}</Typography>
      <Typography sx={{ mt: 0.25, fontSize: 13.5, fontWeight: 550, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontFamily: mono ? "ui-monospace, SFMono-Regular, Menlo, monospace" : undefined }}>{value || "—"}</Typography>
    </Box>
  );
}

function RepoCard({ repo, canEdit, onOpen, onChanged }: { repo: Repository; canEdit: boolean; onOpen: (tab: "branches" | "settings") => void; onChanged: () => void }) {
  const [menu, setMenu] = useState<HTMLElement | null>(null);
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState<{ ok: boolean; message: string } | null>(null);
  const syncing = repo.sync_run && (repo.sync_run.status === "queued" || repo.sync_run.status === "running");
  const tone = fetchTone(repo);

  async function act(kind: "sync" | "test" | "primary" | "remove") {
    setMenu(null);
    setBusy(kind);
    setNote(null);
    try {
      if (kind === "sync") await platform.syncRepository(repo.id);
      if (kind === "test") {
        const result = await platform.testRepository(repo.id);
        setNote({ ok: result.ok, message: result.message });
      }
      if (kind === "primary") await platform.editRepository(repo.id, { is_primary: true });
      if (kind === "remove") {
        if (!window.confirm(`Remove ${repo.name}? The mirror and checkouts are deleted; pipelines that need a repository will pause.`)) return;
        await platform.removeRepository(repo.id);
      }
      onChanged();
    } catch (err) {
      setNote({ ok: false, message: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy("");
    }
  }

  return (
    <Box sx={{ position: "relative", borderRadius: "16px", border: `1px solid ${repo.last_fetch_status !== "ok" && repo.last_fetch_status !== "never" && repo.mode !== "local" ? apple.dangerLine : apple.hairline}`, bgcolor: apple.raised, overflow: "hidden" }}>
      {syncing ? <LinearProgress aria-label="Syncing" sx={{ position: "absolute", top: 0, left: 0, right: 0, height: 2 }} /> : null}
      <Box sx={{ p: 2.25, display: "grid", gap: 2 }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5 }}>
          <ProviderMark id={repo.provider} name={repo.provider} size={40} />
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
              <Typography sx={{ fontSize: 16, fontWeight: 650, letterSpacing: "-0.01em" }}>{repo.name}</Typography>
              {repo.is_primary ? (
                <Tooltip title="Releases, codebase Q&A and discovery read this repository">
                  <Chip size="small" icon={<StarRoundedIcon sx={{ fontSize: 14 }} />} label="Primary" sx={{ height: 22, borderRadius: "7px", fontWeight: 600 }} />
                </Tooltip>
              ) : null}
            </Box>
            <Typography sx={{ fontSize: 12.5, color: apple.muted, fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{repo.mode === "local" ? repo.local_path : repo.remote_url}</Typography>
          </Box>
          <Box sx={{ display: "flex", gap: 0.5 }}>
            <Tooltip title={syncing ? `Sync ${runTone(repo.sync_run?.status || "running").label.toLowerCase()}` : "Fetch and update now"}>
              <span>
                <IconButton size="small" onClick={() => act("sync")} disabled={Boolean(syncing) || Boolean(busy)} aria-label={`Sync ${repo.name}`} sx={{ border: `1px solid ${apple.hairline}` }}>
                  <SyncRoundedIcon fontSize="small" className={syncing ? "sync-spinning" : undefined} />
                </IconButton>
              </span>
            </Tooltip>
            <IconButton size="small" onClick={(event) => setMenu(event.currentTarget)} aria-label={`More actions for ${repo.name}`} sx={{ border: `1px solid ${apple.hairline}` }}>
              <MoreHorizRoundedIcon fontSize="small" />
            </IconButton>
            <Menu anchorEl={menu} open={Boolean(menu)} onClose={() => setMenu(null)} slotProps={{ paper: { sx: { borderRadius: "12px", minWidth: 200 } } }}>
              <MenuItem onClick={() => { setMenu(null); onOpen("branches"); }}>Browse branches</MenuItem>
              {canEdit ? <MenuItem onClick={() => { setMenu(null); onOpen("settings"); }}>Edit settings</MenuItem> : null}
              {canEdit ? <MenuItem onClick={() => act("test")}>Test access</MenuItem> : null}
              {canEdit && !repo.is_primary ? <MenuItem onClick={() => act("primary")}>Make primary</MenuItem> : null}
              {canEdit ? <MenuItem onClick={() => act("remove")} sx={{ color: apple.danger }}>Remove</MenuItem> : null}
            </Menu>
          </Box>
        </Box>
        <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, minmax(0,1fr))" } }}>
          <Fact label="Product branch" value={repo.product_branch} mono />
          <Fact label="Releases" value={repo.release_pattern} mono />
          <Fact label="Branches" value={repo.branch_count ? repo.branch_count.toLocaleString() : "—"} />
          <Fact label="Indexed" value={repo.indexed_branches.length ? repo.indexed_branches.slice(0, 2).join(", ") : "Not yet"} />
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, flexWrap: "wrap" }}>
          <ToneChip tone={syncing ? runTone(repo.sync_run?.status || "running", "product") : tone} size="sm" />
          {repo.last_fetch_at ? (
            <Tooltip title={absoluteTime(repo.last_fetch_at)}>
              <Typography sx={{ fontSize: 12, color: apple.muted }}>Last fetch {relativeTime(repo.last_fetch_at)}</Typography>
            </Tooltip>
          ) : null}
          {repo.path_scopes.length ? <Typography sx={{ fontSize: 12, color: apple.muted }}>Scoped to {repo.path_scopes.join(", ")}</Typography> : null}
          <PillButton variant="text" size="small" onClick={() => onOpen("branches")} sx={{ ml: "auto", fontSize: 13 }}>
            Branches
          </PillButton>
        </Box>
        {repo.last_fetch_error && repo.last_fetch_status !== "ok" ? <Banner severity={repo.last_fetch_status === "remote_blocked" ? "warning" : "error"}>{repo.last_fetch_error}</Banner> : null}
        {note ? <Banner severity={note.ok ? "success" : "error"}>{note.message}</Banner> : null}
      </Box>
    </Box>
  );
}

function BranchList({ repo }: { repo: Repository }) {
  const [rows, setRows] = useState<Branch[] | null>(null);
  const [meta, setMeta] = useState<{ last_fetch_at: string | null; last_fetch_status: string; last_fetch_error: string } | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(
    async (refresh = false) => {
      setBusy(true);
      setError("");
      try {
        const data = await platform.branches(repo.id, { refresh });
        setRows(data.branches);
        setMeta(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [repo.id],
  );

  useEffect(() => {
    void load(false);
  }, [load]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (rows || [])
      .filter((b) => (filter === "release" ? b.is_release : filter === "open" ? !b.merged : filter === "indexed" ? b.indexed : true))
      .filter((b) => !needle || b.name.toLowerCase().includes(needle) || (b.message || "").toLowerCase().includes(needle));
  }, [rows, query, filter]);

  return (
    <Box sx={{ display: "grid", gap: 1.5 }}>
      <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
        <TextField
          size="small"
          fullWidth
          placeholder="Filter branches"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }, htmlInput: { "aria-label": "Filter branches" } }}
        />
        <Tooltip title="Fetch from the remote and refresh the list">
          <span>
            <PillButton variant="gray" size="small" onClick={() => load(true)} disabled={busy} startIcon={<SyncRoundedIcon className={busy ? "sync-spinning" : undefined} />}>
              Fetch
            </PillButton>
          </span>
        </Tooltip>
      </Box>
      <Segmented
        value={filter}
        onChange={setFilter}
        options={[
          { id: "all", label: `All${rows ? ` · ${rows.length}` : ""}` },
          { id: "release", label: "Releases" },
          { id: "open", label: "Unmerged" },
          { id: "indexed", label: "Indexed" },
        ]}
      />
      {meta ? (
        <Typography sx={{ fontSize: 12, color: apple.muted }}>
          {meta.last_fetch_at ? `Fetched ${relativeTime(meta.last_fetch_at)}` : "Never fetched"}
          {meta.last_fetch_status !== "ok" && meta.last_fetch_status !== "never" ? ` · ${FETCH_TONES[meta.last_fetch_status]?.label || meta.last_fetch_status}` : ""}
        </Typography>
      ) : null}
      {error ? <Banner severity="error">{error}</Banner> : null}
      {meta?.last_fetch_error && meta.last_fetch_status !== "ok" ? <Banner severity="warning">{meta.last_fetch_error}</Banner> : null}
      {rows === null ? (
        <LoadingBlock rows={6} height={44} label="Loading branches" />
      ) : visible.length ? (
        <Box sx={{ border: `1px solid ${apple.hairline}`, borderRadius: "12px", overflow: "hidden" }}>
          {visible.slice(0, 200).map((branch, index) => (
            <Box key={branch.name} sx={{ display: "flex", alignItems: "center", gap: 1.25, px: 1.5, py: 1, borderTop: index ? `1px solid ${apple.hairline}` : "none" }}>
              <ListItemText
                primary={
                  <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, flexWrap: "wrap" }}>
                    <Box component="span" sx={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 13, fontWeight: 550 }}>{branch.name}</Box>
                    {branch.is_product ? <Chip size="small" label="product" sx={{ height: 18, fontSize: 10.5, borderRadius: "5px", bgcolor: pmm.greenFill, color: pmm.green }} /> : null}
                    {branch.is_default && !branch.is_product ? <Chip size="small" label="default" sx={{ height: 18, fontSize: 10.5, borderRadius: "5px" }} /> : null}
                    {branch.is_release ? <Chip size="small" label="release" sx={{ height: 18, fontSize: 10.5, borderRadius: "5px", bgcolor: pmm.amberFill, color: pmm.amber }} /> : null}
                    {branch.indexed ? <Chip size="small" label="indexed" variant="outlined" sx={{ height: 18, fontSize: 10.5, borderRadius: "5px" }} /> : null}
                  </Box>
                }
                secondary={branch.message ? `${branch.message.split("\n")[0]}` : undefined}
                slotProps={{ secondary: { sx: { fontSize: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } } }}
                sx={{ minWidth: 0, m: 0 }}
              />
              <Box sx={{ textAlign: "right", flexShrink: 0 }}>
                <Typography sx={{ fontSize: 12, color: apple.muted }}>{relativeTime(branch.committed_at)}</Typography>
                <Typography sx={{ fontSize: 11, color: branch.merged ? pmm.green : apple.muted }}>{branch.merged ? "merged" : branch.sha.slice(0, 7)}</Typography>
              </Box>
            </Box>
          ))}
        </Box>
      ) : (
        <EmptyState>{rows.length ? "No branches match." : "No branches cached yet. Fetch to load them."}</EmptyState>
      )}
    </Box>
  );
}

export default function RepositoriesPage() {
  const { reloadPipelines } = usePlatform();
  const [data, setData] = useState<RepositoriesResponse | null>(null);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState<{ id: number; tab: "branches" | "settings" } | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await platform.repositories());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const syncing = (data?.repositories || []).some((r) => r.sync_run && (r.sync_run.status === "queued" || r.sync_run.status === "running"));
  useEffect(() => {
    if (!syncing) return;
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [syncing, load]);

  const selected = data?.repositories.find((r) => r.id === open?.id) || null;
  const changed = () => {
    void load();
    void reloadPipelines();
  };

  return (
    <PageBody>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <PageHeader title="Repositories" subtitle="Each repository is mirrored on the server and checked out at its product branch. Codebase Q&A, release detection and feature discovery read from here." />
        {data?.can_edit ? (
          <PillButton startIcon={<AddRoundedIcon />} onClick={() => setAdding(true)}>
            Add repository
          </PillButton>
        ) : null}
      </Box>
      {error ? <Banner severity="error">{error}</Banner> : null}
      {!data ? (
        <LoadingBlock rows={2} height={180} label="Loading repositories" />
      ) : data.repositories.length ? (
        <Box sx={{ display: "grid", gap: 2 }}>
          {data.repositories.map((repo) => (
            <RepoCard key={repo.id} repo={repo} canEdit={data.can_edit} onOpen={(tab) => setOpen({ id: repo.id, tab })} onChanged={changed} />
          ))}
        </Box>
      ) : (
        <Box sx={{ p: { xs: 3, md: 5 }, borderRadius: "18px", border: `1px dashed ${apple.hairline}`, textAlign: "center", bgcolor: apple.hoverFill }}>
          <Typography sx={{ fontSize: 18, fontWeight: 650 }}>Connect your first repository</Typography>
          <Typography sx={{ mt: 1, mb: 2.5, fontSize: 14, color: apple.muted, maxWidth: 520, mx: "auto" }}>
            Add a GitHub, GitLab or Bitbucket remote. The server keeps a read-only mirror, tracks branches and detects releases from the pattern you set.
          </Typography>
          {data.can_edit ? (
            <PillButton startIcon={<AddRoundedIcon />} onClick={() => setAdding(true)}>
              Add repository
            </PillButton>
          ) : (
            <Typography sx={{ fontSize: 13, color: apple.muted }}>Ask a workspace admin to add one.</Typography>
          )}
        </Box>
      )}

      <SideDrawer open={adding} onClose={() => setAdding(false)} width={{ xs: "100%", sm: 560 }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2.5 }}>
          <Typography component="h2" sx={{ fontSize: 19, fontWeight: 650 }}>
            Add a repository
          </Typography>
          <IconButton onClick={() => setAdding(false)} aria-label="Close" size="small">
            <CloseRoundedIcon fontSize="small" />
          </IconButton>
        </Box>
        {data ? (
          <RepositoryForm
            options={data}
            onCancel={() => setAdding(false)}
            onSaved={() => {
              setAdding(false);
              changed();
            }}
          />
        ) : null}
      </SideDrawer>

      <SideDrawer open={Boolean(selected)} onClose={() => setOpen(null)} width={{ xs: "100%", sm: 600 }}>
        {selected && data && open ? (
          <Box sx={{ display: "grid", gap: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              <ProviderMark id={selected.provider} name={selected.provider} size={36} />
              <Typography component="h2" sx={{ fontSize: 19, fontWeight: 650, flex: 1, minWidth: 0 }}>
                {selected.name}
              </Typography>
              <IconButton onClick={() => setOpen(null)} aria-label="Close" size="small">
                <CloseRoundedIcon fontSize="small" />
              </IconButton>
            </Box>
            {data.can_edit ? (
              <Segmented
                value={open.tab}
                onChange={(tab) => setOpen({ id: selected.id, tab: tab as "branches" | "settings" })}
                options={[
                  { id: "branches", label: "Branches" },
                  { id: "settings", label: "Settings" },
                ]}
              />
            ) : null}
            {open.tab === "settings" && data.can_edit ? (
              <RepositoryForm
                key={selected.id}
                options={data}
                repo={selected}
                onSaved={() => {
                  setOpen({ id: selected.id, tab: "branches" });
                  changed();
                }}
              />
            ) : (
              <BranchList key={selected.id} repo={selected} />
            )}
          </Box>
        ) : null}
      </SideDrawer>
    </PageBody>
  );
}
