"use client";

import ContentCopyRoundedIcon from "@mui/icons-material/ContentCopyRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Collapse from "@mui/material/Collapse";
import Typography from "@mui/material/Typography";
import { useEffect, useState, type ReactNode } from "react";
import { bytes, errorText, mk, providerNote, seconds, statusTone, videoTitle } from "@/app/avatar/shared";
import { Banner, PillButton } from "@/app/ui";
import { ToneChip, absoluteTime, parseUtc } from "@/app/ui/platform";
import { apple, pmm } from "@/app/ui/tokens";
import { PROVIDER_LABEL, avatarApi, isRendering, voiceProvider, type AvatarVideo } from "@/lib/avatar";

const ENGINE_LABEL: Record<string, string> = { avatar_iv: "Avatar IV", avatar_v: "Avatar V", avatar_iii: "Avatar III" };

const STAGES = [
  { label: "Sent to HeyGen", statuses: ["submitting", "submitted"] },
  { label: "Rendering", statuses: ["rendering"] },
  { label: "Saving the file", statuses: ["downloading"] },
  { label: "Ready", statuses: ["completed"] },
];

function useElapsed(from: string | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const start = parseUtc(from)?.getTime();
  return start ? Math.max(0, Math.round((now - start) / 1000)) : null;
}

function RenderProgress({ video, onChange }: { video: AvatarVideo; onChange: (video: AvatarVideo) => void }) {
  const stage = Math.max(0, STAGES.findIndex((item) => item.statuses.includes(video.status)));
  const elapsed = useElapsed(video.submitted_at || video.updated_at);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");

  const check = async () => {
    setChecking(true);
    setError("");
    try {
      onChange(await avatarApi.refresh(video.id));
    } catch (err) {
      setError(errorText(err));
    } finally {
      setChecking(false);
    }
  };

  return (
    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "220px 1fr" }, gap: 3, alignItems: "center", p: { xs: 2, md: 3 }, borderRadius: "20px", border: `1px solid ${apple.hairline}`, background: `radial-gradient(120% 120% at 0% 0%, ${mk.fill} 0%, transparent 60%), ${apple.raised}` }}>
      <Box sx={{ position: "relative", aspectRatio: "3 / 4", borderRadius: "16px", overflow: "hidden", bgcolor: apple.hoverFill, maxWidth: 220 }}>
        {video.avatar.preview_url ? <Box component="img" src={video.avatar.preview_url} alt="" sx={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} /> : null}
        <Box
          aria-hidden
          sx={{
            position: "absolute",
            inset: 0,
            background: `linear-gradient(110deg, transparent 30%, rgba(255,255,255,0.35) 50%, transparent 70%)`,
            backgroundSize: "250% 100%",
            animation: "avatarShimmer 2.4s linear infinite",
            "@keyframes avatarShimmer": { from: { backgroundPosition: "150% 0" }, to: { backgroundPosition: "-100% 0" } },
            "@media (prefers-reduced-motion: reduce)": { animation: "none" },
          }}
        />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontSize: 20, fontWeight: 650, letterSpacing: "-0.02em" }}>HeyGen is making your video</Typography>
        <Typography sx={{ mt: 0.5, fontSize: 13.5, color: apple.muted, lineHeight: 1.55 }}>
          {elapsed != null ? `${seconds(elapsed)} so far. ` : ""}Renders usually take a few minutes. This page checks every few seconds, and the video keeps rendering if you leave.
        </Typography>
        <Box component="ol" sx={{ listStyle: "none", p: 0, m: 0, mt: 2.5, display: "grid", gap: 1.25 }}>
          {STAGES.map((item, index) => {
            const done = index < stage;
            const current = index === stage;
            return (
              <Box component="li" key={item.label} sx={{ display: "flex", alignItems: "center", gap: 1.25 }}>
                <Box
                  aria-hidden
                  className={current ? "live-dot" : undefined}
                  sx={{ width: 12, height: 12, borderRadius: "50%", flexShrink: 0, bgcolor: done ? pmm.green : current ? mk.main : "transparent", border: done || current ? "none" : `1.5px solid ${apple.hairlineHover}` }}
                />
                <Typography sx={{ fontSize: 14, fontWeight: current ? 650 : 500, color: done || current ? apple.text : apple.muted }}>
                  {item.label}
                  {current && video.attempt && video.attempt > 1 ? ` · attempt ${video.attempt}` : ""}
                </Typography>
              </Box>
            );
          })}
        </Box>
        {video.error ? <Typography sx={{ mt: 2, fontSize: 13, color: pmm.amber }}>{video.error}</Typography> : null}
        {error ? <Box sx={{ mt: 2 }}><Banner severity="error">{error}</Banner></Box> : null}
        <Box sx={{ mt: 2.5 }}>
          <PillButton size="small" variant="gray" startIcon={<RefreshRoundedIcon />} onClick={() => void check()} disabled={checking}>
            {checking ? "Checking…" : "Check now"}
          </PillButton>
        </Box>
      </Box>
    </Box>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <Box sx={{ color: apple.muted, fontSize: 13 }}>{label}</Box>
      <Box sx={{ fontSize: 13.5, minWidth: 0, overflowWrap: "anywhere" }}>{children}</Box>
    </>
  );
}

export function VideoViewer({
  video,
  onChange,
  onDuplicate,
  onDelete,
}: {
  video: AvatarVideo;
  onChange: (video: AvatarVideo) => void;
  onDuplicate: () => void;
  onDelete: () => void;
}) {
  const [script, setScript] = useState(false);
  const tone = statusTone(video.status);
  const mp4 = video.assets.find((asset) => asset.kind === "video");
  const captions = video.assets.find((asset) => asset.kind === "captions");
  const still = video.assets.find((asset) => asset.kind === "thumbnail");
  const portrait = video.options.aspect_ratio === "9:16" || video.options.aspect_ratio === "4:5";
  const rendering = isRendering(video);
  const provider = voiceProvider(video.voice.id);

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, flexWrap: "wrap", mb: 2 }}>
        <Typography component="h2" sx={{ fontSize: 21, fontWeight: 650, letterSpacing: "-0.02em", minWidth: 0 }}>
          {videoTitle(video)}
        </Typography>
        <ToneChip tone={tone} size="sm" />
        <Box sx={{ flex: 1 }} />
        {video.video_page_url ? (
          <PillButton size="small" variant="text" href={video.video_page_url} target="_blank" rel="noreferrer" endIcon={<OpenInNewRoundedIcon sx={{ fontSize: 16 }} />}>
            Open in HeyGen
          </PillButton>
        ) : null}
        <PillButton size="small" variant="gray" startIcon={<ContentCopyRoundedIcon />} onClick={onDuplicate}>
          Duplicate and edit
        </PillButton>
        {!rendering ? (
          <PillButton size="small" variant="text" onClick={onDelete} sx={{ color: apple.danger }}>
            Delete
          </PillButton>
        ) : null}
      </Box>

      {rendering ? (
        <RenderProgress video={video} onChange={onChange} />
      ) : (
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: portrait ? "minmax(0, 380px) 1fr" : "minmax(0, 1fr) 300px" }, gap: 3, alignItems: "start" }}>
          <Box sx={{ borderRadius: "18px", overflow: "hidden", bgcolor: "#000", border: `1px solid ${apple.hairline}`, maxWidth: portrait ? 380 : "none" }}>
            {mp4 ? (
              <Box component="video" controls playsInline preload="metadata" poster={still?.url} src={mp4.url} sx={{ display: "block", width: "100%", maxHeight: "72vh", bgcolor: "#000" }} />
            ) : (
              <Box sx={{ aspectRatio: "16 / 9", display: "grid", placeItems: "center", color: "#fff", fontSize: 14 }}>The video file is not available.</Box>
            )}
          </Box>
          <Box sx={{ display: "grid", gap: 2 }}>
            <Box sx={{ p: 2, borderRadius: "16px", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised }}>
              <Typography sx={{ fontSize: 13, fontWeight: 650, mb: 1.25 }}>Downloads</Typography>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                {mp4 ? (
                  <PillButton size="small" href={mp4.url} download={`${videoTitle(video)}.mp4`} startIcon={<DownloadRoundedIcon />}>
                    MP4{mp4.size ? ` · ${bytes(mp4.size)}` : ""}
                  </PillButton>
                ) : null}
                {captions ? (
                  <PillButton size="small" variant="gray" href={captions.url} download={`${videoTitle(video)}.srt`}>
                    Captions (SRT)
                  </PillButton>
                ) : null}
                {still ? (
                  <PillButton size="small" variant="gray" href={still.url} download={still.filename}>
                    Thumbnail
                  </PillButton>
                ) : null}
                {video.narration ? (
                  <PillButton size="small" variant="gray" href={video.narration.url} download={`${videoTitle(video)}-narration.mp3`}>
                    Narration (MP3)
                  </PillButton>
                ) : null}
              </Box>
            </Box>
            <Box sx={{ p: 2, borderRadius: "16px", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised, display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 2, rowGap: 1 }}>
              <Detail label="Presenter">{video.avatar.name || "—"}</Detail>
              <Detail label="Voice">
                {video.voice.name || "Avatar default"}
                <Typography component="span" sx={{ display: "block", fontSize: 12, color: apple.muted }}>
                  {PROVIDER_LABEL[provider]} · {providerNote(video.voice.id).toLowerCase()}
                </Typography>
              </Detail>
              <Detail label="Length">{seconds(video.duration) || `~${seconds(video.estimated_seconds)}`}</Detail>
              <Detail label="Format">
                {video.options.aspect_ratio} · {video.options.resolution} · {ENGINE_LABEL[video.options.engine] || video.options.engine}
              </Detail>
              <Detail label="Speed">{video.options.speed.toFixed(2)}×{video.options.pauses ? " · natural pauses" : ""}</Detail>
              {video.completed_at ? <Detail label="Rendered">{absoluteTime(video.completed_at)}</Detail> : null}
              {video.status === "draft" ? null : video.revision && video.revision > 1 ? <Detail label="Revision">{video.revision}</Detail> : null}
            </Box>
          </Box>
        </Box>
      )}

      <Box sx={{ mt: 3, borderRadius: "16px", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised }}>
        <ButtonBase onClick={() => setScript((open) => !open)} aria-expanded={script} sx={{ width: "100%", justifyContent: "space-between", px: 2, py: 1.5, borderRadius: "16px" }}>
          <Typography sx={{ fontSize: 14, fontWeight: 600 }}>
            Script · {video.words} words
          </Typography>
          <ExpandMoreRoundedIcon sx={{ color: apple.muted, transform: script ? "rotate(180deg)" : "none", transition: `transform 0.25s ${apple.smooth}` }} />
        </ButtonBase>
        <Collapse in={script}>
          <Typography component="div" sx={{ px: 2, pb: 2, fontSize: 14.5, lineHeight: 1.7, whiteSpace: "pre-wrap", color: apple.text }}>
            {video.script}
          </Typography>
        </Collapse>
      </Box>
    </Box>
  );
}