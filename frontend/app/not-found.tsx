"use client";

import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { FrostCard, PillButton } from "@/app/ui";

export default function NotFoundPage() {
  return (
    <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 680, mx: "auto", mt: 6 }}>
      <FrostCard>
        <Typography variant="h2" sx={{ mb: 1 }}>This page isn’t in the workspace</Typography>
        <Typography sx={{ color: "text.secondary", fontSize: 15, mb: 3 }}>
          The address may be out of date. Return to your overview or open a module from the navigation.
        </Typography>
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          <PillButton href="/">Go to overview</PillButton>
          <PillButton variant="gray" href="/jira">Open Jira</PillButton>
        </Box>
      </FrostCard>
    </Box>
  );
}
