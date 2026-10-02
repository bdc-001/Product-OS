import { httpJson } from "./http";

export type AvatarStatus = "draft" | "submitting" | "submitted" | "rendering" | "downloading" | "completed" | "failed";
export type AspectRatio = "16:9" | "9:16" | "1:1" | "4:5" | "auto";
export type Engine = "avatar_iv" | "avatar_v" | "avatar_iii";
export type Expressiveness = "low" | "medium" | "high";

export type AvatarOptions = {
  aspect_ratio: AspectRatio;
  resolution: "1080p" | "720p";
  engine: Engine;
  speed: number;
  background: string;
  pauses: boolean;
  expressiveness: Expressiveness;
  motion_prompt: string;
};

export type AvatarAsset = { filename: string; kind: "video" | "captions" | "thumbnail" | string; mime: string; size?: number; url: string };

export type Narration = {
  key: string; file: string; seconds: number; characters: number; provider: string; voice_id: string; model: string;
  created_at: string | null; stale: boolean; url: string;
};

export type AvatarVideo = {
  id: number;
  title: string;
  feature_id: number | null;
  script: string;
  words: number;
  estimated_seconds: number;
  avatar: { id: string; name: string; type: string; preview_url: string };
  voice: { id: string; name: string };
  options: AvatarOptions;
  status: AvatarStatus;
  error: string;
  heygen_video_id: string | null;
  attempt: number | null;
  revision: number | null;
  duration: number | null;
  video_page_url: string;
  retry_downloads_only: boolean;
  narration: Narration | null;
  assets: AvatarAsset[];
  created_at: string | null;
  updated_at: string | null;
  submitted_at: string | null;
  completed_at: string | null;
};

export type HeyGenAccount = { configured: boolean; reachable: boolean; billing_type: string; balance: number | null; currency: string; error: string };

export type AvatarCatalog = {
  aspect_ratios: AspectRatio[];
  resolutions: AvatarOptions["resolution"][];
  engines: Engine[];
  expressiveness: Expressiveness[];
  max_motion_prompt: number;
  max_script_chars: number;
  words_per_minute: number;
  defaults?: AvatarOptions;
};

export type VoiceRef = { id: string; name: string };

export type AvatarWorkspace = {
  account: HeyGenAccount;
  videos: AvatarVideo[];
  features: { id: number; name: string; module: string }[];
  options: AvatarCatalog;
  script_ready: boolean;
  default_voice: VoiceRef;
  narrators: { cartesia: boolean; elevenlabs: boolean };
};

export type AvatarLook = {
  id: string; name: string; avatar_type: string; group_id: string; gender: string;
  preview_image_url: string; preview_video_url: string; default_voice_id: string; engines: string[];
  orientation: string; status: string; ready: boolean; error: string;
};

export type HeyGenVoice = { id: string; name: string; language: string; gender: string; type: string; preview_audio_url: string };

export type Paged<T> = { items: T[]; has_more: boolean; next_token: string };

export type VideoInput = {
  title: string;
  feature_id: number | null;
  script: string;
  avatar_id: string;
  avatar_name: string;
  avatar_type: string;
  avatar_preview_url: string;
  voice_id: string;
  voice_name: string;
  options: AvatarOptions;
};

export type ScriptDraft = { title: string; script: string; words: number; estimated_seconds: number; model: string };
export type CreatedAvatar = { group_id: string; name: string; looks: AvatarLook[] };
export type ClonedVoice = {
  voice_id: string; id: string; name: string; default: boolean;
  accents?: string[]; accent_error?: string; clip_seconds?: number; requires_verification?: boolean;
};

export const ACTIVE_STATUSES: AvatarStatus[] = ["submitting", "submitted", "rendering", "downloading"];
export const isRendering = (video?: Pick<AvatarVideo, "status"> | null) => Boolean(video && ACTIVE_STATUSES.includes(video.status));
export const isEditable = (video?: Pick<AvatarVideo, "status"> | null) => !video || video.status === "draft" || video.status === "failed";

export type VoiceProvider = "cartesia" | "elevenlabs" | "heygen";

/** Cartesia and ElevenLabs voices are narrated here and uploaded as audio; anything else is a HeyGen voice id. */
export function voiceProvider(id: string): VoiceProvider {
  if (id.startsWith("cartesia:")) return "cartesia";
  if (id.startsWith("elevenlabs:")) return "elevenlabs";
  return "heygen";
}

export const PROVIDER_LABEL: Record<VoiceProvider, string> = { cartesia: "Cartesia", elevenlabs: "ElevenLabs", heygen: "HeyGen" };

export function videoInput(video: AvatarVideo): VideoInput {
  return {
    title: video.title || "",
    feature_id: video.feature_id,
    script: video.script || "",
    avatar_id: video.avatar.id || "",
    avatar_name: video.avatar.name || "",
    avatar_type: video.avatar.type || "",
    avatar_preview_url: video.avatar.preview_url || "",
    voice_id: video.voice.id || "",
    voice_name: video.voice.name || "",
    options: { ...video.options },
  };
}

const base = "/api/avatar-videos";

function query(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value) search.set(key, value);
  const text = search.toString();
  return text ? `?${text}` : "";
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const avatarApi = {
  workspace: () => httpJson<AvatarWorkspace>(base, { cache: "no-store" }),
  avatars: (ownership: "private" | "public", token = "", fresh = false) =>
    httpJson<Paged<AvatarLook>>(`${base}/avatars${query({ ownership, token })}`, fresh ? { cache: "no-store" } : undefined),
  look: (id: string) => httpJson<AvatarLook>(`${base}/avatars/looks/${encodeURIComponent(id)}`, { cache: "no-store" }),
  createAvatar: (form: FormData) => httpJson<CreatedAvatar>(`${base}/avatars`, { method: "POST", body: form }),
  voices: (params: { type: "private" | "public"; language?: string; gender?: string; token?: string }) =>
    httpJson<Paged<HeyGenVoice>>(`${base}/voices${query(params)}`),
  cloneCartesia: (form: FormData) => httpJson<ClonedVoice>(`${base}/voices/cartesia`, { method: "POST", body: form }),
  cloneElevenLabs: (form: FormData) => httpJson<ClonedVoice>(`${base}/voices/elevenlabs`, { method: "POST", body: form }),
  script: (body: { feature_id: number | null; brief: string; seconds: number; angle: string }) =>
    httpJson<ScriptDraft>(`${base}/script`, json("POST", body)),
  create: (body: VideoInput & { render?: boolean }) => httpJson<AvatarVideo>(base, json("POST", body)),
  update: (id: number, body: VideoInput & { render?: boolean }) => httpJson<AvatarVideo>(`${base}/${id}`, json("PUT", body)),
  render: (id: number) => httpJson<AvatarVideo>(`${base}/${id}/render`, json("POST")),
  narration: (id: number) => httpJson<AvatarVideo>(`${base}/${id}/narration`, json("POST")),
  refresh: (id: number) => httpJson<AvatarVideo>(`${base}/${id}/refresh`, json("POST")),
  duplicate: (id: number) => httpJson<AvatarVideo>(`${base}/${id}/duplicate`, json("POST")),
  remove: (id: number) => httpJson<{ ok: boolean }>(`${base}/${id}`, json("DELETE")),
};
