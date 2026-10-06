"use client";

import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import GraphicEqRoundedIcon from "@mui/icons-material/GraphicEqRounded";
import MovieCreationOutlinedIcon from "@mui/icons-material/MovieCreationOutlined";
import UndoRoundedIcon from "@mui/icons-material/UndoRounded";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Collapse from "@mui/material/Collapse";
import MenuItem from "@mui/material/MenuItem";
import Slider from "@mui/material/Slider";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AvatarPicker } from "@/app/avatar/avatar-picker";
import { FieldLabel, errorText, mk, seconds } from "@/app/avatar/shared";
import { VoicePicker } from "@/app/avatar/voice-picker";
import { usePlatform } from "@/app/platform-state";
import { AppDialog, Banner, PillButton, Segmented } from "@/app/ui";
import { requirementHref } from "@/app/ui/platform";
import { apple, shadow } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import {
  PROVIDER_LABEL,
  avatarApi,
  videoInput,
  voiceProvider,
  type AspectRatio,
  type AvatarOptions,
  type AvatarVideo,
  type AvatarWorkspace,
  type VideoInput,
  type VoiceProvider,
  type VoiceRef,
} from "@/lib/avatar";

const ENGINE_LABEL: Record<string, string> = { avatar_iv: "Avatar IV", avatar_v: "Avatar V", avatar_iii: "Avatar III" };
const ASPECT_BOX: Record<AspectRatio, [number, number]> = { "16:9": [28, 16], "9:16": [13, 23], "1:1": [19, 19], "4:5": [17, 21], auto: [22, 16] };
const FALLBACK_OPTIONS: AvatarOptions = { aspect_ratio: "16:9", resolution: "1080p", engine: "avatar_iv", speed: 1, background: "", pauses: true, expressiveness: "low", motion_prompt: "" };

function defaults(ws: AvatarWorkspace): AvatarOptions {
  return { ...(ws.options.defaults ?? ws.videos[0]?.options ?? FALLBACK_OPTIONS) };
}

function blankDraft(ws: AvatarWorkspace): VideoInput {
  const last = ws.videos.find((video) => video.avatar.id);
  return {
    title: "",
    feature_id: null,
    script: "",
    avatar_id: last?.avatar.id || "",
    avatar_name: last?.avatar.name || "",
    avatar_type: last?.avatar.type || "",
    avatar_preview_url: last?.avatar.preview_url || "",
    voice_id: ws.default_voice.id,
    voice_name: ws.default_voice.name,
    options: defaults(ws),
  };
}

function Step({ n, title, hint, aside, children }: { n: number; title: string; hint?: ReactNode; aside?: ReactNode; children: ReactNode }) {
  return (
    <Box component="section" aria-labelledby={`avatar-step-${n}`} sx={{ position: "relative", pl: { xs: 0, md: 5.5 }, pb: 3.5 }}>
      <Box aria-hidden sx={{ display: { xs: "none", md: "grid" }, position: "absolute", left: 0, top: 0, width: 30, height: 30, borderRadius: "50%", placeItems: "center", bgcolor: mk.fill, color: mk.main, fontWeight: 700, fontSize: 13 }}>
        {n}
      </Box>
      <Box aria-hidden sx={{ display: { xs: "none", md: "block" }, position: "absolute", left: 14.25, top: 38, bottom: 6, width: 1.5, borderRadius: 1, bgcolor: apple.hairline }} />
      <Box sx={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 1.5, flexWrap: "wrap", mb: 1.25, minHeight: 30 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography id={`avatar-step-${n}`} component="h3" sx={{ fontSize: 16, fontWeight: 650, letterSpacing: "-0.01em" }}>
            {title}
          </Typography>
          {hint ? <Typography sx={{ fontSize: 12.5, color: apple.muted, lineHeight: 1.5 }}>{hint}</Typography> : null}
        </Box>
        {aside}
      </Box>
      <Box sx={{ p: { xs: 1.75, md: 2.25 }, borderRadius: "16px", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised }}>{children}</Box>
    </Box>
  );
}

function AspectChoice({ ratio, selected, onClick }: { ratio: AspectRatio; selected: boolean; onClick: () => void }) {
  const [w, h] = ASPECT_BOX[ratio];
  return (
    <ButtonBase
      onClick={onClick}
      aria-pressed={selected}
      sx={{
        width: 74,
        height: 64,
        borderRadius: "12px",
        display: "flex",
        flexDirection: "column",
        gap: 0.75,
        border: `1.5px solid ${selected ? mk.main : apple.hairline}`,
        bgcolor: selected ? mk.fill : apple.raised,
        color: selected ? mk.main : apple.muted,
        transition: `border-color 0.2s ${apple.smooth}, background-color 0.2s ${apple.smooth}`,
        "&:hover": { borderColor: selected ? mk.main : apple.hairlineHover },
        "&.Mui-focusVisible": { outline: `2px solid ${apple.ink}`, outlineOffset: 2 },
      }}
    >
      <Box aria-hidden sx={{ width: w, height: h, borderRadius: "3px", border: `1.75px ${ratio === "auto" ? "dashed" : "solid"} currentColor` }} />
      <Typography sx={{ fontSize: 12, fontWeight: 600, color: selected ? mk.main : apple.text }}>{ratio === "auto" ? "Auto" : ratio}</Typography>
    </ButtonBase>
  );
}

function ScriptAssist({ ws, onDraft }: { ws: AvatarWorkspace; onDraft: (title: string, script: string) => void }) {
  const [open, setOpen] = useState(false);
  const [feature, setFeature] = useState<number | null>(null);
  const [brief, setBrief] = useState("");
  const [angle, setAngle] = useState("");
  const [length, setLength] = useState(30);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selected = ws.features.find((item) => item.id === feature) ?? null;

  const draft = async () => {
    setBusy(true);
    setError("");
    try {
      const out = await avatarApi.script({ feature_id: feature, brief, seconds: length, angle });
      onDraft(out.title, out.script);
      setOpen(false);
    } catch (err) {
      setError(errorText(err, "The writing model did not return a script."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ mb: 2, borderRadius: "14px", border: `1px solid ${open ? mk.main : apple.hairline}`, bgcolor: open ? mk.fill : "transparent", transition: `background-color 0.2s ${apple.smooth}, border-color 0.2s ${apple.smooth}` }}>
      <ButtonBase onClick={() => setOpen((value) => !value)} aria-expanded={open} sx={{ width: "100%", justifyContent: "flex-start", gap: 1.25, px: 1.75, py: 1.25, borderRadius: "14px", textAlign: "left" }}>
        <AutoAwesomeOutlinedIcon sx={{ color: mk.main, fontSize: 20 }} />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontSize: 14, fontWeight: 600 }}>Draft it with AI</Typography>
          <Typography sx={{ fontSize: 12, color: apple.muted }}>Pick a feature or describe the idea; the writer targets the length you set.</Typography>
        </Box>
        <ExpandMoreRoundedIcon sx={{ color: apple.muted, transform: open ? "rotate(180deg)" : "none", transition: `transform 0.25s ${apple.smooth}` }} />
      </ButtonBase>
      <Collapse in={open}>
        <Box sx={{ px: 1.75, pb: 1.75, display: "grid", gap: 1.5 }}>
          {!ws.script_ready ? (
            <Banner severity="info">
              The script writer needs an AI model. <PillButton size="small" variant="text" href={requirementHref("llm")}>Connect AI models</PillButton>
            </Banner>
          ) : null}
          <Autocomplete
            size="small"
            options={ws.features}
            value={selected}
            onChange={(_, value) => setFeature(value?.id ?? null)}
            groupBy={(option) => option.module || "Other"}
            getOptionLabel={(option) => option.name}
            isOptionEqualToValue={(option, value) => option.id === value.id}
            renderInput={(params) => <TextField {...params} label="Feature (optional)" />}
          />
          <TextField size="small" label="What should the video cover?" placeholder="The problem, who it is for, the one thing viewers should remember" multiline minRows={2} value={brief} onChange={(event) => setBrief(event.target.value.slice(0, 4000))} />
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.5, alignItems: "center" }}>
            <TextField size="small" label="Angle (optional)" placeholder="e.g. founder intro, customer story" value={angle} onChange={(event) => setAngle(event.target.value.slice(0, 500))} />
            <Box sx={{ px: 1 }}>
              <Typography sx={{ fontSize: 12.5, color: apple.muted }}>Length · about {seconds(length)}</Typography>
              <Slider size="small" value={length} min={15} max={180} step={5} onChange={(_, value) => setLength(value as number)} aria-label="Target length in seconds" sx={{ color: mk.main }} />
            </Box>
          </Box>
          {error ? <Banner severity="error">{error}</Banner> : null}
          <Box>
            <PillButton size="small" startIcon={<AutoAwesomeOutlinedIcon />} onClick={() => void draft()} disabled={busy || !ws.script_ready || (!feature && !brief.trim())}>
              {busy ? "Writing…" : "Draft script"}
            </PillButton>
          </Box>
        </Box>
      </Collapse>
    </Box>
  );
}

export function VideoEditor({
  ws,
  video,
  voices,
  onChange,
  onCreated,
  onCloned,
  onDelete,
}: {
  ws: AvatarWorkspace;
  video: AvatarVideo | null;
  voices: VoiceRef[];
  onChange: (video: AvatarVideo) => void;
  onCreated: (video: AvatarVideo) => void;
  onCloned: (voice: VoiceRef) => void;
  onDelete?: () => void;
}) {
  const { notify } = usePlatform();
  const { can } = useWorkspace();
  const [base, setBase] = useState<VideoInput>(() => (video ? videoInput(video) : blankDraft(ws)));
  const [draft, setDraft] = useState<VideoInput>(base);
  const [synced, setSynced] = useState(video?.updated_at ?? "");
  const [busy, setBusy] = useState<"" | "save" | "narration" | "render">("");
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [undo, setUndo] = useState<{ title: string; script: string } | null>(null);

  const stamp = video?.updated_at ?? "";
  if (video && synced !== stamp) {
    const next = videoInput(video);
    setSynced(stamp);
    setBase(next);
    setDraft(next);
  }

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(base), [draft, base]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const set = (patch: Partial<VideoInput>) => setDraft((current) => ({ ...current, ...patch }));
  const setOption = <K extends keyof AvatarOptions>(key: K, value: AvatarOptions[K]) => setDraft((current) => ({ ...current, options: { ...current.options, [key]: value } }));

  const catalog = ws.options;
  const opts = draft.options;
  const words = draft.script.trim() ? draft.script.trim().split(/\s+/).length : 0;
  const estimate = Math.round((words / (catalog.words_per_minute || 150)) * 60 / Math.max(opts.speed || 1, 0.5));
  const chars = draft.script.length;
  const provider = voiceProvider(draft.voice_id);
  const photoControls = opts.engine === "avatar_iv" && draft.avatar_type === "photo_avatar";
  const heygenReady = ws.account.configured;
  const renderBlocker = !heygenReady ? "Connect HeyGen to render." : !draft.avatar_id ? "Choose a presenter first." : words < 3 ? "Write a script first." : chars > catalog.max_script_chars ? "The script is too long for one render." : "";
  const narration = video?.narration ?? null;
  const narrationStale = Boolean(narration && (narration.stale || dirty));

  const persist = async (): Promise<AvatarVideo> => {
    if (video && !dirty) return video;
    const out = video ? await avatarApi.update(video.id, draft) : await avatarApi.create(draft);
    if (video) onChange(out);
    else onCreated(out);
    return out;
  };

  const run = async (kind: "save" | "narration" | "render") => {
    setBusy(kind);
    setError("");
    try {
      const saved = await persist();
      if (kind === "narration") onChange(await avatarApi.narration(saved.id));
      if (kind === "render") {
        const out = await avatarApi.render(saved.id);
        onChange(out);
        notify(`Sent "${out.title || "your video"}" to HeyGen. It keeps rendering if you leave this page.`, { tone: "success" });
      }
      if (kind === "save") notify("Draft saved.", { tone: "success" });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy("");
      setConfirm(false);
    }
  };

  const balance = ws.account.balance;

  return (
    <Box>
      {video?.status === "failed" ? (
        <Banner severity="error">
          {video.error || "HeyGen could not render this video."}
          {video.retry_downloads_only ? (
            <Box sx={{ mt: 1 }}>
              <PillButton size="small" onClick={() => void run("render")} disabled={Boolean(busy)}>
                {busy === "render" ? "Retrying…" : "Retry the download"}
              </PillButton>
              <Typography component="span" sx={{ ml: 1, fontSize: 12.5 }}>HeyGen already rendered this version, so retrying does not render or charge again.</Typography>
            </Box>
          ) : null}
        </Banner>
      ) : null}

      <Step n={1} title="Presenter" hint="Your photo avatars appear first. Each look renders the same person in a different photo.">
        <AvatarPicker
          selectedId={draft.avatar_id}
          onPick={(look) => set({ avatar_id: look.id, avatar_name: look.name, avatar_type: look.avatar_type, avatar_preview_url: look.preview_image_url })}
        />
      </Step>

      <Step n={2} title="Voice" hint="Cloned voices are narrated first, then HeyGen lip-syncs the presenter to that audio.">
        <VoicePicker
          value={{ id: draft.voice_id, name: draft.voice_name }}
          onPick={(voice) => set({ voice_id: voice.id, voice_name: voice.name })}
          voices={voices}
          defaultId={ws.default_voice.id}
          narrators={ws.narrators}
          canAdmin={can("admin")}
          onCloned={(voice) => {
            const ref = { id: voice.id, name: voice.name };
            onCloned(ref);
            set({ voice_id: ref.id, voice_name: ref.name });
          }}
        />
        {provider !== "heygen" ? (
          <Box sx={{ mt: 2, p: 1.5, borderRadius: "12px", bgcolor: apple.hoverFill, display: "flex", gap: 1.5, alignItems: "center", flexWrap: "wrap" }}>
            <GraphicEqRoundedIcon sx={{ color: mk.main }} />
            <Box sx={{ flex: "1 1 220px", minWidth: 0 }}>
              <Typography sx={{ fontSize: 13.5, fontWeight: 600 }}>Narration preview</Typography>
              <Typography sx={{ fontSize: 12, color: apple.muted }}>
                {narration
                  ? narrationStale
                    ? "The script, voice or speed changed since this preview."
                    : `${seconds(narration.seconds)} · ${PROVIDER_LABEL[narration.provider as VoiceProvider] ?? narration.provider} · reused when you render`
                  : `Hear the script in this voice before rendering. Uses ${PROVIDER_LABEL[provider]} characters, not HeyGen credits.`}
              </Typography>
            </Box>
            {narration && !narrationStale ? <Box component="audio" controls preload="none" src={narration.url} sx={{ height: 36, maxWidth: "100%" }} /> : null}
            <PillButton size="small" variant="gray" onClick={() => void run("narration")} disabled={Boolean(busy) || words < 3}>
              {busy === "narration" ? "Generating…" : narration ? "Regenerate" : "Preview narration"}
            </PillButton>
          </Box>
        ) : null}
      </Step>

      <Step
        n={3}
        title="Script"
        hint="Write it the way you would say it. A blank line between paragraphs adds a longer pause."
        aside={
          undo ? (
            <PillButton
              size="small"
              variant="text"
              startIcon={<UndoRoundedIcon />}
              onClick={() => {
                set(undo);
                setUndo(null);
              }}
            >
              Restore previous script
            </PillButton>
          ) : null
        }
      >
        <ScriptAssist
          ws={ws}
          onDraft={(title, script) => {
            setUndo({ title: draft.title, script: draft.script });
            set({ script, title: draft.title.trim() ? draft.title : title });
          }}
        />
        <TextField size="small" fullWidth label="Title" value={draft.title} onChange={(event) => set({ title: event.target.value.slice(0, 180) })} sx={{ mb: 1.5 }} />
        <TextField
          fullWidth
          multiline
          minRows={8}
          maxRows={22}
          placeholder="Hi, I'm… In the next thirty seconds…"
          value={draft.script}
          onChange={(event) => set({ script: event.target.value })}
          error={chars > catalog.max_script_chars}
          slotProps={{ htmlInput: { "aria-label": "Script" } }}
          sx={{ "& .MuiInputBase-input": { fontSize: 15, lineHeight: 1.65 } }}
        />
        <Box sx={{ mt: 1, display: "flex", gap: 2, flexWrap: "wrap", fontSize: 12.5, color: apple.muted, fontVariantNumeric: "tabular-nums" }}>
          <span>{words} words</span>
          <span>about {seconds(estimate) || "0s"} at {opts.speed.toFixed(2)}×</span>
          <Box component="span" sx={{ color: chars > catalog.max_script_chars ? apple.danger : undefined }}>
            {chars.toLocaleString()} / {catalog.max_script_chars.toLocaleString()} characters
          </Box>
        </Box>
      </Step>

      <Step n={4} title="Look and feel" hint="Format, pacing and how much the presenter moves.">
        <Box sx={{ display: "grid", gap: 2.5 }}>
          <Box>
            <FieldLabel>Aspect ratio</FieldLabel>
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              {catalog.aspect_ratios.map((ratio) => (
                <AspectChoice key={ratio} ratio={ratio} selected={opts.aspect_ratio === ratio} onClick={() => setOption("aspect_ratio", ratio)} />
              ))}
            </Box>
          </Box>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2.5 }}>
            <Box>
              <FieldLabel>Resolution</FieldLabel>
              <Box sx={{ maxWidth: 240 }}>
                <Segmented value={opts.resolution} onChange={(id) => setOption("resolution", id as AvatarOptions["resolution"])} options={catalog.resolutions.map((id) => ({ id, label: id }))} />
              </Box>
            </Box>
            <Box>
              <FieldLabel>Engine</FieldLabel>
              <TextField select size="small" fullWidth value={opts.engine} onChange={(event) => setOption("engine", event.target.value as AvatarOptions["engine"])} slotProps={{ htmlInput: { "aria-label": "Engine" } }}>
                {catalog.engines.map((id) => (
                  <MenuItem key={id} value={id}>
                    {ENGINE_LABEL[id] || id}
                  </MenuItem>
                ))}
              </TextField>
            </Box>
            <Box>
              <FieldLabel hint="Applies to the narration as well as HeyGen voices.">Speaking speed · {opts.speed.toFixed(2)}×</FieldLabel>
              <Slider
                value={opts.speed}
                min={0.5}
                max={1.5}
                step={0.05}
                marks={[{ value: 0.75 }, { value: 1 }, { value: 1.25 }]}
                onChange={(_, value) => setOption("speed", value as number)}
                aria-label="Speaking speed"
                sx={{ color: mk.main, maxWidth: 320 }}
              />
            </Box>
            <Box>
              <FieldLabel hint="Short breaks at sentence ends and longer ones between paragraphs.">Natural pauses</FieldLabel>
              <Switch checked={opts.pauses} onChange={(event) => setOption("pauses", event.target.checked)} slotProps={{ input: { "aria-label": "Natural pauses" } }} />
            </Box>
            <Box>
              <FieldLabel hint="Leave empty to keep the photo's own background.">Background colour</FieldLabel>
              <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                <Box
                  component="input"
                  type="color"
                  value={opts.background || "#ffffff"}
                  onChange={(event) => setOption("background", (event.target as HTMLInputElement).value)}
                  aria-label="Background colour"
                  sx={{ width: 40, height: 34, p: 0, border: `1px solid ${apple.hairline}`, borderRadius: "8px", bgcolor: "transparent", cursor: "pointer" }}
                />
                <Typography sx={{ fontSize: 13, color: apple.muted, fontFamily: "ui-monospace, monospace" }}>{opts.background || "Photo background"}</Typography>
                {opts.background ? (
                  <PillButton size="small" variant="text" onClick={() => setOption("background", "")}>
                    Clear
                  </PillButton>
                ) : null}
              </Box>
            </Box>
            <Box sx={{ opacity: photoControls ? 1 : 0.55 }}>
              <FieldLabel hint={photoControls ? "How much the face moves with the words." : "Only photo avatars on Avatar IV use this."}>Expressiveness</FieldLabel>
              <Box sx={{ maxWidth: 300, pointerEvents: photoControls ? undefined : "none" }}>
                <Segmented value={opts.expressiveness} onChange={(id) => setOption("expressiveness", id as AvatarOptions["expressiveness"])} options={catalog.expressiveness.map((id) => ({ id, label: id[0].toUpperCase() + id.slice(1) }))} />
              </Box>
            </Box>
          </Box>
          <Box sx={{ opacity: photoControls ? 1 : 0.55 }}>
            <FieldLabel hint={photoControls ? "Plain-language direction for the presenter's body and face." : "Only photo avatars on Avatar IV use this."}>Motion</FieldLabel>
            <TextField
              fullWidth
              multiline
              minRows={2}
              size="small"
              value={opts.motion_prompt}
              disabled={!photoControls}
              onChange={(event) => setOption("motion_prompt", event.target.value.slice(0, catalog.max_motion_prompt))}
              helperText={`${opts.motion_prompt.length} / ${catalog.max_motion_prompt}`}
              slotProps={{ htmlInput: { "aria-label": "Motion direction" } }}
            />
            {photoControls && catalog.defaults && opts.motion_prompt !== catalog.defaults.motion_prompt ? (
              <PillButton size="small" variant="text" onClick={() => setOption("motion_prompt", catalog.defaults?.motion_prompt ?? "")}>
                Reset to the default direction
              </PillButton>
            ) : null}
          </Box>
        </Box>
      </Step>

      {error ? <Banner severity="error">{error}</Banner> : null}

      <Box
        sx={{
          position: "sticky",
          bottom: 12,
          zIndex: 5,
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          flexWrap: "wrap",
          p: 1.25,
          pl: 1.5,
          borderRadius: "18px",
          border: `1px solid ${apple.hairline}`,
          bgcolor: apple.raised,
          boxShadow: shadow.raised,
        }}
      >
        <Box sx={{ width: 40, height: 40, borderRadius: "10px", overflow: "hidden", bgcolor: apple.hoverFill, flexShrink: 0 }}>
          {draft.avatar_preview_url ? <Box component="img" src={draft.avatar_preview_url} alt="" sx={{ width: "100%", height: "100%", objectFit: "cover" }} /> : null}
        </Box>
        <Box sx={{ minWidth: 0, flex: "1 1 200px" }}>
          <Typography noWrap sx={{ fontSize: 14, fontWeight: 600 }}>
            {draft.title.trim() || "Untitled video"}
          </Typography>
          <Typography noWrap sx={{ fontSize: 12, color: apple.muted }}>
            {[draft.avatar_name || "No presenter", draft.voice_name || "No voice", `~${seconds(estimate) || "0s"}`, opts.aspect_ratio].join(" · ")}
            {dirty ? " · unsaved changes" : video ? " · saved" : ""}
          </Typography>
        </Box>
        {onDelete ? (
          <PillButton size="small" variant="text" onClick={onDelete} disabled={Boolean(busy)} sx={{ color: apple.danger }}>
            Delete
          </PillButton>
        ) : null}
        <PillButton size="small" variant="gray" onClick={() => void run("save")} disabled={Boolean(busy) || (!dirty && Boolean(video))}>
          {busy === "save" ? "Saving…" : "Save draft"}
        </PillButton>
        <Tooltip title={renderBlocker}>
          <span>
            <PillButton size="small" startIcon={<MovieCreationOutlinedIcon />} onClick={() => setConfirm(true)} disabled={Boolean(busy) || Boolean(renderBlocker)}>
              {busy === "render" ? "Sending…" : "Render video"}
            </PillButton>
          </span>
        </Tooltip>
      </Box>
      {!heygenReady ? (
        <Typography sx={{ mt: 1, fontSize: 12.5, color: apple.muted }}>
          Drafts save without HeyGen. <PillButton size="small" variant="text" href={requirementHref("heygen")}>Connect HeyGen</PillButton> to render them.
        </Typography>
      ) : null}

      <AppDialog
        open={confirm}
        onClose={() => busy !== "render" && setConfirm(false)}
        title="Render with HeyGen?"
        titleId="render-confirm-title"
        actions={
          <>
            <PillButton variant="text" onClick={() => setConfirm(false)} disabled={busy === "render"}>
              Not yet
            </PillButton>
            <PillButton startIcon={<MovieCreationOutlinedIcon />} onClick={() => void run("render")} disabled={busy === "render"}>
              {busy === "render" ? "Sending…" : "Render"}
            </PillButton>
          </>
        }
      >
        <Box sx={{ display: "grid", gridTemplateColumns: "auto 1fr", columnGap: 2, rowGap: 0.75, fontSize: 14, mb: 2 }}>
          <Box sx={{ color: apple.muted }}>Presenter</Box>
          <Box>{draft.avatar_name || "—"}</Box>
          <Box sx={{ color: apple.muted }}>Voice</Box>
          <Box>
            {draft.voice_name || "Avatar default"} · {PROVIDER_LABEL[provider]}
          </Box>
          <Box sx={{ color: apple.muted }}>Length</Box>
          <Box>about {seconds(estimate)}</Box>
          <Box sx={{ color: apple.muted }}>Format</Box>
          <Box>
            {opts.aspect_ratio} · {opts.resolution} · {ENGINE_LABEL[opts.engine] || opts.engine}
          </Box>
        </Box>
        <Typography sx={{ fontSize: 13.5, color: apple.muted, lineHeight: 1.55 }}>
          HeyGen charges your balance for each render{balance != null ? ` (currently ${balance.toLocaleString()}${ws.account.currency ? ` ${ws.account.currency}` : ""})` : ""}.
          {provider !== "heygen" ? ` The ${PROVIDER_LABEL[provider]} narration is generated first, or reused if your preview is current.` : ""} Rendering takes a few minutes and keeps going if you leave this page.
        </Typography>
      </AppDialog>
    </Box>
  );
}
