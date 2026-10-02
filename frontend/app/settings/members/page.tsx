"use client";

import MailOutlineRoundedIcon from "@mui/icons-material/MailOutlineRounded";
import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useCallback, useEffect, useState } from "react";
import { SettingsCard, SettingsPage } from "@/app/settings/shared";
import { Banner, LoadingBlock, PillButton } from "@/app/ui";
import { relativeTime } from "@/app/ui/platform";
import { apple } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { WorkspaceMark } from "@/app/workspace-switcher";
import { platform, type Member, type MembersResponse, type Role } from "@/lib/platform";

const ROLE_INFO: Record<Role, { label: string; blurb: string }> = {
  owner: { label: "Owner", blurb: "Everything, including ownership and removing admins." },
  admin: { label: "Admin", blurb: "Connections, repositories, schedules, profile and members." },
  member: { label: "Member", blurb: "Use every page and run pipelines. Cannot change settings." },
};

function MemberRow({ member, roles, me, onChange, first }: { member: Member; roles: Role[]; me: Role; onChange: () => void; first: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const admin = me === "owner" || me === "admin";
  const locked = !admin || member.you || (member.role === "owner" && me !== "owner");
  const choices = roles.filter((role) => role !== "owner" || me === "owner");

  async function change(role: Role) {
    setBusy(true);
    setError("");
    try {
      await platform.changeRole(member.id, role);
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Remove ${member.name || member.email} from this workspace? They lose access immediately.`)) return;
    setBusy(true);
    setError("");
    try {
      await platform.removeMember(member.id);
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <Box sx={{ px: 1.75, py: 1.25, borderTop: first ? "none" : `1px solid ${apple.hairline}` }}>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "minmax(0,1fr) auto", sm: "minmax(0,1fr) 120px 150px auto" }, gap: 1.5, alignItems: "center" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, minWidth: 0 }}>
          {member.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={member.avatar_url} alt="" width={32} height={32} style={{ borderRadius: "50%", objectFit: "cover" }} />
          ) : (
            <WorkspaceMark name={member.name || member.email} slug={member.email} size={32} />
          )}
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: 14, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {member.name || member.email.split("@")[0]}
              {member.you ? <Box component="span" sx={{ ml: 0.75, fontSize: 12, color: apple.muted, fontWeight: 500 }}>you</Box> : null}
            </Typography>
            <Typography sx={{ fontSize: 12, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{member.email}</Typography>
          </Box>
        </Box>
        <Typography sx={{ fontSize: 12.5, color: apple.muted, display: { xs: "none", sm: "block" } }}>{member.last_seen_at ? `Active ${relativeTime(member.last_seen_at)}` : "Never signed in"}</Typography>
        {locked ? (
          <Typography sx={{ fontSize: 13.5, fontWeight: 600 }}>{ROLE_INFO[member.role]?.label || member.role}</Typography>
        ) : (
          <TextField select size="small" value={member.role} onChange={(e) => void change(e.target.value as Role)} disabled={busy} aria-label={`Role for ${member.email}`}>
            {choices.map((role) => (
              <MenuItem key={role} value={role}>
                {ROLE_INFO[role]?.label || role}
              </MenuItem>
            ))}
          </TextField>
        )}
        {admin && !member.you && member.role !== "owner" ? (
          <PillButton size="small" variant="text" disabled={busy} onClick={() => void remove()} sx={{ color: apple.danger, display: { xs: "none", sm: "inline-flex" } }}>
            Remove
          </PillButton>
        ) : (
          <Box sx={{ display: { xs: "none", sm: "block" } }} />
        )}
      </Box>
      {error ? <Typography sx={{ mt: 0.75, fontSize: 12.5, color: apple.danger }}>{error}</Typography> : null}
    </Box>
  );
}

function InviteForm({ onInvited }: { onInvited: () => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      await platform.invite(email.trim(), role);
      setStatus({ ok: true, message: `Invitation sent to ${email.trim()}.` });
      setEmail("");
      onInvited();
    } catch (err) {
      setStatus({ ok: false, message: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box component="form" onSubmit={send} sx={{ display: "grid", gap: 1 }}>
      <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", sm: "minmax(0,1fr) 140px auto" }, alignItems: "start" }}>
        <TextField size="small" type="email" label="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <TextField size="small" select label="Role" value={role} onChange={(e) => setRole(e.target.value as Role)}>
          <MenuItem value="member">Member</MenuItem>
          <MenuItem value="admin">Admin</MenuItem>
        </TextField>
        <PillButton type="submit" startIcon={<MailOutlineRoundedIcon />} disabled={busy || !email.trim()} sx={{ height: 40 }}>
          {busy ? "Sending…" : "Invite"}
        </PillButton>
      </Box>
      {status ? <Typography sx={{ fontSize: 13, color: status.ok ? apple.muted : apple.danger }}>{status.message}</Typography> : null}
    </Box>
  );
}

export default function MembersSettings() {
  const { me } = useWorkspace();
  const [data, setData] = useState<MembersResponse | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      setData(await platform.members());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const role = me?.role || "member";
  const admin = role === "owner" || role === "admin";
  const local = me?.auth_mode === "local";

  return (
    <SettingsPage subtitle="Who can sign in to this workspace and what they can change.">
      {error ? <Banner severity="error">{error}</Banner> : null}
      {admin && data?.can_invite ? (
        <SettingsCard title="Invite a teammate" description="They get an email to join. Members can use everything and run pipelines; admins can also change settings.">
          <InviteForm onInvited={() => void load()} />
          {data.invitations.length ? (
            <Box sx={{ display: "grid", gap: 0.75 }}>
              <Typography sx={{ fontSize: 12, fontWeight: 650, color: apple.muted, textTransform: "uppercase", letterSpacing: "0.06em" }}>Pending</Typography>
              {data.invitations.map((invite) => (
                <Typography key={invite.id} sx={{ fontSize: 13.5 }}>
                  {invite.email} <Box component="span" sx={{ color: apple.muted }}>· {ROLE_INFO[invite.role]?.label || invite.role}</Box>
                </Typography>
              ))}
            </Box>
          ) : null}
        </SettingsCard>
      ) : null}
      {local ? (
        <Banner severity="info">This server runs in single-user mode, so there is no one to invite. Turn on Clerk sign-in when you host it to add teammates.</Banner>
      ) : data && !data.can_invite && admin ? (
        <Banner severity="info">This is a personal workspace. Create an organization from the workspace switcher to invite teammates.</Banner>
      ) : null}
      <SettingsCard title={`Members${data ? ` · ${data.members.length}` : ""}`}>
        {!data ? (
          <LoadingBlock rows={3} height={52} />
        ) : (
          <Box sx={{ border: `1px solid ${apple.hairline}`, borderRadius: "12px", overflow: "hidden" }}>
            {data.members.map((member, index) => (
              <MemberRow key={member.id} member={member} roles={data.roles} me={role} onChange={() => void load()} first={index === 0} />
            ))}
          </Box>
        )}
      </SettingsCard>
      <SettingsCard title="Roles">
        <Box sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0,1fr))" } }}>
          {(Object.keys(ROLE_INFO) as Role[]).map((r) => (
            <Box key={r} sx={{ p: 1.5, borderRadius: "12px", border: `1px solid ${apple.hairline}`, bgcolor: r === role ? apple.selFill : "transparent" }}>
              <Typography sx={{ fontSize: 14, fontWeight: 650 }}>
                {ROLE_INFO[r].label}
                {r === role ? <Box component="span" sx={{ ml: 0.75, fontSize: 12, color: apple.muted, fontWeight: 500 }}>your role</Box> : null}
              </Typography>
              <Typography sx={{ mt: 0.5, fontSize: 12.5, color: apple.muted, lineHeight: 1.5 }}>{ROLE_INFO[r].blurb}</Typography>
            </Box>
          ))}
        </Box>
      </SettingsCard>
    </SettingsPage>
  );
}
