/** Sign-in is Clerk when a publishable key is configured; otherwise the app runs in local single-user mode. */
export const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

/** Local mode keeps the chosen workspace in this cookie; the API proxy forwards it as `X-Workspace`. */
export const WORKSPACE_COOKIE = "pos_workspace";

export function setWorkspaceCookie(slug: string) {
  const maxAge = 60 * 60 * 24 * 365;
  document.cookie = `${WORKSPACE_COOKIE}=${encodeURIComponent(slug)}; path=/; max-age=${maxAge}; samesite=lax`;
}

export function signInUrl(): string {
  const back = typeof window === "undefined" ? "/" : window.location.pathname + window.location.search;
  return `/sign-in?redirect_url=${encodeURIComponent(back)}`;
}
