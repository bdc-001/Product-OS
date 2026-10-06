"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AdminNotice, SettingsCard, SettingsPage } from "@/app/settings/shared";
import { Banner, EmptyState, LoadingBlock, PillButton, SideDrawer } from "@/app/ui";
import { apple } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { WorkspaceMark } from "@/app/workspace-switcher";
import { platform, type Person } from "@/lib/platform";

const ROLE_LABELS: Record<string, string> = { pm: "Product manager", dev: "Developer", qa: "QA", design: "Designer", notes_pm: "PM (notes only)", other: "Other" };

type Draft = Omit<Person, "id" | "aliases" | "active"> & { aliases: string };

const EMPTY: Draft = { name: "", short: "", email: "", jira_account_id: "", cliq_user_id: "", cliq_chat_id: "", role: "dev", team: "", notes: "", aliases: "" };

function toDraft(person?: Person): Draft {
  if (!person) return { ...EMPTY };
  return Object.fromEntries(Object.keys(EMPTY).map((key) => [key, key === "aliases" ? person.aliases.join(", ") : String(person[key as keyof Person] ?? "")])) as Draft;
}

function PersonSheet({ person, roles, canEdit, onClose, onSaved }: { person?: Person; roles: string[]; canEdit: boolean; onClose: () => void; onSaved: () => void }) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(person));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (patch: Partial<Draft>) => setDraft((current) => ({ ...current, ...patch }));

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = { ...draft, aliases: draft.aliases.split(",").map((a) => a.trim()).filter(Boolean) };
    try {
      if (person) await platform.editPerson(person.id, body);
      else await platform.addPerson(body);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function setActive(active: boolean) {
    if (!person) return;
    setBusy(true);
    try {
      if (active) await platform.editPerson(person.id, { active: true });
      else await platform.removePerson(person.id);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box component="form" onSubmit={save} sx={{ display: "grid", gap: 2 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
        <WorkspaceMark name={draft.name || "New person"} slug={draft.email || draft.name || "new"} size={44} />
        <Typography component="h2" sx={{ fontSize: 19, fontWeight: 650, flex: 1, minWidth: 0 }}>
          {person ? person.name : "Add a person"}
        </Typography>
        <IconButton onClick={onClose} aria-label="Close" size="small">
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </Box>
      {person && !person.active ? <Banner severity="info">Archived. Briefings no longer match this person.</Banner> : null}
      <Box sx={{ display: "grid", gap: 1.75, gridTemplateColumns: "1fr 1fr" }}>
        <TextField size="small" label="Full name" value={draft.name} onChange={(e) => set({ name: e.target.value })} required disabled={!canEdit} sx={{ gridColumn: "1 / -1" }} />
        <TextField size="small" label="Short name" value={draft.short} onChange={(e) => set({ short: e.target.value })} disabled={!canEdit} helperText="How briefings refer to them." />
        <TextField size="small" select label="Role" value={draft.role} onChange={(e) => set({ role: e.target.value })} disabled={!canEdit}>
          {roles.map((role) => (
            <MenuItem key={role} value={role}>
              {ROLE_LABELS[role] || role}
            </MenuItem>
          ))}
        </TextField>
        <TextField size="small" label="Email" value={draft.email} onChange={(e) => set({ email: e.target.value })} disabled={!canEdit} />
        <TextField size="small" label="Team" value={draft.team} onChange={(e) => set({ team: e.target.value })} disabled={!canEdit} />
      </Box>
      <Typography sx={{ fontSize: 12, fontWeight: 650, color: apple.muted, textTransform: "uppercase", letterSpacing: "0.06em", mt: 0.5 }}>Matching</Typography>
      <Box sx={{ display: "grid", gap: 1.75, gridTemplateColumns: "1fr 1fr" }}>
        <TextField size="small" label="Jira account ID" value={draft.jira_account_id} onChange={(e) => set({ jira_account_id: e.target.value })} disabled={!canEdit} sx={{ gridColumn: "1 / -1" }} helperText="Links assignee, developer and QA fields on tickets to this person." />
        <TextField size="small" label="Cliq user ID" value={draft.cliq_user_id} onChange={(e) => set({ cliq_user_id: e.target.value })} disabled={!canEdit} />
        <TextField size="small" label="Cliq direct chat ID" value={draft.cliq_chat_id} onChange={(e) => set({ cliq_chat_id: e.target.value })} disabled={!canEdit} />
        <TextField size="small" label="Also known as" value={draft.aliases} onChange={(e) => set({ aliases: e.target.value })} disabled={!canEdit} sx={{ gridColumn: "1 / -1" }} helperText="Comma-separated nicknames people use in chat." />
        <TextField size="small" label="Notes" value={draft.notes} onChange={(e) => set({ notes: e.target.value })} disabled={!canEdit} multiline minRows={2} sx={{ gridColumn: "1 / -1" }} />
      </Box>
      {error ? <Banner severity="error">{error}</Banner> : null}
      {canEdit ? (
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", pt: 1, borderTop: `1px solid ${apple.hairline}` }}>
          <PillButton type="submit" disabled={busy || !draft.name.trim()}>
            {busy ? "Saving…" : person ? "Save" : "Add person"}
          </PillButton>
          {person ? (
            <PillButton variant="text" disabled={busy} onClick={() => void setActive(!person.active)} sx={{ color: person.active ? apple.danger : apple.text }}>
              {person.active ? "Archive" : "Restore"}
            </PillButton>
          ) : null}
        </Box>
      ) : null}
    </Box>
  );
}

export default function PeopleSettings() {
  const { can } = useWorkspace();
  const canEdit = can("admin");
  const [data, setData] = useState<{ people: Person[]; roles: string[] } | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [role, setRole] = useState("");
  const [archived, setArchived] = useState(false);
  const [open, setOpen] = useState<Person | "new" | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await platform.people());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const people = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (data?.people || []).filter(
      (p) => p.active !== archived && (!role || p.role === role) && (!needle || `${p.name} ${p.short} ${p.email} ${p.team} ${p.aliases.join(" ")}`.toLowerCase().includes(needle)),
    );
  }, [data, query, role, archived]);
  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const p of data?.people || []) if (p.active) out[p.role] = (out[p.role] || 0) + 1;
    return out;
  }, [data]);
  const archivedCount = (data?.people || []).filter((p) => !p.active).length;

  return (
    <SettingsPage subtitle="The roster briefings, release follow-ups and Copilot resolve names against. People here don't need an account; invite teammates who sign in from Members.">
      <AdminNotice />
      {error ? <Banner severity="error">{error}</Banner> : null}
      <SettingsCard title={`Team${data ? ` · ${data.people.filter((p) => p.active).length}` : ""}`}>
        <Box sx={{ display: "flex", gap: 1.25, alignItems: "center", flexWrap: "wrap" }}>
          <TextField
            size="small"
            placeholder="Search people"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            sx={{ width: { xs: "100%", sm: 220 } }}
            slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }, htmlInput: { "aria-label": "Search people" } }}
          />
          <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", flex: 1 }}>
            <Chip label="All" onClick={() => setRole("")} variant={!role ? "filled" : "outlined"} color={!role ? "primary" : "default"} sx={{ borderRadius: "9px" }} />
            {(data?.roles || []).filter((r) => counts[r]).map((r) => (
              <Chip key={r} label={`${ROLE_LABELS[r] || r} · ${counts[r]}`} onClick={() => setRole(r)} variant={role === r ? "filled" : "outlined"} color={role === r ? "primary" : "default"} sx={{ borderRadius: "9px" }} />
            ))}
            {archivedCount ? <Chip label={`Archived · ${archivedCount}`} onClick={() => setArchived((v) => !v)} variant={archived ? "filled" : "outlined"} color={archived ? "primary" : "default"} sx={{ borderRadius: "9px" }} /> : null}
          </Box>
          {canEdit ? (
            <PillButton size="small" startIcon={<AddRoundedIcon />} onClick={() => setOpen("new")}>
              Add person
            </PillButton>
          ) : null}
        </Box>
        {!data ? (
          <LoadingBlock rows={5} height={48} />
        ) : people.length ? (
          <Box sx={{ border: `1px solid ${apple.hairline}`, borderRadius: "12px", overflow: "hidden" }}>
            {people.map((person, index) => {
              const linked = [person.jira_account_id && "Jira", person.cliq_user_id && "Cliq"].filter(Boolean).join(" · ");
              return (
                <ButtonBase
                  key={person.id}
                  onClick={() => setOpen(person)}
                  sx={{ width: "100%", display: "grid", gridTemplateColumns: { xs: "minmax(0,1fr) auto", sm: "minmax(0,1.4fr) 150px 120px" }, gap: 1.5, alignItems: "center", px: 1.75, py: 1.15, textAlign: "left", borderTop: index ? `1px solid ${apple.hairline}` : "none", "&:hover": { bgcolor: apple.hoverFill } }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, minWidth: 0 }}>
                    <WorkspaceMark name={person.name} slug={person.email || person.name} size={30} />
                    <Box sx={{ minWidth: 0 }}>
                      <Typography sx={{ fontSize: 14, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{person.name}</Typography>
                      <Typography sx={{ fontSize: 12, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{person.email || person.team || "—"}</Typography>
                    </Box>
                  </Box>
                  <Typography sx={{ fontSize: 13, color: apple.muted, display: { xs: "none", sm: "block" } }}>{ROLE_LABELS[person.role] || person.role}</Typography>
                  <Typography sx={{ fontSize: 12, color: linked ? apple.text : apple.muted, textAlign: { xs: "right", sm: "left" } }}>{linked || "Not linked"}</Typography>
                </ButtonBase>
              );
            })}
          </Box>
        ) : (
          <EmptyState>{data.people.length ? "No one matches these filters." : "No one yet. Add the developers, QA and designers whose work you track."}</EmptyState>
        )}
      </SettingsCard>
      <SideDrawer open={Boolean(open)} onClose={() => setOpen(null)} width={{ xs: "100%", sm: 480 }}>
        {open ? (
          <PersonSheet
            key={open === "new" ? "new" : open.id}
            person={open === "new" ? undefined : open}
            roles={data?.roles || Object.keys(ROLE_LABELS)}
            canEdit={canEdit}
            onClose={() => setOpen(null)}
            onSaved={() => {
              setOpen(null);
              void load();
            }}
          />
        ) : null}
      </SideDrawer>
    </SettingsPage>
  );
}
