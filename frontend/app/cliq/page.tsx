"use client";

import Box from "@mui/material/Box";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@/app/ui/stack";
import Typography from "@mui/material/Typography";
import { useEffect, useState } from "react";
import { api, peekGet, type CliqBriefing, type CliqDigestItem } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, EmptyState, FrostCard, PageBody, PageHeader, PagedList, RemoveButton, Section, StatusChip } from "@/app/ui";
import { apple } from "@/app/theme";

function Card({ item, onHide }: { item: CliqDigestItem; onHide: (item: CliqDigestItem) => void }) {
  const people = item.people || [];
  return (
    <FrostCard>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
        <Typography variant="h3">{item.title || item.chat || item.from || "Cliq"}</Typography>
        <RemoveButton onClick={() => onHide(item)} title="Remove from my view" />
      </Stack>
      {item.chat ? (
        <Typography sx={{ mt: 0.5, fontSize: 13, color: apple.muted }}>{item.chat}</Typography>
      ) : null}
      <Typography sx={{ mt: 1, fontSize: 15 }}>{item.body || item.summary}</Typography>
      {item.action ? (
        <Typography sx={{ mt: 0.75, fontWeight: 600, fontSize: 15 }}>{item.action}</Typography>
      ) : null}
      {item.why ? (
        <Typography sx={{ mt: 0.75, fontSize: 15, color: apple.muted }}>{item.why}</Typography>
      ) : null}
      {people.length ? (
        <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mt: 1 }}>
          {people.map((person) => (
            <StatusChip key={person} label={person} />
          ))}
        </Stack>
      ) : null}
    </FrostCard>
  );
}

function DigestSection({
  title,
  items,
  empty,
  onHide,
}: {
  title: string;
  items: CliqDigestItem[];
  empty: string;
  onHide: (item: CliqDigestItem) => void;
}) {
  return (
    <Section title={title} count={items.length}>
      <PagedList
        items={items}
        getKey={(item, index) => item.card_key || `${item.title}-${index}`}
        empty={<EmptyState>{empty}</EmptyState>}
        renderItem={(item) => <Card item={item} onHide={onHide} />}
      />
    </Section>
  );
}

export default function CliqPage() {
  const [digest, setDigest] = useState<CliqBriefing | null>(() => peekGet<CliqBriefing>("/api/cliq/digest") ?? null);
  const [error, setError] = useState("");
  const { tick } = useRefresh();

  async function load() {
    const data = await api.cliqDigest();
    setDigest(data);
  }

  useEffect(() => {
    load().catch((err) => setError(String(err)));
  }, [tick]);

  async function hide(item: CliqDigestItem) {
    await api.hideCard({ card_key: item.card_key, title: item.title || item.chat || item.body || "Cliq" });
    await load();
  }

  const loading = !digest && !error;

  return (
    <PageBody>
      <PageHeader title="Cliq" subtitle={digest?.window_label || "Summary of chats you were in, then the loops that still need you."} />
      {error ? <Banner severity="error">{error}</Banner> : null}
      {digest?.ingest_error ? <Banner severity="error">{digest.ingest_error}</Banner> : null}
      {digest?.stale && !digest?.ingest_error ? (
        <Banner severity="info">Showing last stored chats. Live Cliq did not return new messages on the last Refresh.</Banner>
      ) : null}
      {loading ? (
        <Box role="status" aria-label="Loading Cliq digest" sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3 }}>
          {[1, 2, 3, 4].map((id) => <Skeleton key={id} variant="rounded" height={160} sx={{ borderRadius: "18px" }} />)}
        </Box>
      ) : (
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3, alignItems: "start" }}>
          <div>
            <DigestSection title="Follow up tomorrow" items={digest?.follow_up_tomorrow || []} empty="Nothing parked for tomorrow from the current window." onHide={hide} />
            <DigestSection title="Promises to keep" items={digest?.promises || []} empty="No open commitments from you in this window." onHide={hide} />
            <DigestSection title="Forgot to address" items={digest?.unanswered || []} empty="No unanswered pings in this window." onHide={hide} />
          </div>
          <div>
            <DigestSection title="Chats you were in" items={digest?.conversations || []} empty="No chats where you wrote something in this window." onHide={hide} />
          </div>
        </Box>
      )}
    </PageBody>
  );
}
