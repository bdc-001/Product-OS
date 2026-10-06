"use client";

import { OrganizationSwitcher, useClerk } from "@clerk/nextjs";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import LogoutRoundedIcon from "@mui/icons-material/LogoutRounded";
import SettingsBrightnessOutlinedIcon from "@mui/icons-material/SettingsBrightnessOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import UnfoldMoreRoundedIcon from "@mui/icons-material/UnfoldMoreRounded";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Divider from "@mui/material/Divider";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useColorScheme } from "@mui/material/styles";
import NextLink from "next/link";
import { useState } from "react";
import { AppDialog, Banner, PillButton } from "@/app/ui";
import { apple } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { platform, type WorkspaceSummary } from "@/lib/platform";
import { clerkEnabled, setWorkspaceCookie } from "@/lib/session";

function hue(seed: string) {
  let h = 0;
  for (const char of seed) h = (h * 31 + char.charCodeAt(0)) % 360;
  return h;
}

export function WorkspaceMark({ name, slug, size = 32 }: { name: string; slug: string; size?: number }) {
  const h = hue(slug || name);
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase())
    .join("") || "W";
  return (
    <Box
      aria-hidden
      sx={{
        width: size,
        height: size,
        borderRadius: `${Math.round(size * 0.3)}px`,
        flexShrink: 0,
        display: "grid",
        placeItems: "center",
        color: "#fff",
        fontSize: Math.round(size * 0.4),
        fontWeight: 700,
        letterSpacing: "-0.02em",
        background: `linear-gradient(135deg, hsl(${h} 72% 58%) 0%, hsl(${(h + 48) % 360} 70% 46%) 100%)`,
        boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.18)",
      }}
    >
      {initials}
    </Box>
  );
}

const TIMEZONES = ["Asia/Kolkata", "UTC", "Europe/London", "Europe/Berlin", "America/New_York", "America/Chicago", "America/Los_Angeles", "Asia/Singapore", "Asia/Dubai", "Australia/Sydney"];

export function CreateWorkspaceDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Kolkata";
    } catch {
      return "Asia/Kolkata";
    }
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const ws = await platform.createWorkspace(name.trim(), timezone);
      setWorkspaceCookie(ws.slug);
      window.location.assign("/onboarding");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  const zones = TIMEZONES.includes(timezone) ? TIMEZONES : [timezone, ...TIMEZONES];
  return (
    <AppDialog open={open} onClose={onClose} title="Create a workspace" titleId="create-workspace-title">
      <Box component="form" onSubmit={create} sx={{ display: "grid", gap: 2, mt: 1 }}>
        <Typography sx={{ fontSize: 14, color: apple.muted }}>
          A workspace keeps its own connections, repositories, pipelines and data. Use one per product or team.
        </Typography>
        <TextField autoFocus label="Workspace name" placeholder="Acme Analytics" value={name} onChange={(event) => setName(event.target.value)} size="small" fullWidth />
        <TextField select label="Timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)} size="small" fullWidth helperText="Schedules and briefings run on this clock.">
          {zones.map((zone) => (
            <MenuItem key={zone} value={zone}>
              {zone}
            </MenuItem>
          ))}
        </TextField>
        {error ? <Banner severity="error">{error}</Banner> : null}
        <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
          <PillButton variant="text" onClick={onClose} disabled={busy}>
            Cancel
          </PillButton>
          <PillButton type="submit" disabled={busy || !name.trim()}>
            {busy ? "Creating…" : "Create and set up"}
          </PillButton>
        </Box>
      </Box>
    </AppDialog>
  );
}

function LocalSwitcher({ collapsed }: { collapsed: boolean }) {
  const { me, switchTo } = useWorkspace();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [creating, setCreating] = useState(false);
  const current = me?.workspace;
  const label = current?.name || "Workspace";
  const sub = current?.product_name || (current?.role ? `${current.role[0].toUpperCase()}${current.role.slice(1)}` : "Loading…");

  const button = (
    <ButtonBase
      onClick={(event) => setAnchor(event.currentTarget)}
      aria-label={`Workspace: ${label}. Switch workspace`}
      aria-haspopup="menu"
      sx={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: collapsed ? "center" : "flex-start",
        gap: 1.25,
        p: collapsed ? 0.5 : 0.75,
        borderRadius: "12px",
        textAlign: "left",
        transition: `background-color 0.2s ${apple.smooth}`,
        "&:hover": { bgcolor: apple.hoverFill },
      }}
    >
      <WorkspaceMark name={label} slug={current?.slug || ""} size={collapsed ? 34 : 32} />
      {collapsed ? null : (
        <>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography sx={{ fontSize: 14, fontWeight: 650, letterSpacing: "-0.01em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</Typography>
            <Typography sx={{ fontSize: 11.5, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{sub}</Typography>
          </Box>
          <UnfoldMoreRoundedIcon sx={{ fontSize: 18, color: apple.muted }} />
        </>
      )}
    </ButtonBase>
  );

  return (
    <>
      {collapsed ? (
        <Tooltip title={label} placement="right">
          {button}
        </Tooltip>
      ) : (
        button
      )}
      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
        slotProps={{ paper: { sx: { minWidth: 260, mt: 0.5, borderRadius: "14px" } } }}
      >
        <Typography sx={{ px: 2, pt: 1, pb: 0.5, fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: apple.muted }}>Workspaces</Typography>
        {(me?.workspaces || []).map((ws: WorkspaceSummary) => (
          <MenuItem
            key={ws.slug}
            selected={ws.slug === current?.slug}
            onClick={() => {
              setAnchor(null);
              switchTo(ws.slug);
            }}
            sx={{ gap: 1.25, py: 1 }}
          >
            <WorkspaceMark name={ws.name} slug={ws.slug} size={26} />
            <ListItemText primary={ws.name} secondary={ws.product_name || ws.role} slotProps={{ primary: { sx: { fontSize: 14, fontWeight: 550 } }, secondary: { sx: { fontSize: 12 } } }} />
            {ws.slug === current?.slug ? <CheckRoundedIcon sx={{ fontSize: 18, color: apple.text }} /> : null}
          </MenuItem>
        ))}
        <Divider sx={{ my: 0.5 }} />
        <MenuItem
          onClick={() => {
            setAnchor(null);
            setCreating(true);
          }}
          sx={{ py: 1 }}
        >
          <ListItemIcon>
            <AddRoundedIcon fontSize="small" />
          </ListItemIcon>
          Create workspace
        </MenuItem>
        <MenuItem component={NextLink} href="/settings" onClick={() => setAnchor(null)} sx={{ py: 1 }}>
          <ListItemIcon>
            <SettingsOutlinedIcon fontSize="small" />
          </ListItemIcon>
          Workspace settings
        </MenuItem>
      </Menu>
      <CreateWorkspaceDialog open={creating} onClose={() => setCreating(false)} />
    </>
  );
}

function ClerkSwitcher({ collapsed }: { collapsed: boolean }) {
  return (
    <Box sx={{ display: "flex", justifyContent: collapsed ? "center" : "flex-start", "& .cl-rootBox, & .cl-organizationSwitcherTrigger": { width: collapsed ? "auto" : "100%" } }}>
      <OrganizationSwitcher
        hidePersonal={false}
        afterCreateOrganizationUrl="/onboarding"
        afterSelectOrganizationUrl="/"
        afterSelectPersonalUrl="/"
        appearance={{
          elements: {
            organizationSwitcherTrigger: { padding: "6px", borderRadius: "12px", justifyContent: collapsed ? "center" : "flex-start" },
            organizationPreviewTextContainer: collapsed ? { display: "none" } : {},
            organizationSwitcherTriggerIcon: collapsed ? { display: "none" } : {},
          },
        }}
      />
    </Box>
  );
}

export function WorkspaceSwitcher({ collapsed = false }: { collapsed?: boolean }) {
  return clerkEnabled ? <ClerkSwitcher collapsed={collapsed} /> : <LocalSwitcher collapsed={collapsed} />;
}

function ClerkSignOut({ onDone }: { onDone: () => void }) {
  const { signOut } = useClerk();
  return (
    <MenuItem
      onClick={() => {
        onDone();
        void signOut({ redirectUrl: "/sign-in" });
      }}
      sx={{ py: 1 }}
    >
      <ListItemIcon>
        <LogoutRoundedIcon fontSize="small" />
      </ListItemIcon>
      Sign out
    </MenuItem>
  );
}

export function AppearanceToggle() {
  const { mode, setMode } = useColorScheme();
  return (
    <ToggleButtonGroup
      exclusive
      size="small"
      value={mode || "light"}
      onChange={(_, next) => next && setMode(next)}
      aria-label="Appearance"
      sx={{ "& .MuiToggleButton-root": { px: 1.25, py: 0.5, borderRadius: "9px", border: `1px solid ${apple.hairline}`, color: apple.muted, "&.Mui-selected": { color: apple.text, bgcolor: apple.hoverFill } } }}
    >
      <ToggleButton value="light" aria-label="Light">
        <LightModeOutlinedIcon sx={{ fontSize: 16 }} />
      </ToggleButton>
      <ToggleButton value="dark" aria-label="Dark">
        <DarkModeOutlinedIcon sx={{ fontSize: 16 }} />
      </ToggleButton>
      <ToggleButton value="system" aria-label="Match system">
        <SettingsBrightnessOutlinedIcon sx={{ fontSize: 16 }} />
      </ToggleButton>
    </ToggleButtonGroup>
  );
}

export function UserMenu({ collapsed = false }: { collapsed?: boolean }) {
  const { me } = useWorkspace();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const name = me?.user.name || me?.user.email?.split("@")[0] || "You";
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase())
    .join("");
  const avatar = (
    <Avatar src={me?.user.avatar_url || undefined} sx={{ width: 30, height: 30, fontSize: 12, fontWeight: 600, bgcolor: apple.ink, color: apple.onInk }}>
      {initials}
    </Avatar>
  );
  return (
    <>
      <ButtonBase
        onClick={(event) => setAnchor(event.currentTarget)}
        aria-label="Account and appearance"
        aria-haspopup="menu"
        sx={{ width: "100%", display: "flex", alignItems: "center", justifyContent: collapsed ? "center" : "flex-start", gap: 1.25, p: 0.75, borderRadius: "12px", textAlign: "left", "&:hover": { bgcolor: apple.hoverFill } }}
      >
        {avatar}
        {collapsed ? null : (
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography sx={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{name}</Typography>
            <Typography sx={{ fontSize: 11, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {me ? `${me.role[0].toUpperCase()}${me.role.slice(1)} · ${me.workspace.name}` : "Loading…"}
            </Typography>
          </Box>
        )}
      </ButtonBase>
      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "top", horizontal: "left" }}
        transformOrigin={{ vertical: "bottom", horizontal: "left" }}
        slotProps={{ paper: { sx: { minWidth: 250, mb: 0.5, borderRadius: "14px" } } }}
      >
        <Box sx={{ px: 2, pt: 1, pb: 1.25 }}>
          <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{name}</Typography>
          <Typography sx={{ fontSize: 12, color: apple.muted }}>{me?.user.email}</Typography>
        </Box>
        <Divider />
        <Box sx={{ px: 2, py: 1.25, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
          <Typography sx={{ fontSize: 13 }}>Appearance</Typography>
          <AppearanceToggle />
        </Box>
        <Divider />
        <MenuItem component={NextLink} href="/settings" onClick={() => setAnchor(null)} sx={{ py: 1 }}>
          <ListItemIcon>
            <SettingsOutlinedIcon fontSize="small" />
          </ListItemIcon>
          Settings
        </MenuItem>
        {clerkEnabled ? <ClerkSignOut onDone={() => setAnchor(null)} /> : null}
      </Menu>
    </>
  );
}
