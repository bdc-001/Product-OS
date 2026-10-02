"use client";

import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import Box from "@mui/material/Box";
import Link from "@mui/material/Link";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AdminNotice, SaveFooter, SettingsCard, SettingsPage, useProfileDraft } from "@/app/settings/shared";
import { Banner, LoadingBlock, PillButton } from "@/app/ui";
import { clockLabel } from "@/app/ui/platform";
import { apple } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { platform, type BrandAssets, type BrandStem } from "@/lib/platform";

const PRODUCT_KEYS = ["product_name", "company_name", "product_description", "website", "industries", "product_modules"] as const;
const VOICE_KEYS = ["tone", "brand_rules", "support_email", "newsletter_sender"] as const;
const JIRA_KEYS = ["project_keywords", "jira_scope_rules"] as const;
const MARKET_KEYS = ["competitor_focus", "competitor_pack"] as const;
const TIMING_KEYS = ["standup_hour"] as const;
const BUILD_KEYS = ["data_branch", "prototype_kit"] as const;

const TONES = ["Clear and direct", "Warm and friendly", "Technical and precise", "Bold and energetic"];
const HOURS = Array.from({ length: 24 }, (_, h) => h);

function useCanEdit() {
  return useWorkspace().can("admin");
}

function ProductCard() {
  const canEdit = useCanEdit();
  const form = useProfileDraft(PRODUCT_KEYS);
  if (!form.detail) return <LoadingBlock rows={3} height={56} />;
  const d = form.draft;
  return (
    <SettingsCard
      title="Product"
      description="Every prompt is grounded in this. Release notes, PRDs, campaigns and briefings name the product and its modules from here."
      footer={<SaveFooter canEdit={canEdit} dirty={form.dirty} busy={form.busy} status={form.status} onSave={() => void form.save("Product saved.")} onReset={form.reset} />}
    >
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
        <TextField size="small" label="Product name" value={d.product_name || ""} onChange={(e) => form.set({ product_name: e.target.value })} disabled={!canEdit} />
        <TextField size="small" label="Company" value={d.company_name || ""} onChange={(e) => form.set({ company_name: e.target.value })} disabled={!canEdit} />
        <TextField size="small" label="What it does" value={d.product_description || ""} onChange={(e) => form.set({ product_description: e.target.value })} disabled={!canEdit} multiline minRows={3} sx={{ gridColumn: "1 / -1" }} helperText="The problem, who has it, and how the product solves it." />
        <TextField size="small" label="Website" value={d.website || ""} onChange={(e) => form.set({ website: e.target.value })} disabled={!canEdit} placeholder="https://" />
        <TextField size="small" label="Industries" value={d.industries || ""} onChange={(e) => form.set({ industries: e.target.value })} disabled={!canEdit} placeholder="SaaS, fintech, retail" />
        <TextField size="small" label="Modules" value={d.product_modules || ""} onChange={(e) => form.set({ product_modules: e.target.value })} disabled={!canEdit} sx={{ gridColumn: "1 / -1" }} helperText="Comma-separated, main module first. Used to label features, notes and the roadmap." />
      </Box>
    </SettingsCard>
  );
}

function VoiceCard() {
  const canEdit = useCanEdit();
  const form = useProfileDraft(VOICE_KEYS);
  if (!form.detail) return null;
  const d = form.draft;
  const tone = d.tone || "";
  return (
    <SettingsCard
      title="Voice"
      description="How customer-facing writing sounds and who it comes from."
      footer={<SaveFooter canEdit={canEdit} dirty={form.dirty} busy={form.busy} status={form.status} onSave={() => void form.save("Voice saved.")} onReset={form.reset} />}
    >
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
        <TextField select size="small" label="Tone" value={tone} onChange={(e) => form.set({ tone: e.target.value })} disabled={!canEdit}>
          <MenuItem value="">Default</MenuItem>
          {[...TONES, ...(tone && !TONES.includes(tone) ? [tone] : [])].map((t) => (
            <MenuItem key={t} value={t}>
              {t}
            </MenuItem>
          ))}
        </TextField>
        <TextField size="small" label="Newsletter signed by" value={d.newsletter_sender || ""} onChange={(e) => form.set({ newsletter_sender: e.target.value })} disabled={!canEdit} helperText="Defaults to the briefing owner's first name." />
        <TextField size="small" label="Support email" value={d.support_email || ""} onChange={(e) => form.set({ support_email: e.target.value })} disabled={!canEdit} sx={{ gridColumn: "1 / -1" }} />
        <TextField size="small" label="Brand rules" value={d.brand_rules || ""} onChange={(e) => form.set({ brand_rules: e.target.value })} disabled={!canEdit} multiline minRows={3} sx={{ gridColumn: "1 / -1" }} helperText="Naming and wording rules every generator follows, e.g. 'Always write Acme Analytics in full; never say AA.'" />
      </Box>
    </SettingsCard>
  );
}

const BRAND_LABELS: Record<BrandStem, { title: string; hint: string; dark?: boolean }> = {
  "logo-light": { title: "Logo for light backgrounds", hint: "SVG or PNG. Used on one-pagers and light slides." },
  "logo-dark": { title: "Logo for dark backgrounds", hint: "SVG or PNG. Used on dark slides and film end cards.", dark: true },
  wordmark: { title: "PDF wordmark", hint: "PNG or JPEG. Printed in release-note PDF headers." },
};

function BrandCard() {
  const canEdit = useCanEdit();
  const [assets, setAssets] = useState<BrandAssets | null>(null);
  const [busy, setBusy] = useState<BrandStem | "">("");
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const inputs = useRef<Partial<Record<BrandStem, HTMLInputElement | null>>>({});

  const load = useCallback(() => platform.brand().then(setAssets).catch((err) => setError(err instanceof Error ? err.message : String(err))), []);
  useEffect(() => {
    void load();
  }, [load]);

  async function upload(stem: BrandStem, file: File | undefined) {
    if (!file) return;
    setBusy(stem);
    setError("");
    try {
      setAssets(await platform.uploadBrand(stem, file));
      setVersion((v) => v + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
      const input = inputs.current[stem];
      if (input) input.value = "";
    }
  }

  async function remove(stem: BrandStem) {
    setBusy(stem);
    setError("");
    try {
      setAssets(await platform.removeBrand(stem));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  }

  return (
    <SettingsCard title="Brand kit" description="Without uploads, artifacts use a text wordmark of your company name.">
      {error ? <Banner severity="error">{error}</Banner> : null}
      {!assets ? (
        <LoadingBlock rows={1} height={120} />
      ) : (
        <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, minmax(0,1fr))" } }}>
          {(Object.keys(BRAND_LABELS) as BrandStem[]).map((stem) => {
            const info = BRAND_LABELS[stem];
            const asset = assets.assets[stem];
            return (
              <Box key={stem} sx={{ display: "grid", gap: 1, alignContent: "start" }}>
                <Box sx={{ height: 96, borderRadius: "12px", border: `1px ${asset.uploaded ? "solid" : "dashed"} ${apple.hairline}`, bgcolor: info.dark ? "#111" : "#fff", display: "grid", placeItems: "center", p: 1.5, overflow: "hidden" }}>
                  {asset.uploaded ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={`/api/workspace/brand/${stem}?v=${version}-${asset.updated_at}`} alt={info.title} style={{ maxWidth: "100%", maxHeight: 64, objectFit: "contain" }} />
                  ) : (
                    <Typography sx={{ fontSize: 12, color: info.dark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.45)" }}>Not uploaded</Typography>
                  )}
                </Box>
                <Typography sx={{ fontSize: 13.5, fontWeight: 600 }}>{info.title}</Typography>
                <Typography sx={{ fontSize: 12, color: apple.muted, lineHeight: 1.45 }}>{info.hint}</Typography>
                {canEdit ? (
                  <Box sx={{ display: "flex", gap: 1 }}>
                    <input ref={(el) => { inputs.current[stem] = el; }} type="file" hidden accept={asset.accepts.join(",")} onChange={(e) => void upload(stem, e.target.files?.[0])} />
                    <PillButton size="small" variant="gray" startIcon={<CloudUploadOutlinedIcon />} disabled={busy === stem} onClick={() => inputs.current[stem]?.click()}>
                      {busy === stem ? "Uploading…" : asset.uploaded ? "Replace" : "Upload"}
                    </PillButton>
                    {asset.uploaded ? (
                      <PillButton size="small" variant="text" disabled={busy === stem} onClick={() => void remove(stem)} sx={{ color: apple.muted }}>
                        Remove
                      </PillButton>
                    ) : null}
                  </Box>
                ) : null}
              </Box>
            );
          })}
        </Box>
      )}
    </SettingsCard>
  );
}

function JiraScopeCard() {
  const canEdit = useCanEdit();
  const form = useProfileDraft(JIRA_KEYS);
  if (!form.detail) return null;
  const d = form.draft;
  return (
    <SettingsCard
      title="Relevance"
      description={
        <>
          How briefings decide a ticket or chat is about this product. Which Jira projects sync is set on the{" "}
          <Link component={NextLink} href="/settings/connections?provider=jira">
            Jira connection
          </Link>
          .
        </>
      }
      footer={<SaveFooter canEdit={canEdit} dirty={form.dirty} busy={form.busy} status={form.status} onSave={() => void form.save("Saved. The next sync uses it.")} onReset={form.reset} />}
    >
      <Box sx={{ display: "grid", gap: 2 }}>
        <TextField size="small" label="Product keywords" value={d.project_keywords || ""} onChange={(e) => form.set({ project_keywords: e.target.value })} disabled={!canEdit} helperText="Comma-separated words that mark a ticket or chat as relevant." />
        <TextField size="small" label="Scope rules" value={d.jira_scope_rules || ""} onChange={(e) => form.set({ jira_scope_rules: e.target.value })} disabled={!canEdit} multiline minRows={3} helperText="Plain-language rules for edge cases, e.g. 'Support tickets count only when a developer from the team is assigned.'" />
      </Box>
    </SettingsCard>
  );
}

function MarketCard() {
  const canEdit = useCanEdit();
  const form = useProfileDraft(MARKET_KEYS);
  if (!form.detail) return null;
  const d = form.draft;
  const pack = d.competitor_pack || "";
  return (
    <SettingsCard
      title="Market watch"
      description="What the competitor and market watch pipeline looks for."
      footer={<SaveFooter canEdit={canEdit} dirty={form.dirty} busy={form.busy} status={form.status} onSave={() => void form.save("Market watch saved.")} onReset={form.reset} />}
    >
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "2fr 1fr" } }}>
        <TextField size="small" label="Focus" value={d.competitor_focus || ""} onChange={(e) => form.set({ competitor_focus: e.target.value })} disabled={!canEdit} multiline minRows={2} helperText="The category you compete in and what matters to buyers." />
        <TextField select size="small" label="Starting watch list" value={pack} onChange={(e) => form.set({ competitor_pack: e.target.value })} disabled={!canEdit} helperText="Add your own competitors from the Competitors page.">
          <MenuItem value="">Standard</MenuItem>
          {pack ? <MenuItem value={pack}>{pack[0].toUpperCase() + pack.slice(1)} pack</MenuItem> : null}
        </TextField>
      </Box>
    </SettingsCard>
  );
}

function TimingCard() {
  const canEdit = useCanEdit();
  const form = useProfileDraft(TIMING_KEYS);
  if (!form.detail) return null;
  const d = form.draft;
  return (
    <SettingsCard
      title="Workday"
      description={`Briefings cover work since this time on the previous working day (or today, after it). Times are in ${form.detail.timezone}; when pipelines run is set on each pipeline.`}
      footer={<SaveFooter canEdit={canEdit} dirty={form.dirty} busy={form.busy} status={form.status} onSave={() => void form.save("Workday saved.")} onReset={form.reset} />}
    >
      <Box sx={{ maxWidth: 260 }}>
        <TextField select size="small" fullWidth label="Workday starts at" value={d.standup_hour ?? 9} onChange={(e) => form.set({ standup_hour: Number(e.target.value) })} disabled={!canEdit}>
          {HOURS.map((h) => (
            <MenuItem key={h} value={h}>
              {clockLabel(h, 0)}
            </MenuItem>
          ))}
        </TextField>
      </Box>
    </SettingsCard>
  );
}

function BuildCard() {
  const canEdit = useCanEdit();
  const form = useProfileDraft(BUILD_KEYS);
  if (!form.detail) return null;
  const d = form.draft;
  const kit = d.prototype_kit || "starter";
  return (
    <SettingsCard
      title="Code and prototypes"
      description="Which branch Copilot and codebase answers read by default, and which UI kit new prototypes start from."
      footer={<SaveFooter canEdit={canEdit} dirty={form.dirty} busy={form.busy} status={form.status} onSave={() => void form.save("Saved.")} onReset={form.reset} />}
    >
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
        <TextField size="small" label="Default data branch" value={d.data_branch || ""} onChange={(e) => form.set({ data_branch: e.target.value })} disabled={!canEdit} helperText="Leave empty to use the most recently indexed branch." />
        <TextField select size="small" label="Prototype kit" value={kit} onChange={(e) => form.set({ prototype_kit: e.target.value })} disabled={!canEdit}>
          <MenuItem value="starter">Starter (neutral UI kit)</MenuItem>
          {kit !== "starter" ? <MenuItem value={kit}>{kit[0].toUpperCase() + kit.slice(1)} kit</MenuItem> : null}
        </TextField>
      </Box>
    </SettingsCard>
  );
}

export default function ProfileSettings() {
  return (
    <SettingsPage subtitle="What every pipeline knows about your product. Changes apply to the next run; nothing already generated is rewritten.">
      <AdminNotice />
      <ProductCard />
      <VoiceCard />
      <BrandCard />
      <JiraScopeCard />
      <MarketCard />
      <TimingCard />
      <BuildCard />
    </SettingsPage>
  );
}
