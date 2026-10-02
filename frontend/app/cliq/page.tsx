"use client";

import { Box, Button, Skeleton, Tabs, Tab, TextField, Typography, Snackbar } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { api, peekGet, type CliqBriefing, type CliqDigestItem } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { useCopilot } from "@/app/copilot/context";
import { Banner, EmptyState, FrostCard, PageBody, PageHeader, PagedList, PillButton, StatusChip } from "@/app/ui";

const views = [
  { id: "unanswered", label: "Needs a response", empty: "No unanswered messages in this window." },
  { id: "promises", label: "Commitments", empty: "No open commitments in this window." },
  { id: "follow_up_tomorrow", label: "Follow-ups", empty: "No upcoming follow-ups in this window." },
  { id: "conversations", label: "Conversations", empty: "No conversations in this window." },
] as const;
type View = typeof views[number]["id"];

export default function CliqPage() {
  const { tick } = useRefresh();
  const { open } = useCopilot();
  const [digest, setDigest] = useState<CliqBriefing | null>(() => peekGet<CliqBriefing>("/api/cliq/digest") ?? null);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("unanswered");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [pending, setPending] = useState(false);
  const [hidden, setHidden] = useState<{ key: string; title: string } | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    api.cliqDigest().then(data => { if (active) setDigest(data); }).catch(e => { if (active) setError(String(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [tick, attempt]);

  async function hide(item: CliqDigestItem) {
    setPending(true); setError("");
    try {
      const result = await api.hideCard({ card_key: item.card_key, title: item.title || item.chat || item.body || "Conversation" });
      setHidden({ key: result.card_key, title: item.title || item.chat || "Conversation" });
      setDigest(await api.cliqDigest());
    } catch (e) { setError(String(e)); } finally { setPending(false); }
  }
  async function undo() {
    if (!hidden) return;
    setPending(true);
    try { await api.unhideCard(hidden.key); setHidden(null); setDigest(await api.cliqDigest()); }
    catch (e) { setError(String(e)); } finally { setPending(false); }
  }

  const all = digest?.[view] || [];
  const items = useMemo(() => all.filter(item => [item.title, item.chat, item.from, item.body, item.summary, item.action, ...(item.people || [])].join(" ").toLowerCase().includes(query.trim().toLowerCase())), [all, query]);
  return <PageBody>
    <PageHeader title="Cliq" subtitle={digest?.window_label || "Conversations and commitments that need your attention."} />
    {error && <Banner severity="error">{error} <PillButton variant="text" disabled={loading} onClick={() => setAttempt(n => n + 1)}>Try again</PillButton></Banner>}
    {digest?.ingest_error && <Banner severity="warning">{digest.ingest_error} <a href="/settings/integrations">Check connection</a></Banner>}
    {digest?.stale && !digest.ingest_error && <Banner severity="info">Showing stored conversations. Refresh sources to fetch new messages.</Banner>}
    <Tabs value={view} onChange={(_, value) => setView(value)} variant="scrollable" scrollButtons="auto" aria-label="Conversation categories" sx={{ mb: 2 }}>
      {views.map(item => <Tab key={item.id} value={item.id} label={`${item.label} (${digest?.[item.id]?.length || 0})`} />)}
    </Tabs>
    <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", alignItems: "center", mb: 3 }}>
      <TextField label="Search conversations or people" value={query} onChange={e => setQuery(e.target.value)} sx={{ flex: 1, minWidth: 200 }} />
      {query && <PillButton variant="text" onClick={() => setQuery("")}>Clear search</PillButton>}
      <PillButton variant="text" disabled={loading} onClick={() => setAttempt(n => n + 1)}>{loading ? "Loading…" : "Reload digest"}</PillButton>
    </Box>
    {loading && !digest ? <Box role="status" aria-label="Loading conversations">{[0,1,2].map(n => <Skeleton key={n} height={150} />)}</Box> : !digest && error ? null : <>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }} aria-live="polite">{items.length} {items.length === 1 ? "conversation" : "conversations"}{query ? ` matching “${query}”` : ""}</Typography>
      <PagedList items={items} resetKey={`${view}-${query}`} getKey={(item, index) => item.card_key || `${item.title}-${index}`} empty={<EmptyState>{query ? "No conversations match your search." : views.find(item => item.id === view)?.empty}</EmptyState>} renderItem={item => <FrostCard>
        <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, alignItems: "flex-start" }}>
          <Box sx={{ minWidth: 0 }}><Typography variant="h6" sx={{ overflowWrap: "anywhere" }}>{item.title || item.chat || item.from || "Conversation"}</Typography>{item.chat && item.chat !== item.title && <Typography variant="caption" color="text.secondary">{item.chat}</Typography>}</Box>
          <PillButton variant="text" disabled={pending} onClick={() => hide(item)}>Hide</PillButton>
        </Box>
        <Typography sx={{ mt: 1.5, fontSize: 15, overflowWrap: "anywhere", whiteSpace: "pre-wrap" }}>{item.body || item.summary}</Typography>
        {item.action && <Box sx={{ mt: 2, p: 1.5, bgcolor: "action.hover", borderRadius: 2 }}><Typography variant="caption" color="text.secondary">Next step</Typography><Typography variant="body2">{item.action}</Typography></Box>}
        {item.why && <Box component="details" sx={{ mt: 1.5 }}><Typography component="summary" sx={{ cursor: "pointer", fontSize: 13, color: "text.secondary" }}>Why this matters</Typography><Typography variant="body2" sx={{ mt: 1 }}>{item.why}</Typography></Box>}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", mt: 2 }}>{(item.people || []).map(person => <StatusChip key={person} label={person} />)}<PillButton variant="text" sx={{ ml: "auto" }} onClick={() => open({ notes: [item.title, item.chat, item.body || item.summary, item.action].filter(Boolean).join("\n"), prompt: "Help me prepare a response and next steps for this conversation." })}>Prepare response</PillButton></Box>
      </FrostCard>} />
    </>}
    <Snackbar open={Boolean(hidden)} onClose={() => setHidden(null)} message={`${hidden?.title || "Conversation"} hidden`} action={<Button color="inherit" disabled={pending} onClick={undo}>Undo</Button>} />
  </PageBody>;
}
