"use client";

import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import MicNoneRoundedIcon from "@mui/icons-material/MicNoneRounded";
import PauseRoundedIcon from "@mui/icons-material/PauseRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Checkbox from "@mui/material/Checkbox";
import Collapse from "@mui/material/Collapse";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import MenuItem from "@mui/material/MenuItem";
import Skeleton from "@mui/material/Skeleton";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";
import NextLink from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { DropZone, VoiceBadge, errorText, mk, providerNote, useAudioPreview } from "@/app/avatar/shared";
import { AppDialog, Banner, PillButton, Segmented } from "@/app/ui";
import { requirementHref } from "@/app/ui/platform";
import { apple, pmm } from "@/app/ui/tokens";
import { PROVIDER_LABEL, avatarApi, voiceProvider, type ClonedVoice, type HeyGenVoice, type VoiceRef } from "@/lib/avatar";

function VoiceRow({ voice, selected, isDefault, onPick }: { voice: VoiceRef; selected: boolean; isDefault: boolean; onPick: () => void }) {
  const provider = voiceProvider(voice.id);
  return (
    <ButtonBase
      onClick={onPick}
      role="radio"
      aria-checked={selected}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        width: "100%",
        textAlign: "left",
        p: 1.25,
        borderRadius: "12px",
        border: `1.5px solid ${selected ? mk.main : apple.hairline}`,
        boxShadow: selected ? `0 0 0 3px ${mk.fill}` : "none",
        bgcolor: apple.raised,
        transition: `border-color 0.2s ${apple.smooth}, box-shadow 0.2s ${apple.smooth}`,
        "&:hover": { borderColor: selected ? mk.main : apple.hairlineHover },
        "&.Mui-focusVisible": { outline: `2px solid ${apple.ink}`, outlineOffset: 2 },
      }}
    >
      <VoiceBadge id={voice.id} />
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexWrap: "wrap" }}>
          <Typography noWrap sx={{ fontSize: 14, fontWeight: 600, color: apple.text }}>
            {voice.name || "Unnamed voice"}
          </Typography>
          <Box component="span" sx={{ fontSize: 11, fontWeight: 600, px: 0.75, py: 0.1, borderRadius: 999, bgcolor: apple.hoverFill, color: apple.muted }}>
            {PROVIDER_LABEL[provider]}
          </Box>
          {isDefault ? (
            <Box component="span" sx={{ fontSize: 11, fontWeight: 600, px: 0.75, py: 0.1, borderRadius: 999, bgcolor: pmm.greenFill, color: pmm.green }}>
              Workspace default
            </Box>
          ) : null}
        </Box>
        <Typography sx={{ fontSize: 12, color: apple.muted }}>{providerNote(voice.id)}</Typography>
      </Box>
      <Box aria-hidden sx={{ width: 18, height: 18, borderRadius: "50%", border: `2px solid ${selected ? mk.main : apple.hairlineHover}`, display: "grid", placeItems: "center", flexShrink: 0 }}>
        {selected ? <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: mk.main }} /> : null}
      </Box>
    </ButtonBase>
  );
}

function HeyGenBrowser({ selectedId, onPick }: { selectedId: string; onPick: (voice: VoiceRef) => void }) {
  const [type, setType] = useState<"private" | "public">("public");
  const [gender, setGender] = useState("");
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<HeyGenVoice[] | null>(null);
  const [next, setNext] = useState("");
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);
  const request = useRef(0);
  const { playing, toggle } = useAudioPreview();

  useEffect(() => {
    const id = ++request.current;
    setItems(null);
    setError("");
    avatarApi
      .voices({ type, gender })
      .then((page) => {
        if (id !== request.current) return;
        setItems(page.items);
        setNext(page.has_more ? page.next_token : "");
      })
      .catch((err) => {
        if (id !== request.current) return;
        setItems([]);
        setNext("");
        setError(errorText(err, "Could not load HeyGen voices."));
      });
  }, [type, gender]);

  const loadMore = async () => {
    setMore(true);
    try {
      const page = await avatarApi.voices({ type, gender, token: next });
      setItems((current) => [...(current || []), ...page.items]);
      setNext(page.has_more ? page.next_token : "");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setMore(false);
    }
  };

  const needle = search.trim().toLowerCase();
  const visible = (items || []).filter((voice) => !needle || `${voice.name} ${voice.language}`.toLowerCase().includes(needle));

  return (
    <Box sx={{ mt: 1.5, p: 1.5, borderRadius: "14px", bgcolor: apple.hoverFill }}>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center", mb: 1.25 }}>
        <Box sx={{ width: 200 }}>
          <Segmented value={type} onChange={(id) => setType(id as "private" | "public")} options={[{ id: "public", label: "Library" }, { id: "private", label: "My HeyGen" }]} />
        </Box>
        <TextField select size="small" value={gender} onChange={(event) => setGender(event.target.value)} sx={{ width: 130 }} slotProps={{ htmlInput: { "aria-label": "Gender" } }}>
          <MenuItem value="">Any gender</MenuItem>
          <MenuItem value="female">Female</MenuItem>
          <MenuItem value="male">Male</MenuItem>
        </TextField>
        <TextField
          size="small"
          placeholder="Name or language"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          sx={{ flex: "1 1 160px" }}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRoundedIcon sx={{ fontSize: 18 }} /></InputAdornment> } }}
        />
      </Box>
      {error ? <Banner severity="error">{error}</Banner> : null}
      <Box sx={{ maxHeight: 300, overflow: "auto", display: "grid", gap: 0.5 }}>
        {items === null
          ? Array.from({ length: 4 }, (_, index) => <Skeleton key={index} variant="rounded" height={44} sx={{ borderRadius: "10px" }} />)
          : visible.map((voice) => {
              const on = voice.id === selectedId;
              return (
                <Box key={voice.id} sx={{ display: "flex", alignItems: "center", gap: 1, px: 1, py: 0.6, borderRadius: "10px", bgcolor: on ? mk.fill : apple.raised }}>
                  <IconButton size="small" onClick={() => toggle(voice.id, voice.preview_audio_url)} disabled={!voice.preview_audio_url} aria-label={playing === voice.id ? `Stop ${voice.name}` : `Play ${voice.name}`}>
                    {playing === voice.id ? <PauseRoundedIcon fontSize="small" /> : <PlayArrowRoundedIcon fontSize="small" />}
                  </IconButton>
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Typography noWrap sx={{ fontSize: 13, fontWeight: 600 }}>{voice.name}</Typography>
                    <Typography noWrap sx={{ fontSize: 11.5, color: apple.muted }}>{[voice.language, voice.gender].filter(Boolean).join(" · ") || "HeyGen voice"}</Typography>
                  </Box>
                  <PillButton size="small" variant={on ? "filled" : "gray"} onClick={() => onPick({ id: voice.id, name: voice.name })}>
                    {on ? "Selected" : "Use"}
                  </PillButton>
                </Box>
              );
            })}
        {items !== null && !visible.length && !error ? <Typography sx={{ fontSize: 13, color: apple.muted, p: 1 }}>No voices match.</Typography> : null}
      </Box>
      {next ? (
        <Box sx={{ mt: 1 }}>
          <PillButton variant="text" size="small" onClick={() => void loadMore()} disabled={more}>
            {more ? "Loading…" : "Load more voices"}
          </PillButton>
        </Box>
      ) : null}
    </Box>
  );
}

export function VoicePicker({
  value,
  onPick,
  voices,
  defaultId,
  narrators,
  canAdmin,
  onCloned,
}: {
  value: VoiceRef;
  onPick: (voice: VoiceRef) => void;
  voices: VoiceRef[];
  defaultId: string;
  narrators: { cartesia: boolean; elevenlabs: boolean };
  canAdmin: boolean;
  onCloned: (voice: ClonedVoice) => void;
}) {
  const [browse, setBrowse] = useState(false);
  const [cloning, setCloning] = useState(false);
  const rows = useMemo(() => {
    const seen = new Set<string>();
    return [value, ...voices].filter((voice) => voice.id && !seen.has(voice.id) && seen.add(voice.id));
  }, [value, voices]);
  const canClone = narrators.cartesia || narrators.elevenlabs;

  return (
    <Box>
      <Box role="radiogroup" aria-label="Voice" sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" }, gap: 1 }}>
        {rows.map((voice) => (
          <VoiceRow key={voice.id} voice={voice} selected={voice.id === value.id} isDefault={voice.id === defaultId} onPick={() => onPick(voice)} />
        ))}
      </Box>
      {!rows.length ? (
        <Typography sx={{ fontSize: 13, color: apple.muted }}>No voice yet. Clone one from a recording, or pick a HeyGen voice below.</Typography>
      ) : null}
      <Box sx={{ mt: 1.5, display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
        {canClone ? (
          <PillButton size="small" variant="gray" startIcon={<MicNoneRoundedIcon />} onClick={() => setCloning(true)}>
            Clone a voice
          </PillButton>
        ) : (
          <Typography sx={{ fontSize: 12.5, color: apple.muted }}>
            <Link component={NextLink} href={requirementHref("cartesia")} sx={{ color: apple.text }}>
              Connect Cartesia
            </Link>{" "}
            or ElevenLabs to clone your own voice.
          </Typography>
        )}
        <PillButton
          size="small"
          variant="text"
          onClick={() => setBrowse((open) => !open)}
          aria-expanded={browse}
          endIcon={<ExpandMoreRoundedIcon sx={{ transform: browse ? "rotate(180deg)" : "none", transition: `transform 0.25s ${apple.smooth}` }} />}
        >
          Browse HeyGen voices
        </PillButton>
      </Box>
      <Collapse in={browse} unmountOnExit>
        <HeyGenBrowser selectedId={value.id} onPick={onPick} />
      </Collapse>
      <CloneVoiceDialog
        open={cloning}
        narrators={narrators}
        canAdmin={canAdmin}
        onClose={() => setCloning(false)}
        onCloned={(voice) => {
          setCloning(false);
          onCloned(voice);
        }}
      />
    </Box>
  );
}

const SPEAKERS = {
  hinglish: { label: "Records in Hindi or Hinglish", language: "hi", accent: "standard-hindi", speaks: ["indian-english"] },
  english: { label: "Records in Indian English", language: "en", accent: "indian-english", speaks: [] as string[] },
} as const;
type Speaker = keyof typeof SPEAKERS;

const AUDIO_ACCEPT = ".m4a,.mp3,.wav,.aac,.ogg,.flac,.webm,audio/*";
const MAX_SAMPLE_BYTES = 25 * 1024 * 1024;

export function CloneVoiceDialog({
  open,
  onClose,
  narrators,
  canAdmin,
  onCloned,
}: {
  open: boolean;
  onClose: () => void;
  narrators: { cartesia: boolean; elevenlabs: boolean };
  canAdmin: boolean;
  onCloned: (voice: ClonedVoice) => void;
}) {
  const [provider, setProvider] = useState<"cartesia" | "elevenlabs">(narrators.cartesia ? "cartesia" : "elevenlabs");
  const [name, setName] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [speaker, setSpeaker] = useState<Speaker>("hinglish");
  const [denoise, setDenoise] = useState(false);
  const [makeDefault, setMakeDefault] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ClonedVoice | null>(null);
  const limit = provider === "cartesia" ? 1 : 5;

  const reset = () => {
    setName("");
    setFiles([]);
    setError("");
    setResult(null);
    setMakeDefault(false);
    setDenoise(false);
  };

  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const add = (picked: File[]) => {
    const tooBig = picked.some((file) => file.size > MAX_SAMPLE_BYTES);
    const ok = picked.filter((file) => file.size <= MAX_SAMPLE_BYTES);
    setError(tooBig ? "Each recording must be under 25 MB." : "");
    setFiles((current) => (limit === 1 ? ok.slice(0, 1) : [...current, ...ok].slice(0, limit)));
  };

  const submit = async () => {
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("name", name.trim());
    form.append("make_default", String(canAdmin && makeDefault));
    try {
      let voice: ClonedVoice;
      if (provider === "cartesia") {
        const preset = SPEAKERS[speaker];
        form.append("language", preset.language);
        form.append("accent", preset.accent);
        preset.speaks.forEach((accent) => form.append("speaks", accent));
        form.append("sample", files[0], files[0].name);
        voice = await avatarApi.cloneCartesia(form);
      } else {
        form.append("remove_background_noise", String(denoise));
        files.forEach((file) => form.append("samples", file, file.name));
        voice = await avatarApi.cloneElevenLabs(form);
      }
      if (voice.accent_error || voice.requires_verification) setResult(voice);
      else {
        reset();
        onCloned(voice);
      }
    } catch (err) {
      setError(errorText(err, "The voice could not be cloned."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppDialog
      open={open}
      onClose={close}
      title="Clone a voice"
      titleId="clone-voice-title"
      actions={
        result ? (
          <PillButton
            onClick={() => {
              const voice = result;
              reset();
              onCloned(voice);
            }}
          >
            Use {result.name}
          </PillButton>
        ) : (
          <>
            <PillButton variant="text" onClick={close} disabled={busy}>
              Cancel
            </PillButton>
            <PillButton onClick={() => void submit()} disabled={busy || !name.trim() || !files.length}>
              {busy ? "Cloning…" : "Clone voice"}
            </PillButton>
          </>
        )
      }
    >
      {result ? (
        <Box>
          <Banner severity="success">{result.name} is ready to use.</Banner>
          {result.accent_error ? <Banner severity="warning">Cartesia kept the clone but did not add every accent: {result.accent_error}</Banner> : null}
          {result.requires_verification ? <Banner severity="warning">ElevenLabs asks you to verify this voice in its dashboard before it can be used at full quality.</Banner> : null}
        </Box>
      ) : (
        <Box sx={{ display: "grid", gap: 2 }}>
          {narrators.cartesia && narrators.elevenlabs ? (
            <Box sx={{ maxWidth: 280 }}>
              <Segmented
                value={provider}
                onChange={(id) => {
                  setProvider(id as "cartesia" | "elevenlabs");
                  setFiles([]);
                }}
                options={[{ id: "cartesia", label: "Cartesia" }, { id: "elevenlabs", label: "ElevenLabs" }]}
              />
            </Box>
          ) : null}
          <TextField size="small" label="Voice name" value={name} onChange={(event) => setName(event.target.value.slice(0, 80))} disabled={busy} autoFocus />
          {provider === "cartesia" ? (
            <TextField select size="small" label="Speaker" value={speaker} onChange={(event) => setSpeaker(event.target.value as Speaker)} disabled={busy} helperText="Cartesia clones in the language you recorded in, then adds Indian English so scripts keep the speaker's accent.">
              {Object.entries(SPEAKERS).map(([id, preset]) => (
                <MenuItem key={id} value={id}>
                  {preset.label}
                </MenuItem>
              ))}
            </TextField>
          ) : null}
          <DropZone
            accept={AUDIO_ACCEPT}
            multiple={limit > 1}
            onFiles={add}
            disabled={busy}
            icon={<MicNoneRoundedIcon />}
            title={files.length ? files.map((file) => file.name).join(", ") : limit > 1 ? "Drop up to 5 recordings or browse" : "Drop a recording or browse"}
            hint={
              provider === "cartesia"
                ? "M4A, MP3, WAV, AAC, OGG, FLAC or WebM. At least 8 seconds of clean speech; Cartesia learns from the first 60."
                : "M4A, MP3, WAV, AAC, OGG, FLAC or WebM. Clean speech from one person; a few minutes in total works best."
            }
          />
          {provider === "elevenlabs" ? (
            <FormControlLabel control={<Checkbox checked={denoise} onChange={(event) => setDenoise(event.target.checked)} disabled={busy} />} label="Remove background noise" />
          ) : null}
          {canAdmin ? (
            <FormControlLabel
              control={<Checkbox checked={makeDefault} onChange={(event) => setMakeDefault(event.target.checked)} disabled={busy} />}
              label={<Typography sx={{ fontSize: 14 }}>Make this the workspace default narrator</Typography>}
            />
          ) : null}
          {error ? <Banner severity="error">{error}</Banner> : null}
        </Box>
      )}
    </AppDialog>
  );
}
