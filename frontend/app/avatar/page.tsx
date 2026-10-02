"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import Box from "@mui/material/Box";
import Link from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { VideoEditor } from "@/app/avatar/editor";
import { errorText, mk, seconds, statusTone, thumbnail, videoTitle } from "@/app/avatar/shared";
import { VideoViewer } from "@/app/avatar/viewer";
import { usePlatform } from "@/app/platform-state";
import { AppDialog, Banner, LoadingBlock, PageBody, PillButton, Segmented } from "@/app/ui";
import { PipelineIcon, ToneChip, relativeTime, requirementHref } from "@/app/ui/platform";
import { apple, pmm } from "@/app/ui/tokens";
import { avatarApi, isEditable, isRendering, type AvatarVideo, type AvatarWorkspace, type VoiceRef } from "@/lib/avatar";

const POLL_MS = 8000;

function Service({ label, on, detail, provider }: { label: string; on: boolean; detail?: string; provider: string }) {
  const body = (
    <Box component="span" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, px: 1.1, py: 0.45, borderRadius: 999, border: `1px solid ${apple.hairline}`, bgcolor: apple.raised, fontSize: 12.5, fontWeight: 600, color: on ? apple.text : apple.muted, whiteSpace: "nowrap" }}>
      <Box component="span" sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: on ? pmm.green : apple.hairlineHover }} />
      {label}
      {detail ? <Box component="span" sx={{ fontWeight: 500, color: apple.muted }}>· {detail}</Box> : null}
    </Box>
  );
  if (on) return body;
  return (
    <Link component={NextLink} href={requirementHref(provider)} underline="none" title={`Connect ${label}`}>
      {body}
    </Link>
  );
}

function balanceLabel(ws: AvatarWorkspace) {
  const { account } = ws;
  if (!account.configured) return "not connected";
  if (!account.reachable) return "unreachable";
  if (account.balance == null) return "";
  return `${account.balance.toLocaleString()}${account.currency ? ` ${account.currency}` : ""} left`;
}

function Hero({ ws, onNew }: { ws: AvatarWorkspace; onNew: () => void }) {
  return (
    <Box
      component="section"
      aria-label="Avatar studio"
      sx={{
        mb: 3,
        p: { xs: 2.25, md: 2.75 },
        borderRadius: "20px",
        border: `1px solid ${apple.hairline}`,
        background: `radial-gradient(110% 160% at 0% 0%, ${mk.fill} 0%, transparent 55%), ${apple.raised}`,
        display: "flex",
        gap: 2,
        alignItems: "flex-start",
        flexWrap: "wrap",
      }}
    >
      <PipelineIcon icon="avatar" category="marketing" size={48} />
      <Box sx={{ flex: "1 1 360px", minWidth: 0 }}>
        <Typography component="h1" sx={{ fontSize: 21, fontWeight: 650, letterSpacing: "-0.02em" }}>
          Avatar studio
        </Typography>
        <Typography sx={{ mt: 0.5, fontSize: 14, color: apple.muted, lineHeight: 1.55, maxWidth: 680 }}>
          Presenter videos from your own photo avatar and voice. Pick a presenter and voice, write or draft the script, preview the narration, then render in HeyGen.
        </Typography>
        <Box sx={{ mt: 1.5, display: "flex", gap: 0.75, flexWrap: "wrap" }}>
          <Service label="HeyGen" provider="heygen" on={ws.account.configured && ws.account.reachable} detail={balanceLabel(ws)} />
          <Service label="Cartesia" provider="cartesia" on={ws.narrators.cartesia} />
          <Service label="ElevenLabs" provider="elevenlabs" on={ws.narrators.elevenlabs} />
          <Service label="AI script writer" provider="llm" on={ws.script_ready} />
        </Box>
      </Box>
      <PillButton startIcon={<AddRoundedIcon />} onClick={onNew}>
        New video
      </PillButton>
    </Box>
  );
}

function VideoRow({ video, selected, href }: { video: AvatarVideo; selected: boolean; href: string }) {
  const image = thumbnail(video);
  const tone = statusTone(video.status);
  return (
    <Box
      component={NextLink}
      href={href}
      scroll={false}
      aria-current={selected ? "page" : undefined}
      sx={{
        display: "flex",
        gap: 1.25,
        alignItems: "center",
        p: 1,
        borderRadius: "12px",
        textDecoration: "none",
        color: "inherit",
        bgcolor: selected ? apple.selFill : "transparent",
        boxShadow: selected ? `inset 3px 0 0 ${mk.main}` : "none",
        transition: `background-color 0.2s ${apple.smooth}`,
        "&:hover": { bgcolor: selected ? apple.selFill : apple.hoverFill },
        "&:focus-visible": { outline: `2px solid ${apple.ink}`, outlineOffset: 1 },
      }}
    >
      <Box sx={{ width: 46, height: 46, borderRadius: "10px", overflow: "hidden", bgcolor: apple.hoverFill, flexShrink: 0 }}>
        {image ? <Box component="img" src={image} alt="" loading="lazy" sx={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} /> : null}
      </Box>
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography noWrap sx={{ fontSize: 13.5, fontWeight: 600 }}>
          {videoTitle(video)}
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mt: 0.25, minWidth: 0 }}>
          <ToneChip tone={tone} size="sm" />
          <Typography noWrap sx={{ fontSize: 11.5, color: apple.muted }}>
            {[video.duration != null ? seconds(video.duration) : video.words ? `~${seconds(video.estimated_seconds)}` : "", relativeTime(video.updated_at || video.created_at)].filter(Boolean).join(" · ")}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

type Filter = "all" | "draft" | "ready";

function Library({ videos, selected, creating, onNew }: { videos: AvatarVideo[]; selected: number | null; creating: boolean; onNew: () => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const shown = videos.filter((video) => (filter === "all" ? true : filter === "ready" ? video.status === "completed" : isEditable(video) || isRendering(video)));
  const ready = videos.filter((video) => video.status === "completed").length;
  return (
    <Box component="nav" aria-label="Avatar videos" sx={{ position: { lg: "sticky" }, top: { lg: 16 }, display: "grid", gap: 1.25 }}>
      <Segmented
        value={filter}
        onChange={(id) => setFilter(id as Filter)}
        options={[
          { id: "all", label: `All ${videos.length}` },
          { id: "draft", label: `In progress ${videos.length - ready}` },
          { id: "ready", label: `Ready ${ready}` },
        ]}
      />
      <Box sx={{ display: "grid", gap: 0.25, maxHeight: { xs: 280, lg: "calc(100vh - 220px)" }, overflow: "auto", pr: 0.5 }}>
        {creating ? (
          <Box sx={{ display: "flex", gap: 1.25, alignItems: "center", p: 1, borderRadius: "12px", bgcolor: apple.selFill, boxShadow: `inset 3px 0 0 ${mk.main}` }}>
            <Box sx={{ width: 46, height: 46, borderRadius: "10px", display: "grid", placeItems: "center", bgcolor: mk.fill, color: mk.main }}>
              <AddRoundedIcon />
            </Box>
            <Typography sx={{ fontSize: 13.5, fontWeight: 600 }}>New video</Typography>
          </Box>
        ) : null}
        {shown.map((video) => (
          <VideoRow key={video.id} video={video} selected={video.id === selected} href={`/avatar?video=${video.id}`} />
        ))}
        {!shown.length && !creating ? (
          <Box sx={{ p: 2, textAlign: "center" }}>
            <Typography sx={{ fontSize: 13, color: apple.muted, mb: 1 }}>{filter === "ready" ? "No finished videos yet." : "Nothing here yet."}</Typography>
            <PillButton size="small" variant="gray" onClick={onNew}>
              Start a video
            </PillButton>
          </Box>
        ) : null}
      </Box>
    </Box>
  );
}

function Studio() {
  const router = useRouter();
  const pathname = usePathname() || "/avatar";
  const params = useSearchParams();
  const { notify } = usePlatform();
  const [ws, setWs] = useState<AvatarWorkspace | null>(null);
  const [error, setError] = useState("");
  const [cloned, setCloned] = useState<VoiceRef[]>([]);
  const [removing, setRemoving] = useState<AvatarVideo | null>(null);
  const [deleting, setDeleting] = useState(false);
  const statuses = useRef<Map<number, string>>(new Map());

  const absorb = useCallback(
    (next: AvatarWorkspace) => {
      for (const video of next.videos) {
        const before = statuses.current.get(video.id);
        if (before && before !== video.status && isRendering({ status: before as AvatarVideo["status"] })) {
          if (video.status === "completed") notify(`"${videoTitle(video)}" is ready.`, { tone: "success", href: `/avatar?video=${video.id}`, action: "Watch" });
          if (video.status === "failed") notify(`"${videoTitle(video)}" failed to render.`, { tone: "error", href: `/avatar?video=${video.id}`, action: "Open" });
        }
        statuses.current.set(video.id, video.status);
      }
      setWs(next);
    },
    [notify],
  );

  const load = useCallback(async () => {
    try {
      absorb(await avatarApi.workspace());
      setError("");
    } catch (err) {
      setError(errorText(err, "Could not load the avatar studio."));
    }
  }, [absorb]);

  useEffect(() => {
    void load();
  }, [load]);

  const active = Boolean(ws?.videos.some((video) => isRendering(video)));
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) void load();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [active, load]);

  const param = params.get("video");
  const videos = useMemo(() => ws?.videos ?? [], [ws]);
  const creating = param === "new" || (!param && Boolean(ws) && !videos.length);
  const selected = creating ? null : videos.find((video) => String(video.id) === param) ?? (param ? null : videos[0] ?? null);
  const missing = Boolean(ws && param && param !== "new" && !selected);

  const go = useCallback((value: string) => router.replace(`${pathname}?video=${value}`, { scroll: false }), [pathname, router]);

  const upsert = useCallback((video: AvatarVideo) => {
    statuses.current.set(video.id, video.status);
    setWs((current) => {
      if (!current) return current;
      const exists = current.videos.some((item) => item.id === video.id);
      return { ...current, videos: exists ? current.videos.map((item) => (item.id === video.id ? video : item)) : [video, ...current.videos] };
    });
  }, []);

  const voices = useMemo(() => {
    const seen = new Set<string>();
    const list: VoiceRef[] = [];
    for (const voice of [ws?.default_voice, ...cloned, ...videos.map((video) => video.voice)]) {
      if (!voice?.id || seen.has(voice.id)) continue;
      seen.add(voice.id);
      list.push({ id: voice.id, name: voice.name });
    }
    return list;
  }, [cloned, videos, ws?.default_voice]);

  const duplicate = async (video: AvatarVideo) => {
    try {
      const copy = await avatarApi.duplicate(video.id);
      upsert(copy);
      go(String(copy.id));
    } catch (err) {
      notify(errorText(err), { tone: "error" });
    }
  };

  const remove = async () => {
    if (!removing) return;
    setDeleting(true);
    try {
      await avatarApi.remove(removing.id);
      const rest = videos.filter((video) => video.id !== removing.id);
      setWs((current) => (current ? { ...current, videos: rest } : current));
      setRemoving(null);
      go(rest[0] ? String(rest[0].id) : "new");
    } catch (err) {
      notify(errorText(err), { tone: "error" });
    } finally {
      setDeleting(false);
    }
  };

  if (!ws) {
    return (
      <PageBody>
        {error ? (
          <Banner severity="error">
            {error}{" "}
            <PillButton size="small" variant="text" onClick={() => void load()}>
              Retry
            </PillButton>
          </Banner>
        ) : (
          <LoadingBlock rows={3} height={120} label="Loading avatar studio" />
        )}
      </PageBody>
    );
  }

  return (
    <PageBody>
      <Hero ws={ws} onNew={() => go("new")} />
      {ws.account.configured && !ws.account.reachable ? <Banner severity="warning">HeyGen did not respond: {ws.account.error || "check the API key in Connections."}</Banner> : null}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "280px minmax(0, 1fr)" }, gap: { xs: 2.5, lg: 3.5 }, alignItems: "start" }}>
        <Library videos={videos} selected={selected?.id ?? null} creating={creating} onNew={() => go("new")} />
        <Box sx={{ minWidth: 0 }}>
          {missing ? (
            <Banner severity="info">
              That video no longer exists.{" "}
              <PillButton size="small" variant="text" onClick={() => go("new")}>
                Start a new one
              </PillButton>
            </Banner>
          ) : creating || (selected && isEditable(selected)) ? (
            <VideoEditor
              key={selected?.id ?? "new"}
              ws={ws}
              video={selected}
              voices={voices}
              onChange={upsert}
              onCreated={(video) => {
                upsert(video);
                go(String(video.id));
              }}
              onCloned={(voice) => setCloned((current) => [voice, ...current.filter((item) => item.id !== voice.id)])}
              onDelete={selected ? () => setRemoving(selected) : undefined}
            />
          ) : selected ? (
            <VideoViewer video={selected} onChange={upsert} onDuplicate={() => void duplicate(selected)} onDelete={() => setRemoving(selected)} />
          ) : null}
        </Box>
      </Box>
      <AppDialog
        open={Boolean(removing)}
        onClose={() => !deleting && setRemoving(null)}
        title="Delete this video?"
        titleId="delete-avatar-video"
        maxWidth="xs"
        actions={
          <>
            <PillButton variant="text" onClick={() => setRemoving(null)} disabled={deleting}>
              Keep it
            </PillButton>
            <PillButton onClick={() => void remove()} disabled={deleting} sx={{ bgcolor: apple.danger, "&:hover": { bgcolor: apple.danger } }}>
              {deleting ? "Deleting…" : "Delete"}
            </PillButton>
          </>
        }
      >
        <Typography sx={{ fontSize: 14, color: apple.muted, lineHeight: 1.55 }}>
          {removing ? `"${videoTitle(removing)}"` : "This video"} and its files are removed from this workspace. Anything already in HeyGen stays in your HeyGen account.
        </Typography>
      </AppDialog>
    </PageBody>
  );
}

export default function AvatarPage() {
  return (
    <Suspense fallback={<PageBody><LoadingBlock rows={3} height={120} label="Loading avatar studio" /></PageBody>}>
      <Studio />
    </Suspense>
  );
}
