import { clearHttpCache, httpJson, peekGet } from "@/lib/http";

export { clearHttpCache, peekGet };

export type NoteBlock = {
  id: string;
  type: "paragraph" | "heading" | "actionable" | "decision" | "learning";
  text: string;
  done?: boolean;
  ticket_key?: string;
};
export type DailyNote = {
  id: number;
  day: string;
  title: string;
  body: string;
  learning: string;
  kind?: "daily" | "meeting" | "decision" | "learning";
  blocks?: NoteBlock[];
  actionable_count?: number;
  tags: string[];
  updated_at: string;
};
export type LibraryDocument = { id: number; title: string; filename: string; size: number; status: string; tags: string[]; indexed: boolean; pages: number; extraction_note: string; url: string; text?: string; created_at: string };
export type SourceIndex = { ready: boolean; branch: string; sha: string; file_count?: number; chunk_count?: number; skipped_files?: number; modules?: { name: string; files: number }[] };
export type Source = { type: string; ref?: string; url?: string; chat_id?: string };
export type StandupItem = {
  title: string;
  body?: string;
  action?: string;
  action_type?: string;
  confidence?: string;
  issue_key?: string;
  card_key?: string;
  board?: string;
  flag?: string;
  why?: string;
  snippet?: string;
  sources?: Source[];
  kind?: string;
  urgency?: number;
  rank?: number;
  status?: string;
  assignee?: string;
  recommend?: string;
  age_days?: number | null;
  state_days?: number | null;
  aging?: boolean;
  url?: string;
};
export type Evaluation = {
  overall: number;
  signal_detection: number;
  prioritization: number;
  grounding: number;
  actionability: number;
  completeness: number;
  noise: number;
  hallucination: number;
};
export type Standup = {
  id: number;
  window_start: string | null;
  window_end: string | null;
  needs_attention: StandupItem[];
  at_risk: StandupItem[];
  completed: StandupItem[];
  team_signals: StandupItem[];
  todays_actions: StandupItem[];
  bugs: StandupItem[];
  tasks: StandupItem[];
  wallet_requests: StandupItem[];
  long_pending?: StandupItem[];
  week_actions?: StandupItem[];
  this_week?: StandupItem[];
  other_actions?: StandupItem[];
  cliq_briefing?: CliqBriefing;
  dev_load?: {
    short: string;
    name: string;
    bugs?: number;
    tasks?: number;
    in_progress: number;
    keys?: string[];
    bug_keys?: string[];
    task_keys?: string[];
    tickets?: { key: string; summary?: string; kind?: string }[];
  }[];
  monday_plan?: {
    found?: boolean;
    chat?: string;
    excerpt?: string;
    tasks?: { title: string; area?: string; issue_key?: string; needs_ticket?: boolean; status?: string }[];
  };
  llm_used: boolean;
  delivery_status: string;
  evaluation: Evaluation | null;
  period?: string;
  headline?: string;
  now_label?: string;
  window_label?: string;
  week_label?: string;
};
export type Issue = {
  issue_key: string;
  summary: string;
  status: string;
  priority: string;
  assignee: string;
  creator: string;
  issue_type?: string;
  kind?: string;
  board?: string;
  reporter?: string;
  created_at?: string | null;
  due_date: string | null;
  updated_at: string | null;
  url: string;
  labels?: string;
  description?: string;
  missing_fields?: string[];
  field_checklist?: { label: string; value: string; required?: boolean; empty?: boolean }[];
  fields?: Record<string, unknown>;
  schema_kind?: string;
};
export type ReleaseAskTicket = {
  issue_key: string;
  summary: string;
  released_on: string;
  released_label: string;
  url: string;
  pm: string;
};
export type ReleaseAskGroup = {
  pm: string;
  email: string;
  tickets: ReleaseAskTicket[];
  last_nudged_at?: string;
};
export type ReleaseAsks = {
  lookback_days: number;
  after_date?: string;
  queue_start?: string;
  data_branch?: string;
  connected: boolean;
  cliq: boolean;
  last_nudged_at?: string;
  dismissed?: string[];
  groups: ReleaseAskGroup[];
  count: number;
  error?: string;
};
export type CliqDigestItem = {
  issue_key?: string;
  board?: string;
  jira_summary?: string;
  status?: string;
  assignee?: string;
  summary: string;
  body?: string;
  title?: string;
  action?: string;
  why?: string;
  chats?: string[];
  people?: string[];
  message_count?: number;
  from?: string;
  chat?: string;
  timestamp?: string | null;
  card_key?: string;
};
export type CliqDigest = {
  tasks: CliqDigestItem[];
  bugs: CliqDigestItem[];
  open_points: CliqDigestItem[];
  wallet_requests: CliqDigestItem[];
  period?: string;
  headline?: string;
  window_label?: string;
};
export type CliqBriefing = {
  window_label?: string;
  conversations?: CliqDigestItem[];
  follow_up_tomorrow?: CliqDigestItem[];
  promises?: CliqDigestItem[];
  unanswered?: CliqDigestItem[];
  stale?: boolean;
  ingest_error?: string;
};
export type CodebaseModule = {
  name: string;
  kind?: string;
  summary?: string;
  capabilities?: string[];
  doc_paths?: string[];
};
export type CodebaseStatus = {
  path: string;
  exists: boolean;
  is_git: boolean;
  configured?: boolean;
  pull_enabled?: boolean;
  branch: string;
  commit_sha: string;
  commit_at?: string;
  commit_message?: string;
  ahead: number;
  behind: number;
  dirty?: boolean;
  error?: string;
  indexed?: boolean;
  indexed_at?: string | null;
  indexed_at_label?: string;
  indexed_branch?: string;
  indexed_sha?: string;
  indexed_message?: string;
  module_count?: number;
  pulled?: boolean;
  pull_error?: string;
  stashed?: boolean;
  stashed_note?: string;
  llm_used?: boolean;
  recent_commits?: { sha: string; date: string; message: string }[];
  live_base?: string;
  live_summary?: string;
  live_commits?: { sha: string; date: string; message: string }[];
  live_files?: { change?: string; path: string }[];
  in_sync?: boolean;
  behind_main?: number;
  index_age_days?: number | null;
  clone_alert?: string;
  stashes?: { id: number; branch?: string; message?: string; created_at?: string | null }[];
  modules?: CodebaseModule[];
  map_path?: string;
  now_label?: string;
  data_branch?: string;
};
export type CodebaseBranch = {
  name: string;
  sha: string;
  date?: string;
  day?: string;
  sort_at?: string;
  merged?: boolean;
  message?: string;
  remote?: boolean;
  current?: boolean;
};
export type CodebaseAsk = {
  id: number;
  question: string;
  answer: string;
  citations?: { path?: string; note?: string; url?: string }[];
  branch?: string;
  commit_sha?: string;
  llm_used?: boolean;
  created_at?: string | null;
};
export type CodebaseQueryIndex = {
  ready?: boolean;
  branch?: string;
  sha?: string;
  module_count?: number;
  message?: string;
  error?: string;
  local?: boolean;
  stale?: boolean;
};
export type NewsletterItem = { feature: string; headline?: string; body?: string; cta?: string };
export type ReleaseNotesJob = {
  id: number;
  branch?: string;
  commit_sha?: string;
  pack_id?: number;
  pdf_path?: string;
  emailed_to?: string;
  status?: string;
  error?: string;
  created_at?: string | null;
};
export type ReleaseFeature = {
  name: string;
  what?: string;
  why?: string;
  modules?: string[];
  confidence?: string;
  evidence?: string;
  gap?: string;
};
export type ReleaseJob = {
  id: number;
  branch: string;
  sha?: string;
  base_sha?: string;
  merged_at?: string;
  merged_at_label?: string;
  snapshot_id?: number;
  pack_id?: number;
  pdf_path?: string;
  drive_file_id?: string;
  drive_link?: string;
  extraction?: { features?: ReleaseFeature[]; internal?: string[]; doc?: Record<string, unknown> };
  features?: ReleaseFeature[];
  internal?: string[];
  doc?: Record<string, unknown>;
  status: string;
  error_detail?: string;
  triggered_by?: string;
  created_at?: string | null;
  updated_at?: string | null;
  dry_run?: boolean;
  doc_ready?: boolean;
  create_artifacts?: boolean;
  artifacts?: { feature: string; file_id?: string; doc_id?: string; url?: string; pdf_path?: string; image?: string }[];
};
export type DriveStatus = {
  configured?: boolean;
  mode?: string;
  label?: string;
};
export type FeatureArtifact = {
  feature: string;
  format?: string;
  filename?: string;
  pdf_path?: string;
  file_id?: string;
  url?: string;
  branch?: string;
  created_at?: string | null;
};
export type CommsKind = "whatsapp" | "release_notes" | "newsletter" | "pack";
export type ReleasePack = {
  id: number;
  kind?: CommsKind;
  title: string;
  angle?: string;
  internal_update: string;
  whatsapp?: string;
  release_notes: string;
  newsletter: NewsletterItem[];
  newsletter_intro?: string;
  newsletter_closer?: string;
  newsletter_markdown?: string;
  snapshot_id?: number;
  branch?: string;
  commit_sha?: string;
  llm_used?: boolean;
  artifacts?: { feature: string; file_id?: string; doc_id?: string; url?: string; pdf_path?: string; image?: string }[];
  created_at?: string | null;
};
export type Prd = {
  id: number;
  title: string;
  problem?: string;
  service?: string;
  issue_key?: string;
  issue_keys?: string[];
  markdown: string;
  sources?: { type?: string; ref?: string }[];
  snapshot_id?: number;
  branch?: string;
  commit_sha?: string;
  llm_used?: boolean;
  created_at?: string | null;
};
export type RoadmapAttachment = {
  id?: string;
  kind: "pdf" | "sheet" | "link";
  name: string;
  url: string;
};
export type RoadmapTicket = {
  key: string;
  summary: string;
  status?: string;
  priority?: string;
  assignee?: string;
  issue_type?: string;
  due_date?: string;
  url?: string;
  month?: string;
  note?: string;
  attachments?: RoadmapAttachment[];
};
export type RoadmapEpic = {
  key: string;
  title: string;
  status?: string;
  assignee?: string;
  priority?: string;
  url?: string;
  note?: string;
  tickets?: RoadmapTicket[];
};
export type Roadmap = {
  id: number;
  year: number;
  quarter: number;
  label: string;
  months: string[];
  month_labels: string[];
  current_month?: string;
  epics: RoadmapEpic[];
  notes?: string;
  llm_used?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  ticket_count?: number;
  epic_count?: number;
};
export type CopilotAction = {
  id: string;
  kind: string;
  ready?: boolean;
  needs_epic?: boolean;
  missing?: string[];
  blocked?: string;
  preview?: string;
  project?: string;
  issue_type?: string;
  summary?: string;
  description?: string;
  fields?: Record<string, string>;
  assignee?: string;
  parent_epic?: string;
  issue_key?: string;
  body?: string;
  transition?: string;
  from_status?: string;
  to_status?: string;
  image_ids?: string[];
};
export type CopilotPlan = {
  history?: {role?: string; text?: string}[];
  parent_plan_id?: number;
  context?: { document_ids?: number[]; note_ids?: number[]; prototype_ids?: number[]; prd_id?: number; code_scope?: string; code_files?: number; sha?: string; retrieval_note?: string };
  id: number;
  prompt?: string;
  notes?: string;
  branch?: string;
  ticket_keys?: string[];
  people?: string[];
  image_ids?: string[];
  answer?: string;
  actions?: CopilotAction[];
  questions?: string[];
  epics?: { key: string; title: string; status?: string }[];
  citations?: { path?: string; note?: string; url?: string }[];
  needs_confirm?: boolean;
  status?: string;
  results?: { id?: string; ok?: boolean; kind?: string; issue_key?: string; error?: string; attached?: string[]; from_status?: string; to_status?: string; undo?: { kind?: string; issue_key?: string; transition?: string } | null }[];
  llm_used?: boolean;
  ready_count?: number;
  blocked_count?: number;
  permission?: string;
  created_at?: string | null;
  ran_at?: string | null;
  plan_hash?: string;
};
export type PrototypeFile = { path: string; content: string };
export type PrototypeMessage = { id: number; role: string; body: string; created_at?: string | null };
export type PrototypeSession = {
  id: number;
  title: string;
  status: string;
  error?: string;
  llm_used?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  file_count?: number;
  files?: PrototypeFile[];
  messages?: PrototypeMessage[];
};
export type BackgroundJob = {
  id: number;
  kind?: string;
  status?: string;
  steps?: Record<string, { ok?: boolean; status?: string; error?: string; jira_count?: number; cliq_count?: number; branch?: string; pulled?: boolean; already_up_to_date?: boolean; stashed?: boolean; count?: number; remote_blocked?: boolean }>;
  result?: Record<string, unknown>;
  error?: string;
  created_at?: string | null;
  finished_at?: string | null;
};
export type CopilotMention = {
  kind: "ticket" | "person" | "branch" | string;
  key: string;
  label: string;
  summary?: string;
  status?: string;
  role?: string;
  type?: string;
  epic?: string;
  date?: string;
};
export type CopilotFile = { id: string; name: string; mime?: string; url: string };
export type Competitor = {
  id: number;
  slug: string;
  name: string;
  aliases?: string[];
  website?: string;
  changelog_url?: string;
  blog_url?: string;
  pricing_url?: string;
  g2_url?: string;
  notes?: string;
  active?: boolean;
  last_fetched_at?: string | null;
};
export type CompetitorSignal = {
  id: number;
  competitor_id?: number;
  competitor_name: string;
  source: string;
  title: string;
  summary: string;
  url: string;
  tag: string;
  ask_eng: string;
  seen_at?: string | null;
};
export type CompetitorDigest = {
  shipped: CompetitorSignal[];
  messaging: CompetitorSignal[];
  pricing: CompetitorSignal[];
  ask_eng: { competitor: string; ask_eng: string; title: string; id: number }[];
  generated_at?: string;
};
export type ParityCapability = {
  id: number;
  name: string;
  source?: string;
  epic_key?: string;
  coverage: Record<string, string>;
  notes?: string;
};
export type ParityGap = {
  signal_id: number;
  competitor: string;
  title: string;
  url?: string;
  reason: string;
  ask_eng?: string;
};
export type PricingSnapshot = {
  id: number;
  competitor_id: number;
  competitor_name: string;
  url: string;
  changed: boolean;
  change_note: string;
  excerpt: string;
  fetched_at?: string | null;
};
export type MarketWatch = {
  id: number;
  category: string;
  name: string;
  url: string;
  notes?: string;
  last_fetched_at?: string | null;
};
export type MarketSignal = {
  id: number;
  watch_id?: number;
  category: string;
  source_name: string;
  title: string;
  summary: string;
  url: string;
  affects_roadmap: "yes" | "no" | "watch" | string;
  seen_at?: string | null;
};

function isInterruptedJob(error: unknown) {
  return /interrupted|restarted|Retrying is safe/i.test(String(error || ""));
}

async function runRefresh(onStep?: (job: BackgroundJob) => void) {
  clearHttpCache();
  const response = await fetch("/api/refresh", { method: "POST", body: "{}", headers: { "Content-Type": "application/json" }, cache: "no-store" });
  if (response.status === 202) {
    const job = (await response.json()) as BackgroundJob;
    const result = await pollJob<{ ok?: boolean; error?: string; steps?: BackgroundJob["steps"] }>(job.id, onStep);
    return {
      ok: Boolean(result.ok),
      error: result.error || "",
      steps: (result.steps || job.steps || {}) as NonNullable<BackgroundJob["steps"]>,
    };
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json() as Promise<{
    ok: boolean;
    error?: string;
    steps: NonNullable<BackgroundJob["steps"]>;
  }>;
}

async function pollJob<T>(jobId: number, onStep?: (job: BackgroundJob) => void, timeoutMs = 8 * 60 * 1000): Promise<T> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const job = await request<BackgroundJob>(`/api/jobs/${jobId}`);
    onStep?.(job);
    if (job.status === "completed") return (job.result || job) as T;
    if (job.status === "failed") {
      const detail = job.error || (job.result as { error?: string } | undefined)?.error || "Job failed";
      throw new Error(detail);
    }
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
  throw new Error("Timed out waiting for the job.");
}

export type LlmProviderSettings = {
  id: string;
  label: string;
  protocol: string;
  base_url: string;
  project?: string;
  api_key_set?: boolean;
  api_key_hint?: string;
  api_key?: string;
  clear_api_key?: boolean;
};

export type LlmRouteSettings = { provider: string; model: string };

export type WorkspaceSettings = {
  pm_display_name: string;
  pm_cliq_user_id: string;
  pm_cliq_mentions: string;
  timezone: string;
  data_branch?: string;
  jira?: {
    base_url: string;
    email: string;
    projects: string;
    token_set: boolean;
    token_hint?: string;
    configured: boolean;
  };
  cliq?: {
    client_id: string;
    api_domain: string;
    accounts_url: string;
    redirect_uri?: string;
    pm_email?: string;
    pm_chat_id?: string;
    client_secret_set: boolean;
    refresh_token_set: boolean;
    access_token_set: boolean;
    client_secret_hint?: string;
    refresh_token_hint?: string;
    access_token_hint?: string;
    configured: boolean;
  };
  llm?: {
    providers: LlmProviderSettings[];
    routes: Record<string, LlmRouteSettings>;
    route_labels?: Record<string, string>;
    configured: boolean;
  };
  mail?: {
    release_notes_email: string;
    smtp_host: string;
    smtp_port: number;
    smtp_user: string;
    smtp_from: string;
    smtp_use_tls: boolean;
    password_set: boolean;
    password_hint?: string;
    cron_token_set?: boolean;
    cron_token_hint?: string;
  };
  workspace?: {
    codebase_path: string;
    data_branch?: string;
    product_internal_chat_id?: string;
    gdrive_folder_id?: string;
    gdrive_assets_folder_id?: string;
    gdrive_domain?: string;
    marketing_sheet_id?: string;
    marketing_sheet_tab?: string;
    cartesia_voice_id?: string;
    cartesia_model?: string;
    cartesia_key_set?: boolean;
    cartesia_key_hint?: string;
    gdrive_key_set?: boolean;
    gdrive_key_hint?: string;
  };
  people?: Record<string, string>;
  connections?: { jira?: boolean; cliq?: boolean; llm?: boolean };
  security?: {
    encrypted?: boolean;
    segments?: Record<string, { encrypted?: boolean; set?: boolean }>;
  };
};

export type WorkspaceSettingsPatch = {
  pm_display_name?: string;
  pm_cliq_user_id?: string;
  pm_cliq_mentions?: string;
  timezone?: string;
  data_branch?: string;
  jira?: Record<string, unknown>;
  cliq?: Record<string, unknown>;
  llm?: { providers?: LlmProviderSettings[]; routes?: Record<string, LlmRouteSettings> };
  mail?: Record<string, unknown>;
  workspace?: Record<string, unknown>;
  people?: Record<string, string>;
};

const API = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return httpJson<T>(`${API}${path}`, init);
}

export const api = {
  dashboard: (section: string) => request<{standup: Partial<Standup> | null}>(`/api/dashboard/${section}`),
  workspaceSummary: () => request<{ pm_display_name: string; data_branch: string; jira: boolean; cliq: boolean; llm: boolean; last_run_age_seconds?: number; last_run_stale?: boolean; dead_letter?: boolean }>("/api/workspace/summary"),
  notes: (q = "", offset = 0, kind = "", day = "") =>
    request<{notes: DailyNote[]; total: number}>(`/api/notes?q=${encodeURIComponent(q)}&kind=${encodeURIComponent(kind)}&day=${encodeURIComponent(day)}&offset=${offset}`),
  prototypes: () => request<{ prototypes: PrototypeSession[] }>("/api/prototypes"),
  prototype: (id: number) => request<PrototypeSession>(`/api/prototypes/${id}`),
  createPrototype: async (body: { title?: string; prompt?: string } = {}, onStep?: (job: BackgroundJob) => void) => {
    const response = await fetch("/api/prototypes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (response.status === 202) {
      clearHttpCache();
      const job = (await response.json()) as BackgroundJob & { prototype_id?: number };
      await pollJob<{ ok?: boolean; title?: string; files?: string[] }>(job.id, onStep, 4 * 60 * 1000);
      if (!job.prototype_id) throw new Error("Prototype job did not return an id.");
      return request<PrototypeSession>(`/api/prototypes/${job.prototype_id}`);
    }
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    clearHttpCache();
    return response.json() as Promise<PrototypeSession>;
  },
  prototypeTurn: async (id: number, prompt: string, onStep?: (job: BackgroundJob) => void, target = "") => {
    const job = await request<BackgroundJob>(`/api/prototypes/${id}/turn`, { method: "POST", body: JSON.stringify({ prompt, target }) });
    return pollJob<{ ok?: boolean; title?: string; files?: string[]; llm_used?: boolean }>(job.id, onStep, 10 * 60 * 1000);
  },
  savePrototypeFile: (id: number, path: string, content: string) =>
    request<PrototypeSession>(`/api/prototypes/${id}/files`, { method: "PUT", body: JSON.stringify({ path, content }) }),
  prototypeExportUrl: (id: number) => `/api/prototypes/${id}/export`,
  prototypePreviewUrl: (id: number, revision = "") =>
    `/api/prototypes/${id}/preview${revision ? `?v=${encodeURIComponent(revision)}` : ""}`,
  note: (id: number) => request<DailyNote>(`/api/notes/${id}`),
  saveNote: (body: Omit<DailyNote, "id" | "updated_at" | "actionable_count">, id?: number) => request<DailyNote>(id ? `/api/notes/${id}` : "/api/notes", {method: id ? "PUT" : "POST", body: JSON.stringify(body)}),
  deleteNote: (id: number) => request<{ ok: boolean; id: number }>(`/api/notes/${id}`, { method: "DELETE" }),
  assistNote: (body: { action: "summarize" | "structure" | "extract"; title?: string; body?: string; learning?: string; blocks?: NoteBlock[] }) =>
    request<{ title: string; blocks: NoteBlock[]; llm_used?: boolean }>("/api/notes/assist", { method: "POST", body: JSON.stringify(body) }),
  documents: (q = "", offset = 0) => request<{documents: LibraryDocument[]; total: number}>(`/api/library/documents?q=${encodeURIComponent(q)}&offset=${offset}`),
  document: (id: number) => request<LibraryDocument>(`/api/library/documents/${id}`),
  updateDocument: (id: number, body: {title?: string; status?: string; tags?: string[]}) => request<LibraryDocument>(`/api/library/documents/${id}`, {method: "PATCH", body: JSON.stringify(body)}),
  uploadDocument: async (file: File) => {
    const body = new FormData(); body.append("file", file);
    const response = await fetch("/api/library/documents", {method:"POST", body});
    if (!response.ok) { const error = await response.json().catch(() => ({detail: "Upload failed. Please retry."})); throw new Error(error.detail); }
    clearHttpCache();
    return response.json() as Promise<LibraryDocument>;
  },
  sourceIndex: (branch: string) => request<SourceIndex>(`/api/codebase/source-index?branch=${encodeURIComponent(branch)}`),
  prepareSources: async (branch: string, onStep?: (job: BackgroundJob) => void) => {
    const job = await request<BackgroundJob>("/api/codebase/source-index", {method:"POST", body:JSON.stringify({branch, pull:false})});
    return pollJob<SourceIndex>(job.id, onStep);
  },
  refreshSection: async (section: string, onStep?: (job: BackgroundJob) => void) => {
    const job = await request<BackgroundJob>(`/api/refresh/${section}`, {method:"POST"});
    return pollJob<{ok?: boolean; error?: string; steps?: Record<string, any>}>(job.id, onStep);
  },
  health: () =>
    request<{
      ok: boolean;
      jira: boolean;
      cliq: boolean;
      llm: boolean;
      timezone: string;
      now?: string;
      now_label?: string;
      period?: string;
      headline?: string;
      cliq_user_id?: string;
      pm_name?: string;
      last_run_at?: string | null;
      last_run_age_seconds?: number | null;
      last_run_stale?: boolean;
      dead_letter?: boolean;
    }>("/api/health"),
  platform: () =>
    request<{
      app_name: string;
      pm_display_name: string;
      pm_cliq_user_id: string;
      pm_cliq_mentions: string;
      timezone: string;
      data_branch?: string;
      boards: { AC: number; PS: number };
      hidden_count: number;
      connections: { jira: boolean; cliq: boolean; llm: boolean };
      jira_email?: string;
      jira_base_url?: string;
    }>("/api/platform"),
  settings: () => request<WorkspaceSettings>("/api/settings"),
  saveSettings: (body: WorkspaceSettingsPatch) =>
    request<WorkspaceSettings>("/api/settings", { method: "PATCH", body: JSON.stringify(body) }),
  captureSettings: () => request<WorkspaceSettings>("/api/settings/capture", { method: "POST" }),
  latest: () => request<{ standup: Standup | null }>("/api/standup/latest"),
  run: () => request<{ run: Record<string, unknown>; standup: Standup | null }>("/api/pipeline/run", { method: "POST" }),
  refreshAll: async (onStep?: (job: BackgroundJob) => void) => {
    try {
      return await runRefresh(onStep);
    } catch (err) {
      if (!isInterruptedJob(err)) throw err;
      onStep?.({ id: 0, status: "queued", error: "", steps: { jira: { status: "running" } } });
      return await runRefresh(onStep);
    }
  },
  deliver: () => request<{ ok: boolean }>("/api/standup/deliver", { method: "POST" }),
  ask: (query: string) => request<{ answer: string; items: unknown; searched?: number }>("/api/standup/ask", { method: "POST", body: JSON.stringify({ query }) }),
  attachWeekTicket: (body: { issue_key: string; title?: string; card_key?: string }) =>
    request<{ ok: boolean; item: StandupItem }>("/api/standup/attach-ticket", { method: "POST", body: JSON.stringify(body) }),
  copilotPlan: (body: { document_ids?: number[]; note_ids?: number[]; prototype_ids?: number[]; parent_plan_id?: number; code_scope?: string; prompt?: string; notes?: string; branch?: string; ticket_keys?: string[]; people?: string[]; image_ids?: string[] }) =>
    request<CopilotPlan>("/api/copilot/plan", { method: "POST", body: JSON.stringify(body) }),
  copilotPlanGet: (planId: number) => request<CopilotPlan>(`/api/copilot/plans/${planId}`),
  copilotRun: (body: { plan_id: number; approved: boolean; action_ids: string[]; overrides?: Record<string, Record<string, unknown>> }) =>
    request<CopilotPlan>("/api/copilot/run", { method: "POST", body: JSON.stringify(body) }),
  copilotUndo: (planId: number) => request<CopilotPlan>("/api/copilot/undo", { method: "POST", body: JSON.stringify({ plan_id: planId }) }),
  copilotThread: () => request<{ id: number; turns: { role?: string; text?: string; plan_id?: number }[]; plans: CopilotPlan[] }>("/api/copilot/conversations"),
  copilotMentions: (q = "") =>
    request<{ tickets: CopilotMention[]; people: CopilotMention[]; branches: CopilotMention[]; prototypes?: CopilotMention[] }>(`/api/copilot/mentions?q=${encodeURIComponent(q)}`),
  uploadCopilotFile: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch("/api/copilot/files", { method: "POST", body, cache: "no-store" });
    if (!response.ok) {
      const text = await response.text();
      let detail = text || response.statusText;
      try {
        const parsed = JSON.parse(text);
        if (parsed?.detail) detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
      } catch {
        /* keep text */
      }
      throw new Error(detail);
    }
    clearHttpCache();
    return response.json() as Promise<CopilotFile>;
  },
  issuesPage: (board: string, q: string, kind: string, state: string, offset: number) => request<{ issues: Issue[]; total: number; connected: boolean }>(`/api/issues?${new URLSearchParams({board,q,kind,state,offset:String(offset),limit:"20",compact:"true"})}`),
  issues: (board?: string) => request<{ issues: Issue[]; connected?: boolean; board?: string }>(`/api/issues?${new URLSearchParams({ ...(board ? { board } : {}), compact: "true" })}`),
  releaseAsks: () => request<ReleaseAsks>("/api/release-asks"),
  dismissReleaseAsk: (issueKey: string) =>
    request<{ ok: boolean; issue_key: string; dismissed: string[] }>("/api/release-asks/dismiss", { method: "POST", body: JSON.stringify({ issue_key: issueKey }) }),
  nudgeReleaseAsks: (pm: string) =>
    request<{ ok: boolean; sent: { pm: string; ok: boolean; via: string; count: number; keys?: string[] }[]; last_nudged_at?: string; errors?: string[] }>(
      "/api/release-asks/nudge",
      { method: "POST", body: JSON.stringify({ pm }) },
    ),
  jiraSchemas: () => request<{ connected: boolean; bug: { key: string; label: string; required: boolean }[]; task: { key: string; label: string; required: boolean }[]; report: { key: string; label: string; required: boolean }[]; why_unknown: string | null }>("/api/jira/schemas"),
  hideCard: (body: { issue_key?: string; title?: string; card_key?: string }) => request<{ ok: boolean; card_key: string }>("/api/cards/hide", { method: "POST", body: JSON.stringify(body) }),
  hiddenCards: () => request<{ hidden: { card_key: string; title: string }[] }>("/api/cards/hidden"),
  unhideCard: (cardKey: string) => request<{ ok: boolean }>(`/api/cards/hide?card_key=${encodeURIComponent(cardKey)}`, { method: "DELETE" }),
  issue: (key: string) => request<Record<string, unknown>>(`/api/issues/${key}`),
  messages: () => request<{ messages: Record<string, unknown>[] }>("/api/messages"),
  cliqDigest: () => request<CliqBriefing>("/api/cliq/digest"),
  insights: () => request<{ insights: Record<string, unknown>[] }>("/api/insights"),
  runs: () => request<{ runs: Record<string, unknown>[] }>("/api/runs"),
  codebaseStatus: () => request<CodebaseStatus>("/api/codebase/status"),
  codebaseUpdate: () => request<CodebaseStatus>("/api/codebase/update", { method: "POST" }),
  codebaseBranches: (fetchRemote = false) =>
    request<{ ok?: boolean; error?: string; fetched?: boolean; remote_blocked?: boolean; current?: string; base?: string; branches: CodebaseBranch[] }>(
      `/api/codebase/branches?fetch=${fetchRemote ? "true" : "false"}`,
      { method: "POST", body: "{}" },
    ),
  codebaseIndex: async (branch: string, onStep?: (job: BackgroundJob) => void) => {
    const response = await fetch("/api/codebase/index", {
      method: "POST",
      body: JSON.stringify({ branch, pull: true }),
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
    if (response.status === 202) {
      clearHttpCache();
      const job = (await response.json()) as BackgroundJob;
      return pollJob<CodebaseStatus>(job.id, onStep);
    }
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    return response.json() as Promise<CodebaseStatus>;
  },
  codebaseQueryIndex: (branch: string) =>
    request<CodebaseQueryIndex>(`/api/codebase/query-index?branch=${encodeURIComponent(branch)}`),
  codebasePrepareQuery: (branch: string) =>
    request<CodebaseQueryIndex>("/api/codebase/query-index", { method: "POST", body: JSON.stringify({ branch, pull: false }) }),
  codebaseAsk: (question: string, branch = "") =>
    request<CodebaseAsk>("/api/codebase/ask", { method: "POST", body: JSON.stringify({ question, branch }) }),
  codebaseAsks: () => request<{ asks: CodebaseAsk[] }>("/api/codebase/asks"),
  codebaseLive: () => request<CodebaseStatus>("/api/codebase/live", { method: "POST", body: "{}" }),
  codebaseSetDataBranch: (branch: string) =>
    request<CodebaseStatus>("/api/codebase/data-branch", { method: "POST", body: JSON.stringify({ branch }) }),
  prds: () => request<{ prds: Prd[]; codebase: CodebaseStatus }>("/api/prd"),
  prd: (id: number) => request<Prd>(`/api/prd/${id}`),
  generatePrd: (body: { title: string; problem: string; service?: string; issue_key?: string; issue_keys?: string[]; prototype_id?: number }) =>
    request<Prd>("/api/prd/generate", { method: "POST", body: JSON.stringify(body) }),
  prdPdfUrl: (id: number) => `/api/prd/${id}/pdf`,
  comms: () =>
    request<{
      packs: ReleasePack[];
      codebase: CodebaseStatus;
      release_job?: ReleaseNotesJob | null;
      release_jobs?: ReleaseJob[];
      pending_releases?: ReleaseJob[];
      drive?: DriveStatus;
      drive_configured?: boolean;
      release_hour?: number;
      release_email?: string;
      smtp_ready?: boolean;
    }>("/api/comms"),
  generateComms: (body: { title?: string; angle?: string; kind?: CommsKind; artifacts?: boolean }) =>
    request<ReleasePack>("/api/comms/generate", { method: "POST", body: JSON.stringify(body) }),
  commsPack: (id: number) => request<ReleasePack>(`/api/comms/${id}`),
  approveReleaseJob: (id: number) => request<ReleaseJob>(`/api/comms/release-jobs/${id}/approve`, { method: "POST", body: "{}" }),
  regenerateReleaseJob: (id: number, body: { checked?: string[]; features_in_short?: string; artifacts?: boolean }) =>
    request<ReleaseJob>(`/api/comms/release-jobs/${id}/regenerate`, { method: "POST", body: JSON.stringify(body) }),
  retryReleaseJob: (id: number) => request<ReleaseJob>(`/api/comms/release-jobs/${id}/retry`, { method: "POST", body: "{}" }),
  uploadRoadmapFile: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch("/api/roadmap/files", { method: "POST", body, cache: "no-store" });
    if (!response.ok) {
      const text = await response.text();
      let detail = text || response.statusText;
      try {
        const parsed = JSON.parse(text);
        if (parsed?.detail) detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
      } catch {
        /* keep text */
      }
      throw new Error(detail);
    }
    clearHttpCache();
    return response.json() as Promise<RoadmapAttachment>;
  },
  runReleaseNotes: (force = false) =>
    request<{ job: ReleaseNotesJob | null; pack: ReleasePack | null; status: CodebaseStatus }>(
      `/api/comms/release-notes/run?force=${force ? "true" : "false"}`,
      { method: "POST", body: "{}" },
    ),
  roadmap: () => request<{ roadmap: Roadmap | null }>("/api/roadmap"),
  generateRoadmap: () => request<Roadmap>("/api/roadmap/generate", { method: "POST" }),
  saveRoadmap: (body: { notes?: string; epics: RoadmapEpic[] }) => request<Roadmap>("/api/roadmap", { method: "PATCH", body: JSON.stringify(body) }),
  artifacts: () =>
    request<{ artifacts: FeatureArtifact[]; codebase: CodebaseStatus; drive_configured?: boolean }>("/api/artifacts"),
  createArtifact: async (body: { feature: string; notes?: string; format?: "brief" | "deck" }, onStep?: (job: BackgroundJob) => void) => {
    const response = await fetch("/api/artifacts", {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
    if (response.status === 202) {
      clearHttpCache();
      const job = (await response.json()) as BackgroundJob;
      return pollJob<{ ok?: boolean; artifacts?: FeatureArtifact[]; error?: string }>(job.id, onStep, 18 * 60 * 1000);
    }
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    return response.json() as Promise<{ ok?: boolean; artifacts?: FeatureArtifact[] }>;
  },
  artifactPdfUrl: (filename: string) => `/api/artifacts/files/${encodeURIComponent(filename)}`,
  competitors: () =>
    request<{
      competitors: Competitor[];
      digest: CompetitorDigest;
      counts: { rivals: number; shipped: number; pricing: number; ask_eng: number };
    }>("/api/competitors"),
  competitorsDigest: () => request<CompetitorDigest>("/api/competitors/digest"),
  competitorSignals: (filters: {view:string;q:string;rival:number;focus:string;tag:string;snapshots:boolean;offset:number;limit:number}) => request<{signals:(CompetitorSignal & {focus:string[];news_tag:string;ai_area?:string;maturity?:string;release_status:string;is_snapshot:boolean;sense_relevance:string;excerpt:string})[];total:number}>(`/api/competitors/signals?${new URLSearchParams(Object.entries(filters).map(([k,v])=>[k,String(v)]))}`),
  createNewsTask: (id: number) => request<CopilotPlan>(`/api/competitors/signals/${id}/ticket`, {method:"POST"}),
  refreshAINews: async () => {
    const job = await request<BackgroundJob>("/api/competitors/ai/refresh", {method:"POST"});
    const result = await pollJob<{ok:boolean;sources:{error?:string;watch?:string}[];created?:number;failed?:number;error?:string}>(job.id);
    if (!result.ok) {
      const failed = (result.sources || []).filter(s => s.error).map(s => s.watch || "source");
      throw new Error(result.error || (failed.length ? `AI news sources unavailable: ${failed.join(", ")}` : "AI news refresh failed."));
    }
    return result;
  },
  competitorsParity: () =>
    request<{ competitors: Competitor[]; capabilities: ParityCapability[]; gap_suggestions: ParityGap[] }>("/api/competitors/parity"),
  competitorsPricing: () => request<{ snapshots: PricingSnapshot[] }>("/api/competitors/pricing"),
  competitorsMarket: (category?: string) =>
    request<{ watches: MarketWatch[]; signals: MarketSignal[] }>(
      `/api/competitors/market${category ? `?category=${encodeURIComponent(category)}` : ""}`,
    ),
  saveCompetitor: (body: Partial<Competitor> & { name: string }, id?: number) =>
    request<Competitor>(id ? `/api/competitors/${id}` : "/api/competitors", {
      method: id ? "PATCH" : "POST",
      body: JSON.stringify(body),
    }),
  deactivateCompetitor: (id: number) => request<{ ok: boolean }>(`/api/competitors/${id}`, { method: "DELETE" }),
  setParityCell: (capabilityId: number, competitor_slug: string, level: string) =>
    request<{ id: number; name: string; coverage: Record<string, string> }>(`/api/competitors/parity/${capabilityId}`, {
      method: "POST",
      body: JSON.stringify({ competitor_slug, level }),
    }),
  addParityCapability: (body: { name: string; epic_key?: string; notes?: string }) =>
    request<{ id: number; name: string; epic_key: string; coverage: Record<string, string> }>("/api/competitors/parity/capabilities", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setMarketAffects: (signalId: number, affects_roadmap: "yes" | "no" | "watch") =>
    request<MarketSignal>(`/api/competitors/market/${signalId}/affects`, {
      method: "POST",
      body: JSON.stringify({ affects_roadmap }),
    }),
  refreshCompetitors: async (onStep?: (job: BackgroundJob) => void) => {
    const response = await fetch("/api/competitors/refresh", { method: "POST", cache: "no-store" });
    if (response.status === 202) {
      clearHttpCache();
      const job = (await response.json()) as BackgroundJob;
      return pollJob<{ ok?: boolean; competitors?: unknown[]; market?: unknown[]; error?: string }>(job.id, onStep, 12 * 60 * 1000);
    }
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    return response.json();
  },
};
