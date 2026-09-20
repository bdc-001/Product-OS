import { api } from "@/lib/api";
import { marketingApi } from "@/lib/marketing";

const loaders: Record<string, () => Promise<unknown>> = {
  "/": () =>
    Promise.all([
      api.dashboard("summary"),
      api.dashboard("actions"),
      api.dashboard("developer-load"),
      api.hiddenCards(),
      api.workspaceSummary(),
    ]),
  "/jira": () => api.issuesPage("AC", "", "all", "all", 0),
  "/cliq": () => api.cliqDigest(),
  "/codebase": () => Promise.all([api.codebaseStatus(), api.codebaseAsks(), api.codebaseBranches(false)]),
  "/prototype": () => api.prototypes(),
  "/prd": () => Promise.all([api.prds(), api.issues("AC")]),
  "/roadmap": () => api.roadmap(),
  "/marketing": () => marketingApi.workspace(),
  "/artifacts": () => api.artifacts(),
  "/comms": () => api.comms(),
  "/competitors": () => api.competitors(),
  "/notes": () => api.notes(),
  "/lms": () => api.documents(),
  "/settings": () => Promise.all([api.settings(), api.platform()]),
};

const queued = new Set<string>();

export function prefetchSection(href: string) {
  const load = loaders[href];
  if (!load || queued.has(href)) return;
  queued.add(href);
  void load().catch(() => null).finally(() => queued.delete(href));
}
