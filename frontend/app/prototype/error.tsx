"use client";

import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { FrostCard, PillButton } from "@/app/ui";

export default function PrototypeError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 680, mx: "auto", mt: 6 }}>
      <FrostCard>
        <Typography variant="h2" sx={{ mb: 1 }}>Studio couldn’t load</Typography>
        <Typography sx={{ color: "text.secondary", fontSize: 15, mb: 3 }}>
          Reload this prototype. The Sense preview stays in this sandbox; nothing is written to go_services.
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <PillButton onClick={reset}>Try again</PillButton>
          <PillButton variant="gray" href="/prototype">All prototypes</PillButton>
        </Box>
      </FrostCard>
    </Box>
  );
}
