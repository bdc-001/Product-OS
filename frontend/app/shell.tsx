"use client";

import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Link from "@mui/material/Link";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { CommandPaletteProvider, useCommandPalette } from "@/app/command-palette";
import { useCopilot } from "@/app/copilot/context";
import { CopilotWidget } from "@/app/copilot/widget";
import { PRIMARY, isActive, visibleOutputs, type NavLink } from "@/app/navigation";
import { PlatformProvider, usePlatform } from "@/app/platform-state";
import { PulseBar } from "@/app/pulse";
import { useRefresh } from "@/app/refresh";
import { Banner } from "@/app/ui";
import { apple, categoryAccent } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { UserMenu, WorkspaceSwitcher } from "@/app/workspace-switcher";
import { api } from "@/lib/api";
import { prefetchSection } from "@/lib/prefetch";

const COLLAPSE_KEY = "pm-shell-collapsed";

function NavItem({ link, on, collapsed, live, badge, onNavigate }: { link: NavLink; on: boolean; collapsed: boolean; live?: boolean; badge?: ReactNode; onNavigate?: () => void }) {
  const Icon = link.Icon;
  const tint = link.category ? categoryAccent(link.category).main : apple.text;
  const body = (
    <Link
      component={NextLink}
      href={link.href}
      prefetch
      underline="none"
      onClick={onNavigate}
      onPointerDown={() => prefetchSection(link.href)}
      onMouseEnter={() => prefetchSection(link.href)}
      onFocus={() => prefetchSection(link.href)}
      aria-label={collapsed ? link.label : undefined}
      aria-current={on ? "page" : undefined}
      sx={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        gap: collapsed ? 0 : 1.25,
        justifyContent: collapsed ? "center" : "flex-start",
        px: collapsed ? 1 : 1.25,
        py: 0.6,
        minHeight: 34,
        fontSize: 14,
        borderRadius: "10px",
        color: on ? apple.text : apple.muted,
        bgcolor: on ? apple.raised : "transparent",
        boxShadow: on ? `0 0 0 1px ${apple.hairline}, ${apple.shadow}` : "none",
        fontWeight: on ? 600 : 450,
        whiteSpace: "nowrap",
        transition: `background-color 0.25s ${apple.smooth}, color 0.25s ${apple.smooth}, transform 0.35s ${apple.pop}`,
        "&:hover": { bgcolor: on ? apple.raised : apple.selFill, color: apple.text, textDecoration: "none" },
        "&:active": { transform: "scale(0.97)" },
      }}
    >
      <Icon sx={{ fontSize: 19, flexShrink: 0, color: on ? tint : "inherit", transition: `color 0.25s ${apple.smooth}` }} />
      {collapsed ? null : <Box component="span" sx={{ overflow: "hidden", textOverflow: "ellipsis" }}>{link.label}</Box>}
      {live ? (
        <Box
          component="span"
          aria-label="Running"
          className="live-dot"
          sx={{ position: collapsed ? "absolute" : "static", top: 6, right: 6, ml: collapsed ? 0 : "auto", width: 7, height: 7, borderRadius: "50%", bgcolor: tint, flexShrink: 0 }}
        />
      ) : badge && !collapsed ? (
        <Box component="span" sx={{ ml: "auto" }}>{badge}</Box>
      ) : null}
    </Link>
  );
  return collapsed ? (
    <Tooltip title={link.label} placement="right">
      <Box>{body}</Box>
    </Tooltip>
  ) : (
    body
  );
}

function GroupLabel({ label, category, collapsed }: { label: string; category?: NavLink["category"]; collapsed: boolean }) {
  if (collapsed) return <Box sx={{ height: 1, bgcolor: apple.hairline, mx: 1.5, my: 1 }} />;
  return (
    <Typography sx={{ display: "flex", alignItems: "center", gap: 0.75, px: 1.25, pt: 1.75, pb: 0.5, fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: apple.muted }}>
      {category ? <Box component="span" sx={{ width: 6, height: 6, borderRadius: "2px", bgcolor: categoryAccent(category).main }} /> : null}
      {label}
    </Typography>
  );
}

function SearchTrigger({ collapsed }: { collapsed: boolean }) {
  const { openPalette } = useCommandPalette();
  const trigger = (
    <ButtonBase
      onClick={() => openPalette()}
      aria-label="Search or jump to (Command K)"
      sx={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: collapsed ? "center" : "flex-start",
        gap: 1,
        px: collapsed ? 1 : 1.25,
        py: 0.85,
        borderRadius: "10px",
        border: `1px solid ${apple.hairline}`,
        bgcolor: apple.raised,
        color: apple.muted,
        fontSize: 13,
        transition: `border-color 0.2s ${apple.smooth}`,
        "&:hover": { borderColor: apple.hairlineHover },
      }}
    >
      <SearchRoundedIcon sx={{ fontSize: 18 }} />
      {collapsed ? null : (
        <>
          <span>Search or jump to…</span>
          <Box component="kbd" sx={{ ml: "auto", fontSize: 11, fontFamily: "inherit", border: `1px solid ${apple.hairline}`, borderRadius: "6px", px: 0.6, lineHeight: "18px" }}>⌘K</Box>
        </>
      )}
    </ButtonBase>
  );
  return collapsed ? (
    <Tooltip title="Search (⌘K)" placement="right">
      {trigger}
    </Tooltip>
  ) : (
    trigger
  );
}

function Navigation({ collapsed, path, onNavigate }: { collapsed: boolean; path: string; onNavigate?: () => void }) {
  const { enabled, running, pipelines } = usePlatform();
  const { open: openCopilot } = useCopilot();
  const outputs = useMemo(() => visibleOutputs(enabled), [enabled]);
  const runningIds = useMemo(() => new Set(running.map((p) => p.id)), [running]);
  const failing = useMemo(() => (pipelines?.pipelines || []).filter((p) => p.status === "connection_error").flatMap((p) => p.readiness.failing), [pipelines]);
  const groups = useMemo(() => {
    const out: { label: string; category: NavLink["category"]; links: NavLink[] }[] = [];
    for (const link of outputs) {
      const last = out[out.length - 1];
      if (last && last.label === link.group) last.links.push(link);
      else out.push({ label: link.group, category: link.category, links: [link] });
    }
    return out;
  }, [outputs]);
  const settingsLink: NavLink = { href: "/settings", label: "Settings", Icon: SettingsOutlinedIcon, group: "Workspace" };

  return (
    <>
      <Box component="nav" aria-label="Main navigation" sx={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", mx: collapsed ? -0.5 : -1, px: collapsed ? 0.5 : 1, display: "grid", alignContent: "start", gap: 0.25 }}>
        {PRIMARY.map((link) => (
          <NavItem key={link.href} link={link} collapsed={collapsed} on={isActive(link, path)} onNavigate={onNavigate} />
        ))}
        {groups.map((group) => (
          <Box key={group.label} sx={{ display: "grid", gap: 0.25 }}>
            <GroupLabel label={group.label} category={group.category} collapsed={collapsed} />
            {group.links.map((link) => (
              <NavItem key={link.href} link={link} collapsed={collapsed} on={isActive(link, path)} onNavigate={onNavigate} live={(link.pipelines || []).some((id) => runningIds.has(id))} />
            ))}
          </Box>
        ))}
      </Box>
      <Box sx={{ borderTop: `1px solid ${apple.hairline}`, pt: 1, display: "grid", gap: 0.25 }}>
        <Tooltip title={collapsed ? "Copilot" : ""} placement="right">
          <ButtonBase
            onClick={() => {
              onNavigate?.();
              openCopilot();
            }}
            aria-label="Open Copilot"
            sx={{ display: "flex", alignItems: "center", justifyContent: collapsed ? "center" : "flex-start", gap: 1.25, px: collapsed ? 1 : 1.25, py: 0.6, minHeight: 34, borderRadius: "10px", fontSize: 14, color: apple.muted, "&:hover": { bgcolor: apple.selFill, color: apple.text } }}
          >
            <AutoAwesomeOutlinedIcon sx={{ fontSize: 19 }} />
            {collapsed ? null : "Copilot"}
          </ButtonBase>
        </Tooltip>
        <NavItem
          link={settingsLink}
          collapsed={collapsed}
          on={path.startsWith("/settings")}
          onNavigate={onNavigate}
          live={running.length > 0}
          badge={
            failing.length ? (
              <Box component="span" title={`${new Set(failing).size} connection needs attention`} sx={{ display: "block", width: 7, height: 7, borderRadius: "50%", bgcolor: apple.danger }} />
            ) : undefined
          }
        />
        <Box sx={{ mt: 0.5 }}>
          <UserMenu collapsed={collapsed} />
        </Box>
      </Box>
    </>
  );
}

function Frame({ children }: { children: ReactNode }) {
  const path = usePathname() || "/";
  const { me, error, loading } = useWorkspace();
  const { openPalette } = useCommandPalette();
  const { tick } = useRefresh();
  const [stash, setStash] = useState<{ branch?: string } | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => setMobileOpen(false), [path]);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      /* private mode */
    }
  }, []);

  useEffect(() => {
    if (!path.startsWith("/codebase")) {
      setStash(null);
      return;
    }
    api
      .codebaseStatus()
      .then((data) => setStash(data.stashed || data.stashed_note ? { branch: data.stashes?.[0]?.branch || "" } : null))
      .catch(() => null);
  }, [path, tick]);

  function toggleCollapsed() {
    setCollapsed((value) => {
      const next = !value;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* private mode */
      }
      return next;
    });
  }

  const studioCanvas = /^\/prototype\/\d+/.test(path) && !path.includes("/embed");
  const notesCanvas = path.startsWith("/notes");
  const bare = path.startsWith("/onboarding");
  const rail = collapsed ? 72 : 252;

  return (
    <Box
      className="platform"
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: bare ? "1fr" : `${rail}px minmax(0,1fr)` },
        minHeight: "100vh",
        bgcolor: apple.page,
        transition: `grid-template-columns 0.35s ${apple.smooth}`,
      }}
    >
      <Link href="#main-content" className="skip-link">
        Skip to content
      </Link>
      {bare ? null : (
        <>
          <Box sx={{ display: { xs: "flex", md: "none" }, alignItems: "center", gap: 1, px: 1.5, py: 1, bgcolor: apple.nav, borderBottom: `1px solid ${apple.hairline}`, position: "sticky", top: 0, zIndex: 10 }}>
            <IconButton aria-label="Open navigation" onClick={() => setMobileOpen(true)}>
              <MenuRoundedIcon />
            </IconButton>
            <Typography sx={{ fontWeight: 650, fontSize: 15, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{me?.workspace.name || "Product OS"}</Typography>
            <IconButton aria-label="Search" onClick={() => openPalette()}>
              <SearchRoundedIcon />
            </IconButton>
          </Box>
          <Drawer open={mobileOpen} onClose={() => setMobileOpen(false)} sx={{ display: { md: "none" } }} slotProps={{ paper: { sx: { width: 284, p: 1.5, bgcolor: apple.nav, display: "flex", flexDirection: "column", gap: 1.25 } } }}>
            <WorkspaceSwitcher />
            <SearchTrigger collapsed={false} />
            <Navigation collapsed={false} path={path} onNavigate={() => setMobileOpen(false)} />
          </Drawer>
          <Box
            component="aside"
            sx={{
              display: { xs: "none", md: "flex" },
              position: "sticky",
              top: 0,
              height: "100vh",
              flexDirection: "column",
              gap: 1.25,
              px: collapsed ? 1 : 1.5,
              py: 1.5,
              bgcolor: apple.nav,
              borderRight: `1px solid ${apple.hairline}`,
              transition: `padding 0.35s ${apple.smooth}`,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexDirection: collapsed ? "column" : "row" }}>
              <Box sx={{ flex: 1, minWidth: 0, width: "100%" }}>
                <WorkspaceSwitcher collapsed={collapsed} />
              </Box>
              <Tooltip title={collapsed ? "Expand sidebar" : "Collapse sidebar"} placement="right">
                <IconButton size="small" onClick={toggleCollapsed} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} sx={{ color: apple.muted, "&:hover": { bgcolor: apple.selFill } }}>
                  {collapsed ? <ChevronRightRoundedIcon fontSize="small" /> : <ChevronLeftRoundedIcon fontSize="small" />}
                </IconButton>
              </Tooltip>
            </Box>
            <SearchTrigger collapsed={collapsed} />
            <Navigation collapsed={collapsed} path={path} />
          </Box>
        </>
      )}
      <Box
        id="main-content"
        tabIndex={-1}
        component="main"
        className="workspace"
        sx={{
          minWidth: 0,
          bgcolor: apple.page,
          height: studioCanvas ? "100vh" : { xs: "auto", md: "100vh" },
          maxHeight: studioCanvas ? "100vh" : { md: "100vh" },
          overflow: studioCanvas ? "hidden" : notesCanvas ? { xs: "auto", md: "hidden" } : "auto",
          overflowX: "hidden",
          display: { md: notesCanvas ? "flex" : undefined },
          flexDirection: notesCanvas ? "column" : undefined,
          WebkitOverflowScrolling: "touch",
        }}
      >
        {studioCanvas || bare ? null : (
          <Box sx={notesCanvas ? { flexShrink: 0 } : undefined}>
            <Suspense fallback={null}>
              <PulseBar />
            </Suspense>
          </Box>
        )}
        {error && !loading ? (
          <Box sx={{ px: { xs: 2, md: 3, xl: 4 }, pt: 2 }}>
            <Banner severity="error">{error}</Banner>
          </Box>
        ) : null}
        {stash ? (
          <Box sx={{ px: { xs: 2, md: 3, xl: 4 }, pt: 2, flexShrink: 0 }}>
            <Banner severity="warning">
              Local code changes are saved in a stash{stash.branch ? ` on ${stash.branch}` : ""}.{" "}
              <Link component={NextLink} href="/settings/repositories" sx={{ fontWeight: 600 }}>
                Review in Repositories
              </Link>
            </Banner>
          </Box>
        ) : null}
        {notesCanvas ? <Box sx={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>{children}</Box> : children}
        {bare ? null : <CopilotWidget />}
      </Box>
    </Box>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname() || "/";
  if (/\/prototype\/\d+\/embed\/?$/.test(path) || /^\/sign-(in|up)(\/|$)/.test(path)) {
    return <>{children}</>;
  }
  return (
    <PlatformProvider>
      <CommandPaletteProvider>
        <Frame>{children}</Frame>
      </CommandPaletteProvider>
    </PlatformProvider>
  );
}
