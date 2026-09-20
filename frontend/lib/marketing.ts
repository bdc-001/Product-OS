import type { BackgroundJob } from "./api";
import { httpJson, peekGet } from "./http";

export const formatLabels: Record<string, string> = {
  linkedin_post: "LinkedIn post", linkedin_carousel: "LinkedIn carousel", linkedin_portrait_video: "LinkedIn portrait video",
  youtube_short: "YouTube Short", youtube_landscape_video: "Launch video · landscape", article: "Article", feature_brief: "Artifact · feature brief",
  release_notes: "Release notes", case_study: "Case study",
};
export type ContentStatus = { status: string; campaign_id?: number; revision?: number; stale: boolean; reason?: string; error?: string; delivery?: string; assets: MarketingAsset[] };
export type PmmDecision = {
  verdict: "approve" | "skip" | "defer"; rationale: string; audience: string; buyer_problem: string; positioning: string;
  evidence_quotes: string[]; missing_evidence: string[]; cta: string; model: string;
  assignments: { format: string; reason: string; angle: string; objective: string; outline: string[] }[];
  omitted_formats: Record<string, string>;
};
export type FormatContent = { title: string; body: string; slides?: { headline: string; body: string }[];
  scenes?: { headline: string; body: string; narration: string }[];
  review?: { passed: boolean; scores: Record<string, number>; feature_specificity?: string } };
export type FormatState = { status: string; error?: string; content?: FormatContent };
export type MarketingFeature = {
  id: number; name: string; description: string; summary?: string; audience: string; benefit: string; notes: string;
  status: "draft" | "candidate" | "ready" | "dismissed"; source: string; revision: number;
  module: string; priority: string; hook: string; start_date: string; end_date: string;
  sheet_status: "Not started" | "In Progress" | "Completed" | string;
  script: string; video: string; tag: "New" | "Queued" | "In pipeline" | "Done" | string;
  evidence: { module: string; paths: string[]; quote: string; branch: string; sha: string }[];
  decision?: PmmDecision; updated_at: string;
  content_status?: Record<string, ContentStatus>;
};
export type FeatureInput = Pick<MarketingFeature,
  "name" | "description" | "summary" | "audience" | "benefit" | "notes" | "status" |
  "module" | "priority" | "hook" | "start_date" | "end_date" | "sheet_status" | "script" | "video" | "tag"
> & { revision?: number };
export type MarketingAsset = { filename: string; channel: string; mime: string; file_id?: string; drive_url?: string };
export type Campaign = {
  id: number; feature_id: number; feature_revision: number; feature_snapshot: MarketingFeature;
  status: string; error: string; created_at: string; drive_url: string; assets: MarketingAsset[];
  content: Partial<Record<"linkedin" | "youtube" | "article" | "document", { title: string; body: string }>> & {
    version?: number; decision?: PmmDecision; formats?: Record<string, FormatState>;
    strategy?: { positioning: string; buyer_pain: string; differentiation: string; pillars: string[]; cta: string; content_ideas: { channel: string; idea: string; angle: string }[] };
    video?: { title: string; scenes: { headline: string; body: string; narration: string; evidence: string }[] };
  };
};
export type MarketingWorkspace = {
  features: MarketingFeature[]; campaigns: Campaign[];
  drive: { configured: boolean; url: string }; sheet?: { configured: boolean; url: string }; video: { ready: boolean; voice: string; label: string };
  manager_model: string; formats: Record<string, string>; model_configured: boolean; active_job: BackgroundJob | null;
  sheet_statuses?: string[]; tags?: string[];
  last_sync?: BackgroundJob | null;
};
function request<T>(path: string, init?: RequestInit): Promise<T> {
  return httpJson<T>(`/api${path}`, init);
}
export const marketingApi = {
  workspace: () => request<MarketingWorkspace>("/marketing"),
  peekWorkspace: () => peekGet<MarketingWorkspace>("/api/marketing"),
  save: (body: FeatureInput, id?: number) => request<MarketingFeature>(id ? `/marketing/features/${id}` : `/marketing/features`, { method: id ? "PUT" : "POST", body: JSON.stringify(body) }),
  generate: (ids: number[], formats?: string[]) => request<BackgroundJob>("/marketing/generate", { method: "POST", body: JSON.stringify({ feature_ids: ids, ...(formats ? { formats } : {}) }) }),
  campaign: (id: number) => request<Campaign>(`/marketing/campaigns/${id}`),
  discover: () => request<BackgroundJob>("/marketing/discover", { method: "POST" }),
  retry: (id: number) => request<BackgroundJob>(`/marketing/campaigns/${id}/retry`, { method: "POST" }),
  job: (id: number) => request<BackgroundJob>(`/jobs/${id}`),
  file: (id: number, name: string) => `/api/marketing/campaigns/${id}/files/${encodeURIComponent(name)}`,
};
