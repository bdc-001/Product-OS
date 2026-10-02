"use client";

import { useAuth } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { clearHttpCache, setHttpScope } from "@/lib/http";
import { platform, type Me, type Role } from "@/lib/platform";
import { clerkEnabled, setWorkspaceCookie } from "@/lib/session";

const RANK: Record<string, number> = { member: 1, admin: 2, owner: 3 };

type WorkspaceState = {
  me: Me | null;
  loading: boolean;
  error: string;
  reload: () => Promise<void>;
  /** Local mode only: Clerk mode switches through the organization switcher. */
  switchTo: (slug: string) => void;
  can: (role: Role) => boolean;
};

const WorkspaceContext = createContext<WorkspaceState>({
  me: null,
  loading: true,
  error: "",
  reload: async () => undefined,
  switchTo: () => undefined,
  can: () => false,
});

export function useWorkspace() {
  return useContext(WorkspaceContext);
}

function hardReload(to = "/") {
  clearHttpCache();
  window.location.assign(to);
}

/** Clerk switches organizations in place; everything cached belongs to the old workspace. */
function ClerkOrgWatcher() {
  const { orgId, isLoaded } = useAuth();
  const seen = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (!isLoaded) return;
    const current = orgId ?? null;
    if (seen.current !== undefined && seen.current !== current) hardReload(window.location.pathname);
    seen.current = current;
  }, [orgId, isLoaded]);
  return null;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const path = usePathname() || "/";
  const authPage = /^\/sign-(in|up)(\/|$)/.test(path);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(!authPage);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    try {
      const next = await platform.me();
      setHttpScope(next.workspace.slug);
      setMe(next);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your workspace.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authPage) void reload();
  }, [authPage, reload]);

  const value = useMemo<WorkspaceState>(
    () => ({
      me,
      loading,
      error,
      reload,
      switchTo: (slug: string) => {
        if (clerkEnabled || slug === me?.workspace.slug) return;
        setWorkspaceCookie(slug);
        hardReload("/");
      },
      can: (role: Role) => (RANK[me?.role || ""] || 0) >= (RANK[role] || 99),
    }),
    [me, loading, error, reload],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {clerkEnabled ? <ClerkOrgWatcher /> : null}
      {children}
    </WorkspaceContext.Provider>
  );
}
