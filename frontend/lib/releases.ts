import { httpJson } from "./http";

export type ReleaseView = {
  id: string; branch: string; sha: string; merged_at: string; merge_verified: boolean;
  state: "needs_attention" | "awaiting_review" | "drafts" | "tracked";
  counts: { buyer_facing: number; artifacts: number; drafts: number };
  changes: { name: string; what: string; confidence: string; evidence: string; internal?: boolean }[];
  features: { id: number; name: string; summary: string; module: string; status: string; buyer_facing: boolean; verdict: string; rationale: string; url: string }[];
  assessments: { name: string; summary: string; verdict: string; rationale: string }[];
  campaigns: { id: number; name: string; status: string; error: string; association: string; url: string }[];
  artifacts: { name: string; url: string; source: string; association: string; drive_url: string }[];
  comms: { id: number; title: string; kind: string; state: string; association: string; url: string; review_url: string }[];
  jobs: { id: number; status: string; error: string; url: string; pack_id: number }[];
};
export type ReleaseWorkspace = { releases: ReleaseView[]; warnings: string[]; unlinked: { features: number; comms: number; artifacts: number }; history_limit: number };
export const loadReleases = () => httpJson<ReleaseWorkspace>("/api/releases", { cache: "no-store" });
export const releaseState: Record<ReleaseView["state"], string> = {
  needs_attention: "Needs attention", awaiting_review: "Awaiting approval", drafts: "Drafts in progress", tracked: "Tracked",
};
