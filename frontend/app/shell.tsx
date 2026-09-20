"use client";

import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import Drawer from "@mui/material/Drawer";
import Avatar from "@mui/material/Avatar";
import { LINKS } from "@/app/navigation";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Link from "@mui/material/Link";
import Stack from "@/app/ui/stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { api, peekGet } from "@/lib/api";
import { prefetchSection } from "@/lib/prefetch";
import { PulseBar } from "@/app/pulse";
import { CopilotWidget } from "@/app/copilot/widget";
import { useRefresh } from "@/app/refresh";
import { Banner, ConnectionDots } from "@/app/ui";
import { apple } from "@/app/theme";


const COLLAPSE_KEY = "pm-shell-collapsed";

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname() || "/";
  const cached = peekGet<{ pm_display_name: string; jira: boolean; cliq: boolean; llm: boolean }>("/api/workspace/summary");
  const [profile, setProfile] = useState({ pm_display_name: cached?.pm_display_name || "Arsalaan" });
  const [health, setHealth] = useState<{ jira?: boolean; cliq?: boolean; llm?: boolean }>(
    cached ? { jira: cached.jira, cliq: cached.cliq, llm: cached.llm } : {},
  );
  const [stash, setStash] = useState<{ branch?: string } | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => setMobileOpen(false), [path]);
  const { tick } = useRefresh();

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    api
      .workspaceSummary()
      .then((data) => {
        setProfile({ pm_display_name: data.pm_display_name || "Arsalaan" });
        setHealth({jira:data.jira,cliq:data.cliq,llm:data.llm});
      })
      .catch(() => null);
  }, [tick]);

  useEffect(() => {
    if (!path.startsWith("/codebase")) { setStash(null); return; }
    api
      .codebaseStatus()
      .then((data) => {
        if (data.stashed || data.stashed_note) setStash({ branch: data.stashes?.[0]?.branch || "" });
        else setStash(null);
      })
      .catch(() => null);
  }, [path, tick]);

  const [studioCanvas, setStudioCanvas] = useState(false);
  useEffect(() => {
    setStudioCanvas(/^\/prototype\/\d+/.test(path) && !path.includes("/embed"));
  }, [path]);
  const ticketBoard = (path.match(/^\/issues\/([A-Z]+)-/i) || [])[1]?.toUpperCase();
  const firstName = (profile.pm_display_name || "Arsalaan").split(" ")[0] || "Arsalaan";
  const rail = collapsed ? 76 : 240;

  function active(href: string) {
    if (href === "/") return path === "/";
    if (href === "/jira") {
      return (
        path.startsWith("/jira") ||
        path.startsWith("/sense") ||
        path.startsWith("/support") ||
        ticketBoard === "AC" ||
        ticketBoard === "PS"
      );
    }
    if (href === "/cliq") return path.startsWith("/cliq") || path.startsWith("/signals");
    if (href === "/codebase") return path.startsWith("/codebase");
    if (href === "/prototype") return path.startsWith("/prototype");
    if (href === "/prd") return path.startsWith("/prd");
    if (href === "/marketing") return path.startsWith("/marketing");
    if (href === "/artifacts") return path.startsWith("/artifacts");
    if (href === "/comms") return path.startsWith("/comms");
    if (href === "/roadmap") return path.startsWith("/roadmap");
    if (href === "/competitors") return path.startsWith("/competitors");
    if (href === "/notes" || href === "/lms") return path.startsWith(href);
    if (href === "/settings") return path.startsWith("/settings");
    return false;
  }

  function toggleCollapsed() {
    setCollapsed((value) => {
      const next = !value;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  const navLinkSx = (on: boolean) => ({
    display: "flex",
    alignItems: "center",
    gap: collapsed ? 0 : 1.25,
    justifyContent: collapsed ? "center" : "flex-start",
    px: collapsed ? 1 : 1.5,
    py: 0.55,
    minHeight: 34,
    fontSize: 14,
    borderRadius: "10px",
    color: on ? "#fff" : apple.text,
    bgcolor: on ? apple.ink : "transparent",
    fontWeight: on ? 500 : 400,
    whiteSpace: "nowrap" as const,
    transition: `background-color 0.3s ${apple.smooth}, color 0.3s ${apple.smooth}, transform 0.4s ${apple.pop}`,
    "&:hover": { bgcolor: on ? apple.inkHover : "rgba(0,0,0,0.04)", color: on ? "#fff" : apple.text, textDecoration: "none" },
    "&:active": { transform: "scale(0.96)" },
  });

  if (/\/prototype\/\d+\/embed\/?$/.test(path)) {
    return <>{children}</>;
  }

  return (
    <Box
      className="platform"
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: `${rail}px minmax(0,1fr)` },
        minHeight: "100vh",
        bgcolor: apple.page,
        transition: `grid-template-columns 0.35s ${apple.smooth}`,
      }}
    >
      <Link href="#main-content" className="skip-link">Skip to content</Link>
      <Box sx={{ display: { xs: "flex", md: "none" }, alignItems: "center", gap: 1.5, px: 2, py: 1.25, bgcolor: apple.nav, borderBottom: `1px solid ${apple.hairline}` }}>
        <IconButton aria-label="Open navigation" onClick={() => setMobileOpen(true)}><MenuRoundedIcon /></IconButton>
        <Typography sx={{ fontWeight: 700, fontSize: 16 }}>PM Platform</Typography>
        <Typography sx={{ ml: "auto", fontSize: 13, color: apple.muted }}>{LINKS.find((link) => active(link.href))?.label}</Typography>
      </Box>
      <Drawer open={mobileOpen} onClose={() => setMobileOpen(false)} sx={{ display: { md: "none" } }} slotProps={{ paper: { sx: { width: 280, p: 2, bgcolor: apple.nav } } }}>
        <Typography sx={{ p: 1.5, fontWeight: 700 }}>Your workspace</Typography>
        <Box component="nav" aria-label="Mobile navigation">
          {LINKS.map(({ href, label, Icon, group }, index) => <Box key={href}>
            {LINKS[index - 1]?.group !== group ? <Typography className="nav-group">{group}</Typography> : null}
            <Link component={NextLink} href={href} prefetch onClick={() => setMobileOpen(false)} onMouseEnter={() => prefetchSection(href)} onFocus={() => prefetchSection(href)} underline="none" aria-current={active(href) ? "page" : undefined} sx={{ ...navLinkSx(active(href)), gap: 1.25, justifyContent: "flex-start" }}><Icon sx={{ fontSize: 20 }} />{label}</Link>
          </Box>)}
        </Box>
      </Drawer>
      <Box
        component="aside"
        sx={{
          display: { xs: "none", md: "flex" },
          position: "sticky",
          top: 0,
          height: "100vh",
          flexDirection: "column",
          gap: 1.5,
          px: collapsed ? 1 : 2,
          py: 2.5,
          bgcolor: apple.nav,
          backdropFilter: "saturate(180%) blur(20px)",
          WebkitBackdropFilter: "saturate(180%) blur(20px)",
          borderRight: `1px solid ${apple.hairline}`,
          transition: `padding 0.35s ${apple.smooth}, gap 0.35s ${apple.smooth}`,
        }}
      >
        <Stack direction="row" alignItems="flex-start" justifyContent={collapsed ? "center" : "space-between"} spacing={1}>
          {collapsed ? null : (
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em", color: apple.text }}>PM Platform</Typography>
              <Typography sx={{ mt: 0.5, fontSize: 12, color: apple.muted }}>Product workspace</Typography>
            </Box>
          )}
          <Tooltip title={collapsed ? "Expand nav" : "Collapse nav"}>
            <IconButton
              size="small"
              onClick={toggleCollapsed}
              aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
              sx={{
                border: `1px solid ${apple.hairline}`,
                bgcolor: apple.page,
                "&:hover": { bgcolor: apple.hoverFill },
              }}
            >
              {collapsed ? <ChevronRightRoundedIcon fontSize="small" /> : <ChevronLeftRoundedIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Stack>
        <Stack component="nav" aria-label="Main navigation" spacing={0.5} sx={{ overflow: "auto", flex: 1 }}>
          {LINKS.map((link, index) => {
            const on = active(link.href);
            const Icon = link.Icon;
            const body = (
              <Link component={NextLink} href={link.href} prefetch underline="none" onMouseEnter={() => prefetchSection(link.href)} onFocus={() => prefetchSection(link.href)} sx={navLinkSx(on)} aria-label={link.label} aria-current={on ? "page" : undefined}>
                <Icon sx={{ fontSize: 20, flexShrink: 0 }} />
                {collapsed ? null : link.label}
              </Link>
            );
            return collapsed ? (
              <Tooltip key={link.href} title={link.label} placement="right">
                <Box>{body}</Box>
              </Tooltip>
            ) : (
              <Box key={link.href}>{LINKS[index - 1]?.group !== link.group ? <Typography className="nav-group">{link.group}</Typography> : null}{body}</Box>
            );
          })}
        </Stack>
        <Tooltip title={`Jira: ${health.jira == null ? "checking" : health.jira ? "connected" : "offline"} · Cliq: ${health.cliq == null ? "checking" : health.cliq ? "connected" : "offline"} · AI: ${health.llm == null ? "checking" : health.llm ? "available" : "offline"}`}>
          <Link component={NextLink} href="/settings" underline="none" aria-label="View connection status" sx={{ display: "flex", alignItems: "center", gap: 1, fontSize: 11, color: apple.muted, px: 1 }}>
            <ConnectionDots jira={health.jira} cliq={health.cliq} llm={health.llm} />
            {!collapsed ? (Object.keys(health).length ? `${[health.jira, health.cliq, health.llm].filter(Boolean).length} of 3 connections ready` : "Checking connections…") : null}
          </Link>
        </Tooltip>
        <Stack direction="row" spacing={1.25} alignItems="center" sx={{ borderTop: `1px solid ${apple.hairline}`, pt: 2 }}>
          <Avatar sx={{ width: 32, height: 32, bgcolor: apple.ink, fontSize: 13 }}>{firstName.slice(0, 2).toUpperCase()}</Avatar>
          {!collapsed ? <Box><Typography sx={{ fontSize: 13, fontWeight: 600 }}>{firstName}</Typography><Typography sx={{ fontSize: 11, color: apple.muted }}>Personal workspace</Typography></Box> : null}
        </Stack>
      </Box>
      <Box id="main-content" tabIndex={-1} component="main" className="workspace" sx={{ minWidth: 0, bgcolor: apple.page, height: studioCanvas ? "100vh" : "auto", overflow: studioCanvas ? "hidden" : "auto", overflowX: "hidden" }}>
        {studioCanvas ? null : (
          <Suspense fallback={null}>
            <PulseBar />
          </Suspense>
        )}
        {stash ? (
          <Box sx={{ px: { xs: 2, md: 3, xl: 4 }, pt: 2 }}>
            <Banner severity="warning">
              Local code changes are saved in a stash{stash.branch ? ` on ${stash.branch}` : ""}. <Link component={NextLink} href="/codebase" sx={{ fontWeight: 600 }}>Review in Codebase</Link>
            </Banner>
          </Box>
        ) : null}
        {children}
        <CopilotWidget />
      </Box>
    </Box>
  );
}
