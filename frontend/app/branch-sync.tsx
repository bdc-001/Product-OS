"use client";

import Stack from "@/app/ui/stack";
import Typography from "@mui/material/Typography";
import type { CodebaseStatus } from "@/lib/api";
import { PillButton } from "@/app/ui";
import { apple } from "@/app/theme";

export function BranchSync({ status }: { status: CodebaseStatus | null; page?: string }) {
  const indexed = Boolean(status?.indexed_branch);
  const branch = status?.indexed_branch || "—";
  return (
    <Stack spacing={1} sx={{ mb: 2.5 }}>
      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" alignItems="center">
        <Typography sx={{ fontSize: 15, color: apple.text }}>
          Product {indexed ? branch : "—"}
          {status?.data_branch && status.data_branch !== branch ? ` · data ${status.data_branch}` : ""}
        </Typography>
        <PillButton variant="text" href="/codebase">
          {indexed || status?.data_branch ? "Change" : "Open Codebase"}
        </PillButton>
      </Stack>
      {status?.in_sync === false ? (
        <Typography sx={{ fontSize: 13, color: apple.muted }}>Clone is on {status?.branch}</Typography>
      ) : null}
    </Stack>
  );
}
