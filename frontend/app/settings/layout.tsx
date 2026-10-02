"use client";

import Box from "@mui/material/Box";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { SETTINGS_LINKS, settingsSection } from "@/app/navigation";
import { apple } from "@/app/ui/tokens";
import { prefetchSection } from "@/lib/prefetch";

const GROUPS = Array.from(new Set(SETTINGS_LINKS.map((link) => link.group)));

export default function SettingsLayout({ children }: { children: ReactNode }) {
  const path = usePathname() || "/settings";
  const active = settingsSection(path)?.href;
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "minmax(0,1fr)", lg: "220px minmax(0,1fr)" }, minWidth: 0 }}>
      <Box
        component="nav"
        aria-label="Settings sections"
        sx={{
          px: { xs: 2, lg: 1.5 },
          py: { xs: 1.5, lg: 3 },
          borderRight: { lg: `1px solid ${apple.hairline}` },
          borderBottom: { xs: `1px solid ${apple.hairline}`, lg: 0 },
          alignSelf: "stretch",
          display: "flex",
          flexDirection: { xs: "row", lg: "column" },
          gap: { xs: 0.5, lg: 2 },
          overflowX: { xs: "auto", lg: "visible" },
        }}
      >
        {GROUPS.map((group) => (
          <Box key={group} sx={{ display: "flex", flexDirection: { xs: "row", lg: "column" }, gap: 0.25, flexShrink: 0 }}>
            <Typography sx={{ display: { xs: "none", lg: "block" }, px: 1.25, pb: 0.5, fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: apple.muted }}>{group}</Typography>
            {SETTINGS_LINKS.filter((link) => link.group === group).map((item) => {
              const on = active === item.href;
              const Icon = item.Icon;
              return (
                <Link
                  key={item.href}
                  component={NextLink}
                  prefetch
                  href={item.href}
                  underline="none"
                  onPointerDown={() => prefetchSection(item.href)}
                  onMouseEnter={() => prefetchSection(item.href)}
                  aria-current={on ? "page" : undefined}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    px: 1.25,
                    py: 0.75,
                    borderRadius: "10px",
                    fontSize: 13.5,
                    whiteSpace: "nowrap",
                    color: on ? apple.text : apple.muted,
                    bgcolor: on ? apple.raised : "transparent",
                    boxShadow: on ? `0 0 0 1px ${apple.hairline}` : "none",
                    fontWeight: on ? 600 : 450,
                    transition: `background-color 0.2s ${apple.smooth}, color 0.2s ${apple.smooth}`,
                    "&:hover": { bgcolor: on ? apple.raised : apple.selFill, color: apple.text },
                  }}
                >
                  <Icon sx={{ fontSize: 17 }} />
                  {item.label}
                </Link>
              );
            })}
          </Box>
        ))}
      </Box>
      <Box sx={{ minWidth: 0 }}>{children}</Box>
    </Box>
  );
}
