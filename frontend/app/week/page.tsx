import { Suspense } from "react";
import { HomeView } from "@/app/home-view";
import { EmptyState, PageBody } from "@/app/ui";

export default function WeekPage() {
  return (
    <Suspense
      fallback={
        <PageBody>
          <EmptyState>Loading…</EmptyState>
        </PageBody>
      }
    >
      <HomeView />
    </Suspense>
  );
}
