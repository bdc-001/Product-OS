"use client";

import { useState } from "react";
import Box from "@mui/material/Box";
import LinearProgress from "@mui/material/LinearProgress";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import {
  AppDialog,
  Banner,
  ConnectionDots,
  EmptyState,
  FrostCard,
  KnowledgeList,
  KnowledgeSplit,
  ListRow,
  LoadingBlock,
  ModuleIntro,
  PageBody,
  PageHeader,
  PillButton,
  QuietDot,
  Segmented,
  SideDrawer,
  StatusChip,
} from "@/app/ui";
import Stack from "@/app/ui/stack";
import { apple, pmm, radius, space } from "@/app/ui/tokens";

function Swatch({ color, name, note }: { color: string; name: string; note?: string }) {
  return (
    <Box sx={{ minWidth: 120 }}>
      <Box sx={{ height: 48, borderRadius: `${radius.md}px`, bgcolor: color, border: `1px solid ${apple.hairline}`, mb: 1 }} />
      <Typography sx={{ fontSize: 12, fontWeight: 600 }}>{name}</Typography>
      <Typography sx={{ fontSize: 11, color: apple.muted, fontFamily: "ui-monospace, monospace" }}>{color}</Typography>
      {note ? <Typography sx={{ fontSize: 11, color: apple.muted }}>{note}</Typography> : null}
    </Box>
  );
}

export default function DesignGalleryPage() {
  const [segment, setSegment] = useState("rest");
  const [dialog, setDialog] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [row, setRow] = useState("a");

  return (
    <PageBody>
      <PageHeader title="Design system" subtitle="Unlisted gallery. Product chrome is Apple ink. Product Marketing keeps a second language. Copilot is a floating chat widget." />
      <ModuleIntro>
        <Typography color="text.secondary">Kit at rest, hover, focus, empty, and loading. Not a product module.</Typography>
        <Stack direction="row" spacing={1}>
          <PillButton variant="gray" onClick={() => setDialog(true)}>Open dialog</PillButton>
          <PillButton variant="gray" onClick={() => setDrawer(true)}>Open drawer</PillButton>
        </Stack>
      </ModuleIntro>

      <Typography variant="h2" sx={{ mb: 1.5 }}>Product ink</Typography>
      <Stack direction="row" flexWrap="wrap" useFlexGap spacing={2} sx={{ mb: 4 }}>
        <Swatch color={apple.ink} name="ink" />
        <Swatch color={apple.text} name="text" />
        <Swatch color={apple.muted} name="muted" />
        <Swatch color={apple.hairline} name="hairline" />
        <Swatch color={apple.wash} name="wash" />
        <Swatch color={apple.hoverFill} name="hoverFill" />
        <Swatch color={apple.danger} name="danger" />
        <Swatch color={apple.page} name="page" />
      </Stack>

      <Typography variant="h2" sx={{ mb: 1.5 }}>Product Marketing only</Typography>
      <Stack direction="row" flexWrap="wrap" useFlexGap spacing={2} sx={{ mb: 4 }}>
        <Swatch color={pmm.blue} name="pmm.blue" note="Do not use on Shell, Pulse, Jira, Cliq, Copilot" />
        <Swatch color={pmm.blueDeep} name="pmm.blueDeep" />
        <Swatch color={pmm.green} name="pmm.green" />
        <Swatch color={pmm.amber} name="pmm.amber" />
        <Swatch color={pmm.blueFill} name="pmm.blueFill" />
        <Swatch color={pmm.greenFill} name="pmm.greenFill" />
        <Swatch color={pmm.amberFill} name="pmm.amberFill" />
      </Stack>

      <Typography variant="h2" sx={{ mb: 1.5 }}>Radius and space</Typography>
      <Stack direction="row" spacing={2} sx={{ mb: 4 }} alignItems="flex-end">
        {([7, 9, 12, 14, 16, 18, 22] as const).map((value) => (
          <Box key={value} sx={{ width: 48, height: 48, border: `1px solid ${apple.hairline}`, borderRadius: `${value}px`, bgcolor: apple.hoverFill }} title={`${value}px`} />
        ))}
        <Typography sx={{ fontSize: 12, color: apple.muted }}>space xs {space.xs} · md {space.md} · xl {space.xl} · xxl {space.xxl}</Typography>
      </Stack>

      <Typography variant="h2" sx={{ mb: 1.5 }}>Actions</Typography>
      <Typography sx={{ fontSize: 13, color: apple.muted, mb: 1.5 }}>Tab to the filled button for the ink focus ring. Hover the gray button for hairline lift.</Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
        <PillButton>Filled rest</PillButton>
        <PillButton variant="gray">Gray hover</PillButton>
        <PillButton variant="text">Text</PillButton>
        <PillButton disabled>Disabled</PillButton>
      </Stack>
      <Stack direction="row" spacing={1} sx={{ mb: 4 }} alignItems="center">
        <StatusChip label="Default" />
        <StatusChip label="Ink" tone="ink" />
        <StatusChip label="Danger" tone="danger" />
        <QuietDot on label="Indexed" />
        <QuietDot label="Pending" />
        <ConnectionDots jira cliq={false} llm={null} />
      </Stack>

      <Typography variant="h2" sx={{ mb: 1.5 }}>Segmented and cards</Typography>
      <Box sx={{ maxWidth: 360, mb: 2 }}>
        <Segmented value={segment} onChange={setSegment} options={[{ id: "rest", label: "Rest" }, { id: "hover", label: "Hover" }, { id: "focus", label: "Focus" }]} />
      </Box>
      <FrostCard sx={{ mb: 4, maxWidth: 480 }}>
        <Typography variant="h3" sx={{ mb: 1 }}>FrostCard</Typography>
        <Typography color="text.secondary">Hover for the named hairline and shadow. Selected view: {segment}.</Typography>
      </FrostCard>

      <Typography variant="h2" sx={{ mb: 1.5 }}>Empty and loading</Typography>
      <Box sx={{ mb: 2 }}><EmptyState>Nothing in this view yet.</EmptyState></Box>
      <Banner severity="info">Banner at rest for status copy.</Banner>
      <Box sx={{ my: 2 }}><LinearProgress aria-label="Example progress" /></Box>
      <LoadingBlock rows={3} height={56} label="Example loading block" />

      <Typography variant="h2" sx={{ mt: 4, mb: 1.5 }}>Knowledge split</Typography>
      <KnowledgeSplit
        sidebar={
          <KnowledgeList>
            <ListRow selected={row === "a"} onClick={() => setRow("a")}>First item</ListRow>
            <ListRow selected={row === "b"} onClick={() => setRow("b")}>Second item</ListRow>
          </KnowledgeList>
        }
      >
        <FrostCard>
          <TextField size="small" fullWidth label="Focus this field" placeholder="Ink focus ring" />
        </FrostCard>
      </KnowledgeSplit>

      <AppDialog open={dialog} onClose={() => setDialog(false)} title="App dialog" titleId="design-dialog-title">
        <Typography sx={{ mt: 1 }}>Shared overlay for Pulse-style search and confirms.</Typography>
      </AppDialog>
      <SideDrawer open={drawer} onClose={() => setDrawer(false)}>
        <Typography variant="h2">Side drawer</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>Right sheet used for Jira detail and LMS preview.</Typography>
      </SideDrawer>
    </PageBody>
  );
}
