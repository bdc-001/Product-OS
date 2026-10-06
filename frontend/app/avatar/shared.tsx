"use client";

import GraphicEqRoundedIcon from "@mui/icons-material/GraphicEqRounded";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { Tone } from "@/app/ui/platform";
import { accent, apple, pmm } from "@/app/ui/tokens";
import { PROVIDER_LABEL, voiceProvider, type AvatarStatus, type AvatarVideo, type VoiceProvider } from "@/lib/avatar";

export const mk = accent.marketing;

export function errorText(error: unknown, fallback = "Something went wrong. Please retry.") {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function statusTone(status: AvatarStatus | string): Tone {
  switch (status) {
    case "draft":
      return { label: "Draft", color: apple.muted, fill: apple.hoverFill };
    case "submitting":
      return { label: "Sending", color: mk.main, fill: mk.fill, live: true };
    case "submitted":
      return { label: "Queued at HeyGen", color: mk.main, fill: mk.fill, live: true };
    case "rendering":
      return { label: "Rendering", color: mk.main, fill: mk.fill, live: true };
    case "downloading":
      return { label: "Saving file", color: mk.main, fill: mk.fill, live: true };
    case "completed":
      return { label: "Ready", color: pmm.green, fill: pmm.greenFill };
    case "failed":
      return { label: "Failed", color: apple.danger, fill: apple.dangerFill };
    default:
      return { label: status || "Unknown", color: apple.muted, fill: apple.hoverFill };
  }
}

export function videoTitle(video: Pick<AvatarVideo, "title" | "id">) {
  return video.title?.trim() || `Untitled video ${video.id}`;
}

export function seconds(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "";
  const total = Math.round(value);
  return total < 60 ? `${total}s` : `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, "0")}s`;
}

export function bytes(size: number | undefined) {
  if (!size) return "";
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / 1024 / 1024).toFixed(size < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

export function thumbnail(video: AvatarVideo) {
  return video.assets.find((asset) => asset.kind === "thumbnail")?.url || video.avatar.preview_url || "";
}

const PROVIDER_TONE: Record<VoiceProvider, { color: string; fill: string }> = {
  cartesia: { color: accent.knowledge.main, fill: accent.knowledge.fill },
  elevenlabs: { color: accent.system.main, fill: accent.system.fill },
  heygen: { color: mk.main, fill: mk.fill },
};

export function VoiceBadge({ id, size = 34 }: { id: string; size?: number }) {
  const tone = PROVIDER_TONE[voiceProvider(id)];
  return (
    <Box aria-hidden sx={{ width: size, height: size, borderRadius: "50%", display: "grid", placeItems: "center", flexShrink: 0, bgcolor: tone.fill, color: tone.color }}>
      <GraphicEqRoundedIcon sx={{ fontSize: Math.round(size * 0.52) }} />
    </Box>
  );
}

export function providerNote(id: string) {
  const provider = voiceProvider(id);
  return provider === "heygen" ? "Spoken inside HeyGen" : `Narrated with ${PROVIDER_LABEL[provider]}, lip-synced in HeyGen`;
}

export function FieldLabel({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <Box sx={{ mb: 0.75 }}>
      <Typography component="div" sx={{ fontSize: 13, fontWeight: 600, color: apple.text }}>
        {children}
      </Typography>
      {hint ? <Typography sx={{ fontSize: 12, color: apple.muted, lineHeight: 1.45 }}>{hint}</Typography> : null}
    </Box>
  );
}

/** One preview plays at a time across a list of voice samples. */
export function useAudioPreview() {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState("");
  useEffect(() => () => audio.current?.pause(), []);
  const toggle = useCallback(
    (id: string, url: string) => {
      if (!url) return;
      audio.current?.pause();
      if (playing === id) {
        setPlaying("");
        return;
      }
      const next = new Audio(url);
      const stop = () => setPlaying((current) => (current === id ? "" : current));
      next.onended = stop;
      next.onerror = stop;
      audio.current = next;
      setPlaying(id);
      void next.play().catch(stop);
    },
    [playing],
  );
  return { playing, toggle };
}

export function DropZone({
  accept,
  multiple,
  onFiles,
  title,
  hint,
  icon,
  disabled,
}: {
  accept: string;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  title: string;
  hint?: string;
  icon: ReactNode;
  disabled?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <Box
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={() => !disabled && input.current?.click()}
      onKeyDown={(event) => {
        if (disabled || (event.key !== "Enter" && event.key !== " ")) return;
        event.preventDefault();
        input.current?.click();
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        if (!disabled) onFiles(Array.from(event.dataTransfer.files));
      }}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        p: 2,
        borderRadius: "14px",
        border: `1.5px dashed ${over ? mk.main : apple.hairlineHover}`,
        bgcolor: over ? mk.fill : apple.hoverFill,
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
        transition: `border-color 0.2s ${apple.smooth}, background-color 0.2s ${apple.smooth}`,
        "&:hover": disabled ? undefined : { borderColor: mk.main },
        "&:focus-visible": { outline: `2px solid ${apple.ink}`, outlineOffset: 2 },
      }}
    >
      <input
        ref={input}
        type="file"
        hidden
        accept={accept}
        multiple={multiple}
        onChange={(event) => {
          onFiles(Array.from(event.target.files || []));
          event.target.value = "";
        }}
      />
      <Box sx={{ width: 40, height: 40, borderRadius: "12px", display: "grid", placeItems: "center", bgcolor: mk.fill, color: mk.main, flexShrink: 0 }}>{icon}</Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{title}</Typography>
        {hint ? <Typography sx={{ fontSize: 12.5, color: apple.muted, lineHeight: 1.45 }}>{hint}</Typography> : null}
      </Box>
    </Box>
  );
}
