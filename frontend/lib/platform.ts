import { httpJson } from "@/lib/http";

export type Role = "owner" | "admin" | "member";

export type WorkspaceSummary = {
  id: number;
  slug: string;
  name: string;
  kind: "personal" | "organization";
  role: Role | "";
  timezone: string;
  product_name: string;
  company_name: string;
  clerk_org_id: string;
  onboarded: boolean;
  created_at: string | null;
};

export type Me = {
  user: { id: number; email: string; name: string; avatar_url: string };
  workspace: WorkspaceSummary;
  role: Role;
  workspaces: WorkspaceSummary[];
  auth_mode: "local" | "clerk";
};

export type Profile = {
  product_name: string;
  company_name: string;
  product_description: string;
  website: string;
  industries: string;
  tone: string;
  pm_display_name: string;
  pm_personas: string;
  pm_cliq_user_id: string;
  pm_cliq_mentions: string;
  project_keywords: string;
  jira_allowed_projects: string;
  jira_scope_rules: string;
  support_email: string;
  newsletter_sender: string;
  competitor_focus: string;
  competitor_pack: string;
  product_modules: string;
  brand_rules: string;
  brand: Record<string, string>;
  data_branch: string;
  prototype_kit: string;
  standup_hour: number;
  standup_nudge_minute: number;
  release_notes_hour: number;
};

export type OnboardingStep = { id: "profile" | "connections" | "repository" | "people"; label: string; done: boolean };
export type WorkspaceDetail = WorkspaceSummary & {
  profile: Profile;
  onboarding: { steps: OnboardingStep[]; complete: boolean; dismissed: boolean };
};

export type ProviderField = {
  key: string;
  label: string;
  kind: "text" | "secret" | "url" | "email" | "number" | "bool" | "select" | "json" | "textarea";
  secret: boolean;
  required: boolean;
  placeholder: string;
  help: string;
  default: unknown;
  options: string[];
  advanced: boolean;
};

export type ConnectionStatus = "connected" | "error" | "untested" | "incomplete" | "disconnected";
export type ConnectionView = {
  provider: string;
  name: string;
  connected: boolean;
  status: ConnectionStatus;
  last_verified_at: string | null;
  last_error: string;
  updated_at?: string | null;
  updated_by?: string;
  config?: Record<string, unknown>;
  secrets?: Record<string, { set: boolean; hint: string }> | Record<string, Record<string, string>>;
  verified?: Record<string, unknown>;
};

export type Provider = {
  id: string;
  name: string;
  category: string;
  description: string;
  help_url: string;
  custom_ui: string;
  multiple: boolean;
  used_by: string[];
  fields: ProviderField[];
  connections: ConnectionView[];
};

export type ConnectionsResponse = { providers: Provider[]; can_edit: boolean; cliq_redirect_uri: string };
export type TestOutcome = { ok: boolean; message: string; details?: Record<string, unknown> };

export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type RunStep = { status?: string; ok?: boolean; error?: string; [key: string]: unknown };
export type Run = {
  id: number;
  kind: string;
  pipeline_id: string;
  pipeline_name?: string;
  task: string;
  status: RunStatus;
  trigger: "manual" | "schedule" | "chained" | string;
  started_by: string;
  params: Record<string, unknown>;
  steps: Record<string, RunStep>;
  result: Record<string, unknown>;
  error: string;
  attempts: number;
  cancel_requested: boolean;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_s: number | null;
};
export type RunLog = { at: string; level: string; message: string };
export type RunDetail = Run & { logs: RunLog[]; cost: Record<string, unknown>; children: Run[] };

export type PipelineStatus = "ready" | "needs_connection" | "connection_error" | "queued" | "running";
export type SettingField = { key: string; label: string; kind: "text" | "number" | "bool" | "select" | "textarea"; default: unknown; help: string; options: string[] };
export type Pipeline = {
  id: string;
  name: string;
  category: "system" | "product" | "marketing" | "knowledge";
  category_label: string;
  description: string;
  output: string;
  icon: string;
  requires: string[];
  optional: string[];
  runnable: boolean;
  interactive: boolean;
  status: PipelineStatus;
  readiness: { status: string; missing: string[]; failing: string[]; optional_missing: string[] };
  steps: string[];
  chain: string[];
  settings_schema: SettingField[];
  settings: Record<string, unknown>;
  enabled: boolean;
  schedule: string;
  default_schedule: string;
  schedule_enabled: boolean;
  last_fired_at: string | null;
  next_run_at: string | null;
  last_run: { id: number; status: RunStatus; trigger: string; created_at: string | null; finished_at: string | null; error: string } | null;
};
export type PipelinesResponse = { pipelines: Pipeline[]; categories: Record<string, string>; can_edit: boolean; timezone: string };

export type Branch = {
  name: string;
  sha: string;
  committed_at: string;
  message: string;
  merged: boolean;
  merged_at: string;
  is_default: boolean;
  is_product: boolean;
  is_release: boolean;
  indexed: boolean;
};
export type FetchStatus = "never" | "ok" | "auth_failed" | "remote_blocked" | "not_found" | "error" | string;
export type Repository = {
  id: number;
  name: string;
  provider: string;
  remote_url: string;
  connection_id: number | null;
  mode: "managed" | "local";
  local_path: string;
  default_branch: string;
  product_branch: string;
  release_pattern: string;
  merge_format: string;
  path_scopes: string[];
  ui_path: string;
  is_primary: boolean;
  checkout_path: string;
  checkout_ready: boolean;
  mirror_ready: boolean;
  last_fetch_at: string | null;
  last_fetch_status: FetchStatus;
  last_fetch_error: string;
  indexed_branches: string[];
  branch_count: number;
  created_at: string | null;
  branches?: Branch[];
  sync_run: Run | null;
};
export type RepositoriesResponse = {
  repositories: Repository[];
  credentials: { id: number; provider: string; name: string; status: string }[];
  egress_ip: string;
  providers: string[];
  merge_formats: string[];
  local_allowed: boolean;
  can_edit: boolean;
};
export type RepositoryInput = Partial<Pick<Repository, "name" | "provider" | "remote_url" | "connection_id" | "mode" | "local_path" | "default_branch" | "product_branch" | "release_pattern" | "merge_format" | "ui_path" | "is_primary">> & { path_scopes?: string[] | string };

export type Person = {
  id: number;
  name: string;
  short: string;
  email: string;
  jira_account_id: string;
  cliq_user_id: string;
  cliq_chat_id: string;
  role: string;
  team: string;
  aliases: string[];
  active: boolean;
  notes: string;
};
export type Member = { id: number; user_id: number; email: string; name: string; avatar_url: string; role: Role; you: boolean; joined_at: string | null; last_seen_at: string | null };
export type MembersResponse = { members: Member[]; invitations: { id: string; email: string; role: Role }[]; roles: Role[]; can_invite: boolean };
export type AuditEvent = { id: number; action: string; target: string; actor: string; detail: Record<string, unknown>; at: string | null };
export type BrandStem = "logo-light" | "logo-dark" | "wordmark";
export type BrandAssets = { assets: Record<BrandStem, { uploaded: boolean; updated_at: string | null; accepts: string[] }> };

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });
const live: RequestInit = { cache: "no-store" };

export const platform = {
  me: () => httpJson<Me>("/api/me", live),
  createWorkspace: (name: string, timezone?: string) => httpJson<WorkspaceSummary>("/api/workspaces", { method: "POST", ...json({ name, timezone }) }),
  workspace: () => httpJson<WorkspaceDetail>("/api/workspace", live),
  saveWorkspace: (patch: { name?: string; timezone?: string; profile?: Partial<Profile> }) => httpJson<WorkspaceDetail>("/api/workspace", { method: "PATCH", ...json(patch) }),
  dismissOnboarding: () => httpJson<{ ok: boolean }>("/api/workspace/onboarding/dismiss", { method: "POST" }),
  brand: () => httpJson<BrandAssets>("/api/workspace/brand", live),
  uploadBrand: (stem: BrandStem, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return httpJson<BrandAssets>(`/api/workspace/brand/${stem}`, { method: "PUT", body });
  },
  removeBrand: (stem: BrandStem) => httpJson<BrandAssets>(`/api/workspace/brand/${stem}`, { method: "DELETE" }),

  connections: () => httpJson<ConnectionsResponse>("/api/connections", live),
  saveConnection: (provider: string, values: Record<string, unknown>, options: { clear?: string[]; name?: string; test?: boolean } = {}) =>
    httpJson<{ connection: ConnectionView; test: TestOutcome | null }>(`/api/connections/${provider}`, { method: "PUT", ...json({ values, clear: options.clear || [], name: options.name || "default", test: options.test ?? true }) }),
  testConnection: (provider: string, name = "default") => httpJson<TestOutcome & { connection: ConnectionView }>(`/api/connections/${provider}/test?name=${encodeURIComponent(name)}`, { method: "POST" }),
  disconnect: (provider: string, name = "default") => httpJson<{ ok: boolean }>(`/api/connections/${provider}?name=${encodeURIComponent(name)}`, { method: "DELETE" }),
  cliqAuthorize: () => httpJson<{ url: string; redirect_uri: string }>("/api/connections/cliq/authorize", live),

  pipelines: () => httpJson<PipelinesResponse>("/api/pipelines", live),
  pipeline: (id: string) => httpJson<Pipeline & { runs: Run[] }>(`/api/pipelines/${id}`, live),
  updatePipeline: (id: string, patch: { enabled?: boolean; schedule?: string; schedule_enabled?: boolean; settings?: Record<string, unknown> }) =>
    httpJson<Pipeline>(`/api/pipelines/${id}`, { method: "PATCH", ...json(patch) }),
  runPipeline: (id: string, params: Record<string, unknown> = {}) => httpJson<Run>(`/api/pipelines/${id}/run`, { method: "POST", ...json({ params }) }),

  runs: (filter: { pipeline?: string; status?: string; limit?: number; before?: number } = {}) => {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(filter)) if (value) query.set(key, String(value));
    const suffix = query.toString() ? `?${query}` : "";
    return httpJson<{ runs: Run[]; next_before: number | null }>(`/api/runs${suffix}`, live);
  },
  run: (id: number) => httpJson<RunDetail>(`/api/runs/${id}`, live),
  cancelRun: (id: number) => httpJson<Run>(`/api/runs/${id}/cancel`, { method: "POST" }),
  retryRun: (id: number) => httpJson<Run>(`/api/runs/${id}/retry`, { method: "POST" }),

  repositories: () => httpJson<RepositoriesResponse>("/api/repositories", live),
  repository: (id: number) => httpJson<Repository>(`/api/repositories/${id}`, live),
  addRepository: (body: RepositoryInput) => httpJson<Repository>("/api/repositories", { method: "POST", ...json(body) }),
  editRepository: (id: number, body: RepositoryInput) => httpJson<Repository>(`/api/repositories/${id}`, { method: "PATCH", ...json(body) }),
  removeRepository: (id: number) => httpJson<{ ok: boolean }>(`/api/repositories/${id}`, { method: "DELETE" }),
  syncRepository: (id: number) => httpJson<Run>(`/api/repositories/${id}/sync`, { method: "POST" }),
  testRepository: (id: number) => httpJson<{ ok: boolean; status: string; message: string; egress_ip: string }>(`/api/repositories/${id}/test`, { method: "POST" }),
  branches: (id: number, options: { refresh?: boolean; q?: string } = {}) =>
    httpJson<{ branches: Branch[]; product_branch: string; release_pattern: string; last_fetch_at: string | null; last_fetch_status: FetchStatus; last_fetch_error: string }>(
      `/api/repositories/${id}/branches?refresh=${options.refresh ? "true" : "false"}&q=${encodeURIComponent(options.q || "")}`,
      live,
    ),

  people: () => httpJson<{ people: Person[]; roles: string[] }>("/api/people", live),
  addPerson: (body: Partial<Person>) => httpJson<Person>("/api/people", { method: "POST", ...json(body) }),
  editPerson: (id: number, body: Partial<Person>) => httpJson<Person>(`/api/people/${id}`, { method: "PATCH", ...json(body) }),
  removePerson: (id: number) => httpJson<{ ok: boolean }>(`/api/people/${id}`, { method: "DELETE" }),

  members: () => httpJson<MembersResponse>("/api/members", live),
  changeRole: (id: number, role: Role) => httpJson<{ ok: boolean }>(`/api/members/${id}`, { method: "PATCH", ...json({ role }) }),
  removeMember: (id: number) => httpJson<{ ok: boolean }>(`/api/members/${id}`, { method: "DELETE" }),
  invite: (email: string, role: Role) => httpJson<{ ok: boolean; id?: string }>("/api/members/invite", { method: "POST", ...json({ email, role }) }),
  audit: (limit = 100) => httpJson<{ events: AuditEvent[] }>(`/api/audit?limit=${limit}`, live),
};

export const ACTIVE_RUN: RunStatus[] = ["queued", "running"];
export const isActive = (run?: { status: string } | null) => Boolean(run && (run.status === "queued" || run.status === "running"));
