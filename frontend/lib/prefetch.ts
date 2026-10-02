import { api } from "@/lib/api";
import { marketingApi } from "@/lib/marketing";
import { platform } from "@/lib/platform";

const loaders: Record<string, () => Promise<unknown>> = {
  "/": () => Promise.all([platform.workspace(), platform.connections(), platform.runs({ limit: 12 })]),
  "/week": () =>
    Promise.all([
      api.dashboard("summary"),
      api.dashboard("actions"),
      api.dashboard("developer-load"),
      api.hiddenCards(),
      api.workspaceSummary(),
    ]),
  "/settings/pipelines": () => Promise.all([platform.pipelines(), platform.runs({ limit: 30 })]),
  "/settings/connections": () => platform.connections(),
  "/settings/repositories": () => platform.repositories(),
  "/jira": () => api.platform(),
  "/cliq": () => api.cliqDigest(),
  "/codebase": () => Promise.all([api.codebaseStatus(), api.codebaseAsks(), api.codebaseBranches(false)]),
  "/prototype": () => api.prototypes(),
  "/prd": () => api.prds(),
  "/roadmap": () => api.roadmap(),
  "/marketing": () => marketingApi.workspace(),
  "/artifacts": () => api.artifacts(),
  "/comms": () => api.comms(),
  "/competitors": () => api.competitors(),
  "/notes": () => api.notes(),
  "/lms": () => api.documents(),
  "/settings": () => platform.workspace(),
  "/settings/profile": () => platform.workspace(),
  "/settings/people": () => platform.people(),
  "/settings/members": () => platform.members(),
};

const queued = new Set<string>();

export function prefetchSection(href: string) {
  const path = href.split("?")[0];
  const load = loaders[path];
  if (!load || queued.has(href)) return;
  queued.add(href);
  void load().catch(() => null).finally(() => queued.delete(href));
}
