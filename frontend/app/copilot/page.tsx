"use client";

import { Suspense, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCopilot } from "./context";

function OpenAndLeave() {
  const params = useSearchParams();
  const router = useRouter();
  const { open } = useCopilot();
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    open({
      plan: Number(params.get("plan") || 0) || undefined,
      document: Number(params.get("document") || 0) || undefined,
      note: Number(params.get("note") || 0) || undefined,
      epic: (params.get("epic") || "").trim() || undefined,
      notes: params.get("notes") || undefined,
    });
    router.replace("/");
  }, [open, params, router]);
  return null;
}

export default function CopilotRoute() {
  return (
    <Suspense fallback={null}>
      <OpenAndLeave />
    </Suspense>
  );
}
