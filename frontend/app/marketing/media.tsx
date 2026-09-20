"use client";

import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import MovieOutlinedIcon from "@mui/icons-material/MovieOutlined";
import Stack from "@/app/ui/stack";
import { marketingApi, type Campaign, type MarketingAsset } from "@/lib/marketing";

export function parseRefs(raw: string): string[] {
  return (raw || "")
    .split(/[\n;]+/)
    .map((part) => part.replace(/^[-•*]+\s*/, "").replace(/\s{2,}/g, " ").trim())
    .filter((part) => part && !/^[-–—]+$/.test(part));
}

function basename(value: string) {
  try {
    if (/^https?:\/\//i.test(value)) {
      const url = new URL(value);
      const last = url.pathname.split("/").filter(Boolean).pop() || url.hostname;
      return decodeURIComponent(last);
    }
  } catch {
    /* keep the original label */
  }
  return value.split(/[/\\]/).pop() || value;
}

function isAssetRef(value: string) {
  return /\.(mp4|mov|webm|m4v|mkv)(\b|$)/i.test(value) || /^https?:\/\//i.test(value);
}

const clamp = { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" } as const;

export function VideoChips({ value, empty = "—" }: { value: string; empty?: string }) {
  const parts = parseRefs(value);
  const assets = parts.filter(isAssetRef);
  if (!assets.length) {
    const note = parts.join(" ").trim();
    if (!note) return <Typography variant="caption" color="text.secondary">{empty}</Typography>;
    return <Typography variant="caption" title={note} sx={{ ...clamp, color: "text.secondary" }}>{note}</Typography>;
  }
  return (
    <Stack direction="row" flexWrap="wrap" spacing={0.5} sx={{ rowGap: 0.5 }}>
      {assets.map((item, index) => {
        const chip = (
          <Chip
            size="small"
            icon={<MovieOutlinedIcon sx={{ fontSize: "14px !important" }} />}
            label={basename(item)}
            sx={{ maxWidth: 168, height: 24, bgcolor: "#f4f6f8", "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" } }}
          />
        );
        return /^https?:\/\//i.test(item) ? (
          <Link key={`${item}-${index}`} href={item} target="_blank" rel="noreferrer" underline="none">{chip}</Link>
        ) : (
          <Box key={`${item}-${index}`}>{chip}</Box>
        );
      })}
    </Stack>
  );
}

function isPortrait(asset: MarketingAsset) {
  const name = asset.filename.toLowerCase();
  return name.includes("portrait") || name.includes("short") || name.includes("9x16") || name.includes("9-16");
}

export function VideoStage({ campaign, assets }: { campaign: Campaign; assets: MarketingAsset[] }) {
  const videos = assets.filter((asset) => asset.mime === "video/mp4");
  if (!videos.length) {
    return <Alert severity="info">Video has not finished rendering. The shot list stays collapsed below when a script exists.</Alert>;
  }
  const landscape = videos.filter((asset) => !isPortrait(asset));
  const portrait = videos.filter(isPortrait);
  const mixed = landscape.length > 0 && portrait.length > 0;
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: mixed ? "minmax(0, 1fr) 220px" : "minmax(0, 1fr)" },
        gap: 2,
        alignItems: "start",
      }}
    >
      {landscape.length > 0 && (
        <Stack spacing={1.5} sx={{ minWidth: 0 }}>
          {landscape.map((asset) => (
            <Clip key={asset.filename} campaign={campaign} asset={asset} portrait={false} />
          ))}
        </Stack>
      )}
      {portrait.length > 0 && (
        <Stack spacing={1.5} sx={{ minWidth: 0, maxWidth: { md: mixed ? 220 : 280 } }}>
          {portrait.map((asset) => (
            <Clip key={asset.filename} campaign={campaign} asset={asset} portrait />
          ))}
        </Stack>
      )}
    </Box>
  );
}

function Clip({ campaign, asset, portrait }: { campaign: Campaign; asset: MarketingAsset; portrait: boolean }) {
  return (
    <Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" sx={{ display: "block", mb: 0.75 }}>{portrait ? "Portrait · 9:16" : "Landscape · 16:9"}</Typography>
      <Box
        component="video"
        controls
        playsInline
        preload="metadata"
        src={marketingApi.file(campaign.id, asset.filename)}
        sx={{
          display: "block",
          width: "100%",
          maxHeight: portrait ? 420 : 360,
          aspectRatio: portrait ? "9 / 16" : "16 / 9",
          objectFit: "contain",
          bgcolor: "#111",
          borderRadius: 2,
        }}
      />
    </Box>
  );
}

export function SceneList({ scenes }: { scenes?: { headline: string; body?: string; narration?: string }[] }) {
  if (!scenes?.length) return null;
  return (
    <Accordion disableGutters elevation={0} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, "&:before": { display: "none" } }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="body2">Shot list · {scenes.length} scenes</Typography>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={1.5}>
          {scenes.map((scene, index) => (
            <Box key={`${scene.headline}-${index}`}>
              <Typography variant="caption">Scene {index + 1}</Typography>
              <Typography sx={{ fontWeight: 600 }}>{scene.headline}</Typography>
              {scene.body ? <Typography color="text.secondary" variant="body2">{scene.body}</Typography> : null}
              {scene.narration ? <Typography variant="body2" sx={{ mt: 0.5 }}>Narration: {scene.narration}</Typography> : null}
            </Box>
          ))}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}
