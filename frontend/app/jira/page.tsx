"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { BoardModule } from "@/app/board-module";
import { EmptyState, PageBody } from "@/app/ui";

function JiraBoard() {
  const params = useSearchParams();
  const board = params.get("board") === "PS" ? "PS" : "AC";
  return <BoardModule board={board} />;
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
