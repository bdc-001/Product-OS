import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import type { ReactNode } from "react";
import { apple, lightPalette } from "@/app/ui/tokens";

const POINTS = [
  { title: "Connect once", body: "Jira, Cliq, Git, Google and your AI models live in one encrypted place per workspace." },
  { title: "Run any pipeline", body: "Briefings, release notes, campaigns, films and avatar videos, each with live run history." },
  { title: "Bring your team", body: "Invite people, set roles, and keep every workspace's data separate." },
];

export const clerkAppearance = {
  variables: {
    colorPrimary: lightPalette.ink,
    colorText: lightPalette.text,
    colorTextSecondary: lightPalette.muted,
    colorBackground: lightPalette.raised,
    colorInputBackground: lightPalette.raised,
    borderRadius: "10px",
    fontFamily: "inherit",
  },
  elements: {
    card: { boxShadow: "none", border: `1px solid ${lightPalette.hairline}` },
    formButtonPrimary: { textTransform: "none", fontWeight: 600 },
  },
} as const;

export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <Box sx={{ minHeight: "100vh", display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0,1fr) minmax(0,1fr)" }, bgcolor: apple.page }}>
      <Box
        sx={{
          display: { xs: "none", md: "flex" },
          flexDirection: "column",
          justifyContent: "space-between",
          p: 6,
          color: "#fff",
          background: "radial-gradient(120% 90% at 0% 0%, #3a2f8f 0%, transparent 55%), radial-gradient(90% 80% at 100% 100%, #0f6b5c 0%, transparent 60%), #111114",
        }}
      >
        <Typography sx={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em" }}>Product OS</Typography>
        <Box sx={{ maxWidth: 440 }}>
          <Typography component="h1" sx={{ fontSize: 40, fontWeight: 650, letterSpacing: "-0.035em", lineHeight: 1.08 }}>
            Your product work, run as pipelines.
          </Typography>
          <Box sx={{ mt: 5, display: "grid", gap: 3 }}>
            {POINTS.map((point) => (
              <Box key={point.title}>
                <Typography sx={{ fontWeight: 600, fontSize: 15 }}>{point.title}</Typography>
                <Typography sx={{ mt: 0.5, fontSize: 14, color: "rgba(255,255,255,0.72)", lineHeight: 1.5 }}>{point.body}</Typography>
              </Box>
            ))}
          </Box>
        </Box>
        <Typography sx={{ fontSize: 12, color: "rgba(255,255,255,0.55)" }}>Each workspace keeps its own connections, data and runs.</Typography>
      </Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", p: { xs: 3, md: 6 } }}>{children}</Box>
    </Box>
  );
}
