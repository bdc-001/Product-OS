"use client";

import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import Box from "@mui/material/Box";
import ButtonBase from "@mui/material/ButtonBase";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { LlmForm, ProviderForm, ProviderMark, connectionTone } from "@/app/settings/connections/provider-form";
import { usePlatform } from "@/app/platform-state";
import { RepositoryForm } from "@/app/settings/repositories/repository-form";
import { Banner, LoadingBlock, PillButton } from "@/app/ui";
import { PipelineIcon, ToneChip, pipelineTone } from "@/app/ui/platform";
import { accent, apple, pmm } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { CreateWorkspaceDialog, WorkspaceMark } from "@/app/workspace-switcher";
import { platform, type ConnectionsResponse, type Person, type Profile, type RepositoriesResponse, type WorkspaceDetail } from "@/lib/platform";
import { clerkEnabled } from "@/lib/session";

const STEPS = [
  { id: "profile", title: "Your product", blurb: "What you build and who it is for." },
  { id: "connections", title: "Connect tools", blurb: "AI models, Jira, chat and docs." },
  { id: "repository", title: "Repository", blurb: "Where shipped code lives." },
  { id: "people", title: "Your team", blurb: "Names briefings should recognise." },
  { id: "done", title: "Ready", blurb: "See what you can run." },
] as const;
type StepId = (typeof STEPS)[number]["id"];

const TONES = ["Clear and direct", "Warm and friendly", "Technical and precise", "Bold and energetic"];
const PERSON_ROLES: Record<string, string> = { pm: "Product manager", dev: "Developer", qa: "QA", design: "Designer", notes_pm: "PM (notes only)", other: "Other" };
const ESSENTIAL = ["llm", "jira", "cliq", "google"];

function StepFrame({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <Box className="page-body" sx={{ display: "grid", gap: 3 }}>
      <Box>
        <Typography component="h1" sx={{ fontSize: { xs: 26, md: 32 }, fontWeight: 650, letterSpacing: "-0.035em", lineHeight: 1.1 }}>
          {title}
        </Typography>
        <Typography sx={{ mt: 1, fontSize: 15, color: apple.muted, maxWidth: 600, lineHeight: 1.55 }}>{subtitle}</Typography>
      </Box>
      {children}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, pt: 1 }}>{footer}</Box>
    </Box>
  );
}

function ProfileStep({ detail, canEdit, onNext }: { detail: WorkspaceDetail; canEdit: boolean; onNext: () => void }) {
  const [name, setName] = useState(detail.name);
  const [profile, setProfile] = useState<Partial<Profile>>(() => ({
    product_name: detail.profile.product_name,
    company_name: detail.profile.company_name,
    product_description: detail.profile.product_description,
    website: detail.profile.website,
    industries: detail.profile.industries,
    tone: detail.profile.tone || TONES[0],
    pm_display_name: detail.profile.pm_display_name,
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (patch: Partial<Profile>) => setProfile((current) => ({ ...current, ...patch }));

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit) return onNext();
    setBusy(true);
    setError("");
    try {
      await platform.saveWorkspace({ name: name.trim() || detail.name, profile });
      onNext();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box component="form" onSubmit={save}>
      <StepFrame
        title="Tell us about your product"
        subtitle="Briefings, release notes, PRDs and campaigns all read this. Write it the way you'd explain the product to a new teammate."
        footer={
          <>
            <PillButton type="submit" disabled={busy || !profile.product_name?.trim()} endIcon={<ArrowForwardRoundedIcon />}>
              {busy ? "Saving…" : "Continue"}
            </PillButton>
            <PillButton variant="text" onClick={onNext} sx={{ color: apple.muted }}>
              Skip for now
            </PillButton>
          </>
        }
      >
        <Box sx={{ display: "grid", gap: 2, maxWidth: 680 }}>
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
            <TextField label="Product name" value={profile.product_name || ""} onChange={(event) => set({ product_name: event.target.value })} required disabled={!canEdit} placeholder="Acme Analytics" />
            <TextField label="Company" value={profile.company_name || ""} onChange={(event) => set({ company_name: event.target.value })} disabled={!canEdit} placeholder="Acme Inc." />
          </Box>
          <TextField label="What it does" value={profile.product_description || ""} onChange={(event) => set({ product_description: event.target.value })} multiline minRows={3} disabled={!canEdit} placeholder="Acme Analytics helps support teams spot churn risk from every customer conversation…" helperText="Two or three sentences: the problem, who has it, and how the product solves it." />
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
            <TextField label="Website" value={profile.website || ""} onChange={(event) => set({ website: event.target.value })} disabled={!canEdit} placeholder="https://acme.com" />
            <TextField label="Industries you sell to" value={profile.industries || ""} onChange={(event) => set({ industries: event.target.value })} disabled={!canEdit} placeholder="SaaS, fintech, retail" />
          </Box>
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
            <TextField select label="Writing tone" value={TONES.includes(profile.tone || "") ? profile.tone : TONES[0]} onChange={(event) => set({ tone: event.target.value })} disabled={!canEdit}>
              {TONES.map((tone) => (
                <MenuItem key={tone} value={tone}>
                  {tone}
                </MenuItem>
              ))}
            </TextField>
            <TextField label="Your name in briefings" value={profile.pm_display_name || ""} onChange={(event) => set({ pm_display_name: event.target.value })} disabled={!canEdit} placeholder="Priya" />
          </Box>
          <TextField label="Workspace name" value={name} onChange={(event) => setName(event.target.value)} disabled={!canEdit} helperText="Shown in the switcher. Usually your team or product." />
          {error ? <Banner severity="error">{error}</Banner> : null}
        </Box>
      </StepFrame>
    </Box>
  );
}

function ConnectionsStep({ canEdit, onNext, onBack }: { canEdit: boolean; onNext: () => void; onBack: () => void }) {
  const [data, setData] = useState<ConnectionsResponse | null>(null);
  const [open, setOpen] = useState<string>("llm");
  const load = useCallback(() => platform.connections().then(setData).catch(() => null), []);
  useEffect(() => {
    void load();
  }, [load]);
  const providers = useMemo(() => (data?.providers || []).filter((p) => ESSENTIAL.includes(p.id)).sort((a, b) => ESSENTIAL.indexOf(a.id) - ESSENTIAL.indexOf(b.id)), [data]);
  const ready = (data?.providers || []).filter((p) => p.connections.some((c) => c.connected && c.status !== "error")).length;

  return (
    <StepFrame
      title="Connect your tools"
      subtitle="Start with an AI model and Jira; most pipelines need one or both. Keys are encrypted for this workspace only. You can add HeyGen, Cartesia, email and Git hosts later from Connections."
      footer={
        <>
          <PillButton variant="gray" onClick={onBack} startIcon={<ArrowBackRoundedIcon />}>
            Back
          </PillButton>
          <PillButton onClick={onNext} endIcon={<ArrowForwardRoundedIcon />}>
            {ready ? "Continue" : "Skip for now"}
          </PillButton>
        </>
      }
    >
      {!data ? (
        <LoadingBlock rows={4} height={64} />
      ) : (
        <Box sx={{ display: "grid", gap: 1.25, maxWidth: 720 }}>
          {providers.map((provider) => {
            const view = provider.connections[0];
            const expanded = open === provider.id;
            return (
              <Box key={provider.id} sx={{ borderRadius: "16px", border: `1px solid ${expanded ? apple.hairlineHover : apple.hairline}`, bgcolor: apple.raised, overflow: "hidden", transition: `border-color 0.2s ${apple.smooth}` }}>
                <ButtonBase onClick={() => setOpen(expanded ? "" : provider.id)} aria-expanded={expanded} sx={{ width: "100%", display: "flex", alignItems: "center", gap: 1.5, p: 2, textAlign: "left" }}>
                  <ProviderMark id={provider.id} name={provider.name} />
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Typography sx={{ fontSize: 15, fontWeight: 650 }}>
                      {provider.name}
                      {provider.id === "llm" ? <Box component="span" sx={{ ml: 1, fontSize: 11, fontWeight: 700, color: accent.system.main, textTransform: "uppercase", letterSpacing: "0.06em" }}>Recommended</Box> : null}
                    </Typography>
                    <Typography sx={{ fontSize: 13, color: apple.muted }}>{provider.description}</Typography>
                  </Box>
                  <ToneChip tone={connectionTone(view)} size="sm" />
                </ButtonBase>
                <Collapse in={expanded} unmountOnExit>
                  <Box sx={{ px: 2, pb: 2.5, pt: 0.5 }}>
                    {provider.custom_ui === "llm" ? (
                      <LlmForm key={view?.updated_at || "new"} view={view} canEdit={canEdit} onSaved={() => void load()} />
                    ) : (
                      <ProviderForm key={view?.updated_at || "new"} provider={provider} view={view} canEdit={canEdit} compact onSaved={() => void load()} />
                    )}
                    {provider.id === "cliq" ? <Typography sx={{ mt: 1.5, fontSize: 12.5, color: apple.muted }}>After saving, finish linking your Zoho account from Connections.</Typography> : null}
                  </Box>
                </Collapse>
              </Box>
            );
          })}
        </Box>
      )}
    </StepFrame>
  );
}

function RepositoryStep({ canEdit, onNext, onBack }: { canEdit: boolean; onNext: () => void; onBack: () => void }) {
  const [data, setData] = useState<RepositoriesResponse | null>(null);
  const load = useCallback(() => platform.repositories().then(setData).catch(() => null), []);
  useEffect(() => {
    void load();
  }, [load]);
  const has = Boolean(data?.repositories.length);
  return (
    <StepFrame
      title="Add your repository"
      subtitle="The server keeps a read-only mirror and checks out your product branch. Release notes, codebase Q&A and feature discovery all read from it."
      footer={
        <>
          <PillButton variant="gray" onClick={onBack} startIcon={<ArrowBackRoundedIcon />}>
            Back
          </PillButton>
          <PillButton onClick={onNext} endIcon={<ArrowForwardRoundedIcon />} variant={has ? "filled" : "gray"}>
            {has ? "Continue" : "Skip for now"}
          </PillButton>
        </>
      }
    >
      {!data ? (
        <LoadingBlock rows={2} height={64} />
      ) : (
        <Box sx={{ maxWidth: 680, display: "grid", gap: 2 }}>
          {data.repositories.map((repo) => (
            <Box key={repo.id} sx={{ display: "flex", alignItems: "center", gap: 1.5, p: 2, borderRadius: "14px", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised }}>
              <ProviderMark id={repo.provider} name={repo.provider} size={36} />
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Typography sx={{ fontSize: 14.5, fontWeight: 650 }}>{repo.name}</Typography>
                <Typography sx={{ fontSize: 12.5, color: apple.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {repo.product_branch || "default branch"} · {repo.sync_run && ["queued", "running"].includes(repo.sync_run.status) ? "syncing…" : repo.last_fetch_status === "ok" ? "fetched" : repo.last_fetch_status}
                </Typography>
              </Box>
              <CheckRoundedIcon sx={{ color: pmm.green }} />
            </Box>
          ))}
          {canEdit && !has ? <RepositoryForm options={data} onSaved={() => void load()} submitLabel="Add repository" /> : null}
          {!canEdit && !has ? <Banner severity="info">Ask a workspace admin to add a repository.</Banner> : null}
        </Box>
      )}
    </StepFrame>
  );
}

function PeopleStep({ canEdit, onNext, onBack }: { canEdit: boolean; onNext: () => void; onBack: () => void }) {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [draft, setDraft] = useState({ name: "", role: "dev", email: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => platform.people().then((data) => setPeople(data.people.filter((p) => p.active))).catch(() => setPeople([])), []);
  useEffect(() => {
    void load();
  }, [load]);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    if (!draft.name.trim()) return;
    setBusy(true);
    setError("");
    try {
      await platform.addPerson({ name: draft.name.trim(), role: draft.role, email: draft.email.trim() });
      setDraft({ name: "", role: draft.role, email: "" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <StepFrame
      title="Who's on the team?"
      subtitle="Briefings group work by person and release follow-ups know who to ask. Add Jira account IDs and chat handles later in Settings → People."
      footer={
        <>
          <PillButton variant="gray" onClick={onBack} startIcon={<ArrowBackRoundedIcon />}>
            Back
          </PillButton>
          <PillButton onClick={onNext} endIcon={<ArrowForwardRoundedIcon />}>
            {people?.length ? "Continue" : "Skip for now"}
          </PillButton>
        </>
      }
    >
      <Box sx={{ maxWidth: 680, display: "grid", gap: 2 }}>
        {canEdit ? (
          <Box component="form" onSubmit={add} sx={{ display: "grid", gap: 1.25, gridTemplateColumns: { xs: "1fr", sm: "1.3fr 1fr 1.3fr auto" }, alignItems: "start" }}>
            <TextField size="small" label="Name" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
            <TextField size="small" select label="Role" value={draft.role} onChange={(event) => setDraft({ ...draft, role: event.target.value })}>
              {Object.entries(PERSON_ROLES).map(([id, label]) => (
                <MenuItem key={id} value={id}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <TextField size="small" label="Email (optional)" value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} />
            <PillButton type="submit" disabled={busy || !draft.name.trim()} sx={{ height: 40 }}>
              Add
            </PillButton>
          </Box>
        ) : null}
        {error ? <Banner severity="error">{error}</Banner> : null}
        {people === null ? (
          <LoadingBlock rows={3} height={44} />
        ) : people.length ? (
          <Box sx={{ border: `1px solid ${apple.hairline}`, borderRadius: "14px", bgcolor: apple.raised, overflow: "hidden" }}>
            {people.map((person, index) => (
              <Box key={person.id} sx={{ display: "flex", alignItems: "center", gap: 1.5, px: 2, py: 1.25, borderTop: index ? `1px solid ${apple.hairline}` : "none" }}>
                <WorkspaceMark name={person.name} slug={person.email || person.name} size={28} />
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{person.name}</Typography>
                  <Typography sx={{ fontSize: 12, color: apple.muted }}>
                    {PERSON_ROLES[person.role] || person.role}
                    {person.email ? ` · ${person.email}` : ""}
                  </Typography>
                </Box>
                {canEdit ? (
                  <IconButton size="small" aria-label={`Remove ${person.name}`} onClick={() => void platform.removePerson(person.id).then(load)}>
                    <DeleteOutlineRoundedIcon fontSize="small" />
                  </IconButton>
                ) : null}
              </Box>
            ))}
          </Box>
        ) : (
          <Typography sx={{ fontSize: 14, color: apple.muted }}>No one yet.</Typography>
        )}
      </Box>
    </StepFrame>
  );
}

function DoneStep({ onBack, onFinish }: { onBack: () => void; onFinish: (run?: boolean) => void }) {
  const { pipelines, reloadPipelines } = usePlatform();
  useEffect(() => {
    void reloadPipelines();
  }, [reloadPipelines]);
  const list = pipelines?.pipelines || [];
  const ready = list.filter((p) => p.status === "ready" || p.status === "running" || p.status === "queued");
  const waiting = list.filter((p) => p.status === "needs_connection");
  const daily = list.find((p) => p.id === "daily-sync");
  return (
    <StepFrame
      title={ready.length ? `${ready.length} pipelines are ready` : "Your workspace is set up"}
      subtitle={waiting.length ? `${waiting.length} more unlock as you add their connections. Everything here is also on the Pipelines page.` : "Everything is connected. Run your first sync to fill the workspace."}
      footer={
        <>
          <PillButton variant="gray" onClick={onBack} startIcon={<ArrowBackRoundedIcon />}>
            Back
          </PillButton>
          {daily?.status === "ready" ? (
            <PillButton onClick={() => onFinish(true)} startIcon={<PlayArrowRoundedIcon />}>
              Run first sync and open Home
            </PillButton>
          ) : null}
          <PillButton variant={daily?.status === "ready" ? "text" : "filled"} onClick={() => onFinish(false)} endIcon={<ArrowForwardRoundedIcon />}>
            Go to Home
          </PillButton>
        </>
      }
    >
      {!pipelines ? (
        <LoadingBlock rows={3} height={56} />
      ) : (
        <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, maxWidth: 900 }}>
          {[...ready, ...waiting].slice(0, 12).map((pipeline) => (
            <Box key={pipeline.id} sx={{ display: "flex", alignItems: "center", gap: 1.5, p: 1.5, borderRadius: "12px", border: `1px solid ${apple.hairline}`, bgcolor: apple.raised, opacity: pipeline.status === "needs_connection" ? 0.7 : 1 }}>
              <PipelineIcon icon={pipeline.icon} category={pipeline.category} size={32} />
              <Typography sx={{ fontSize: 14, fontWeight: 600, flex: 1, minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{pipeline.name}</Typography>
              <ToneChip tone={pipelineTone(pipeline)} size="sm" />
            </Box>
          ))}
        </Box>
      )}
    </StepFrame>
  );
}

function Onboarding() {
  const router = useRouter();
  const params = useSearchParams();
  const { me, can } = useWorkspace();
  const { runPipeline } = usePlatform();
  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [step, setStep] = useState<StepId>("profile");
  const [creating, setCreating] = useState(params.get("new") === "1" && !clerkEnabled);
  const canEdit = can("admin");

  const load = useCallback(() => platform.workspace().then(setDetail).catch(() => null), []);
  useEffect(() => {
    void load();
  }, [load, step]);

  const index = STEPS.findIndex((s) => s.id === step);
  const go = (offset: number) => setStep(STEPS[Math.max(0, Math.min(STEPS.length - 1, index + offset))].id);
  const doneIds = new Set<string>((detail?.onboarding.steps || []).filter((s) => s.done).map((s) => s.id));

  async function finish(run?: boolean) {
    if (canEdit) await platform.dismissOnboarding().catch(() => null);
    if (run) await runPipeline("daily-sync");
    router.push("/");
  }

  return (
    <Box sx={{ minHeight: "100vh", display: "grid", gridTemplateColumns: { xs: "1fr", md: "300px minmax(0,1fr)" }, bgcolor: apple.page }}>
      <Box
        component="aside"
        sx={{
          display: { xs: "none", md: "flex" },
          flexDirection: "column",
          gap: 3,
          p: 3,
          position: "sticky",
          top: 0,
          height: "100vh",
          borderRight: `1px solid ${apple.hairline}`,
          background: `radial-gradient(140% 60% at 0% 0%, ${accent.system.fill} 0%, transparent 60%), radial-gradient(120% 50% at 100% 100%, ${accent.marketing.fill} 0%, transparent 60%), ${apple.nav}`,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.25 }}>
          <WorkspaceMark name={detail?.name || me?.workspace.name || "Workspace"} slug={me?.workspace.slug || ""} size={36} />
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: 15, fontWeight: 650, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{detail?.name || me?.workspace.name || "Workspace"}</Typography>
            <Typography sx={{ fontSize: 12, color: apple.muted }}>Workspace setup</Typography>
          </Box>
        </Box>
        <Box component="ol" sx={{ listStyle: "none", m: 0, p: 0, display: "grid", gap: 0.5 }}>
          {STEPS.map((item, i) => {
            const current = item.id === step;
            const done = doneIds.has(item.id);
            return (
              <Box component="li" key={item.id}>
                <ButtonBase onClick={() => setStep(item.id)} aria-current={current ? "step" : undefined} sx={{ width: "100%", display: "flex", alignItems: "flex-start", gap: 1.5, p: 1.25, borderRadius: "12px", textAlign: "left", bgcolor: current ? apple.raised : "transparent", boxShadow: current ? `0 0 0 1px ${apple.hairline}` : "none", "&:hover": { bgcolor: current ? apple.raised : apple.selFill } }}>
                  <Box sx={{ width: 24, height: 24, borderRadius: "50%", display: "grid", placeItems: "center", flexShrink: 0, fontSize: 12, fontWeight: 700, bgcolor: done ? pmm.green : current ? apple.ink : apple.hoverFill, color: done || current ? apple.onInk : apple.muted, border: done || current ? "none" : `1px solid ${apple.hairline}` }}>
                    {done ? <CheckRoundedIcon sx={{ fontSize: 15, color: "#fff" }} /> : i + 1}
                  </Box>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontSize: 14, fontWeight: current ? 650 : 550, color: current ? apple.text : apple.muted }}>{item.title}</Typography>
                    <Typography sx={{ fontSize: 12, color: apple.muted }}>{item.blurb}</Typography>
                  </Box>
                </ButtonBase>
              </Box>
            );
          })}
        </Box>
        <Box sx={{ mt: "auto" }}>
          <PillButton variant="text" onClick={() => router.push("/")} sx={{ color: apple.muted }}>
            Exit setup
          </PillButton>
        </Box>
      </Box>
      <Box sx={{ minWidth: 0, px: { xs: 2.5, md: 6, xl: 10 }, py: { xs: 3, md: 7 }, maxWidth: 1040 }}>
        <Box sx={{ display: { xs: "flex", md: "none" }, alignItems: "center", gap: 1, mb: 3 }}>
          {STEPS.map((item, i) => (
            <Box key={item.id} sx={{ flex: 1, height: 4, borderRadius: 2, bgcolor: i <= index ? apple.ink : apple.hoverFill }} />
          ))}
        </Box>
        {!canEdit && me ? <Banner severity="info">You can look around, but only workspace admins can change settings.</Banner> : null}
        {!detail ? (
          <LoadingBlock rows={4} height={56} />
        ) : step === "profile" ? (
          <ProfileStep key={detail.id} detail={detail} canEdit={canEdit} onNext={() => go(1)} />
        ) : step === "connections" ? (
          <ConnectionsStep canEdit={canEdit} onNext={() => go(1)} onBack={() => go(-1)} />
        ) : step === "repository" ? (
          <RepositoryStep canEdit={canEdit} onNext={() => go(1)} onBack={() => go(-1)} />
        ) : step === "people" ? (
          <PeopleStep canEdit={canEdit} onNext={() => go(1)} onBack={() => go(-1)} />
        ) : (
          <DoneStep onBack={() => go(-1)} onFinish={(run) => void finish(run)} />
        )}
      </Box>
      <CreateWorkspaceDialog open={creating} onClose={() => setCreating(false)} />
    </Box>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={null}>
      <Onboarding />
    </Suspense>
  );
}
