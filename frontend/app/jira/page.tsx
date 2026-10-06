"use client";

import { api } from "@/lib/api";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { BoardModule } from "@/app/board-module";
import { EmptyState, PageBody } from "@/app/ui";

function JiraBoard() {
  const params = useSearchParams();
  const [projects, setProjects] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.platform().then(data => setProjects(Object.keys(data.boards || {}))).catch(e => setError(String(e))); }, []);
  if (error) return <PageBody><EmptyState>{error}</EmptyState></PageBody>;
  if (!projects) return <PageBody><EmptyState>Loading projects…</EmptyState></PageBody>;
  if (!projects.length) return <PageBody><EmptyState>Add the Jira projects to sync in <a href="/settings/connections?provider=jira">Connections → Jira</a>.</EmptyState></PageBody>;
  const requested = (params.get("board") || "").toUpperCase();
  const board = projects.includes(requested) ? requested : projects[0];
  return <BoardModule key={board} board={board} projects={projects} />;
}

export default function JiraPage() {
  return (
    <Suspense
      fallback={
        <PageBody>
          <EmptyState>Opening Jira…</EmptyState>
        </PageBody>
      }
    >
      <JiraBoard />
    </Suspense>
  );
}
