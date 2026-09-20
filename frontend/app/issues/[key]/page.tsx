"use client";

import Box from "@mui/material/Box";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@/app/ui/stack";
import Typography from "@mui/material/Typography";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, EmptyState, FrostCard, PageBody, PageHeader, PagedList, Section, StatusChip, TicketLink } from "@/app/ui";
import { apple } from "@/app/theme";

export default function IssueDetailPage() {
  const params = useParams<{ key: string }>();
  const issueKey = params.key;
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const { tick } = useRefresh();

  useEffect(() => {
    if (!issueKey) return;
    setData(null);
    setError("");
    api
      .issue(issueKey)
      .then(setData)
      .catch((err) => setError(String(err)));
  }, [issueKey, tick]);

  const issue = (data?.issue || {}) as Record<string, unknown>;
  const changes = (data?.changes || []) as Record<string, string>[];
  const cliq = (data?.cliq || []) as Record<string, string>[];
  const insights = (data?.insights || []) as Record<string, string>[];
  const checklist = (issue.field_checklist || []) as { label: string; value: string; required?: boolean; empty?: boolean }[];
  const missing = (issue.missing_fields || []) as string[];
  const comments = (data?.comments || []) as Record<string, string>[];
  const commentRows = comments.length ? comments : cliq;
  const loading = Boolean(issueKey) && !data && !error;

  return (
    <PageBody>
      <PageHeader title={issueKey || ""} subtitle={loading ? "Loading ticket…" : String(issue.summary || "")} />
      {error ? <Banner severity="error">{error}</Banner> : null}
      {loading ? (
        <Box role="status" aria-label="Loading ticket details" sx={{ display: "grid", gap: 2 }}>
          <Skeleton width="40%" height={28} />
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3 }}>
            <Skeleton variant="rounded" height={180} sx={{ borderRadius: "18px" }} />
            <Skeleton variant="rounded" height={180} sx={{ borderRadius: "18px" }} />
          </Box>
          <Skeleton variant="rounded" height={140} sx={{ borderRadius: "18px" }} />
        </Box>
      ) : null}
      {!loading ? (
        <>
      {data?.why_unknown ? <Banner severity="warning">{String(data.why_unknown)}</Banner> : null}
      <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
        {issue.status ? <StatusChip label={String(issue.status)} /> : null}
        {issue.priority ? <StatusChip label={String(issue.priority)} /> : null}
        {issue.assignee ? <StatusChip label={String(issue.assignee)} /> : null}
      </Stack>
      {issue.url ? (
        <TicketLink href={String(issue.url)}>Open in Jira</TicketLink>
      ) : null}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 3, mt: 3 }}>
        <Section title={issue.schema_kind === "bug" ? "Bug fields" : issue.schema_kind === "report" ? "Product/Report Requirement fields" : "Task fields"}>
          {missing.length ? (
            <Typography sx={{ mb: 1, fontSize: 13, color: apple.danger }}>Missing required: {missing.join(", ")}</Typography>
          ) : null}
          <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 13 }}>
            {checklist.map((row) => (
              <Box component="li" key={row.label} sx={{ color: row.empty && row.required ? apple.danger : apple.text, mb: 0.5 }}>
                {row.label}: {row.empty ? "—" : row.value}
              </Box>
            ))}
          </Box>
        </Section>
        <Section title="Cliq discussion" count={commentRows.length}>
          <PagedList
            items={commentRows}
            getKey={(_, index) => index}
            empty={<EmptyState>No matching Cliq messages stored.</EmptyState>}
            renderItem={(message) => (
              <FrostCard>
                <Typography variant="h3">{message.chat_name || message.author || "Comment"}</Typography>
                <Typography sx={{ mt: 0.75, fontSize: 15 }}>
                  {message.sender ? `${message.sender}: ` : ""}
                  {message.message || message.body || ""}
                </Typography>
              </FrostCard>
            )}
          />
        </Section>
      </Box>

      <Section title="Linked via Cliq">
        {((data?.correlations || []) as { match_reason?: string; confidence?: string; chat_name?: string }[]).map((row, index) => (
          <Typography key={index} sx={{ fontSize: 15, color: apple.muted }}>
            {row.match_reason || "linked"} {row.confidence ? `· ${row.confidence}` : ""}
          </Typography>
        ))}
        {!(data?.correlations as unknown[] | undefined)?.length ? <EmptyState>No stored chat↔ticket links.</EmptyState> : null}
      </Section>

      <Section title="Jira changes" count={changes.length}>
        <PagedList
          items={changes}
          getKey={(_, index) => index}
          empty={<EmptyState>No changes in the last window.</EmptyState>}
          renderItem={(change) => (
            <FrostCard>
              <Typography variant="h3">{change.type}</Typography>
              <Typography sx={{ mt: 0.75, fontSize: 15 }}>
                {change.field}: {change.from || "—"} → {change.to || "—"}
              </Typography>
            </FrostCard>
          )}
        />
      </Section>

      <Section title="Insights" count={insights.length}>
        <PagedList
          items={insights}
          getKey={(_, index) => index}
          empty={<EmptyState>No insights for this ticket.</EmptyState>}
          renderItem={(insight) => (
            <FrostCard>
              <Typography variant="h3">{insight.title}</Typography>
              <Typography sx={{ mt: 0.75, fontSize: 15 }}>{insight.description}</Typography>
              {insight.why ? (
                <Typography sx={{ mt: 0.5, fontSize: 13, color: apple.muted }}>{insight.why}</Typography>
              ) : null}
            </FrostCard>
          )}
        />
      </Section>
        </>
      ) : null}
    </PageBody>
  );
}
