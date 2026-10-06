import type { NextRequest } from "next/server";
import { WORKSPACE_COOKIE, clerkEnabled } from "@/lib/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 300;

const BACKEND = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

// Hop-by-hop headers, plus ones the runtime recomputes (fetch already decoded gzip bodies).
const DROP_REQUEST = new Set(["host", "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "proxy-authorization", "content-length", "cookie", "authorization", "x-workspace"]);
const DROP_RESPONSE = new Set(["connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "content-encoding", "content-length"]);

type Context = { params: Promise<{ path: string[] }> };

async function sessionToken(): Promise<string> {
  if (!clerkEnabled) return "";
  const { auth } = await import("@clerk/nextjs/server");
  const session = await auth();
  return (await session.getToken()) || "";
}

function relativeLocation(location: string): string {
  if (location.startsWith(BACKEND)) return location.slice(BACKEND.length) || "/";
  return location;
}

async function forward(request: NextRequest, { params }: Context): Promise<Response> {
  const { path } = await params;
  const target = `${BACKEND}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!DROP_REQUEST.has(key.toLowerCase())) headers.set(key, value);
  });
  headers.set("x-forwarded-host", request.headers.get("host") || request.nextUrl.host);
  headers.set("x-forwarded-proto", request.nextUrl.protocol.replace(":", ""));
  const token = await sessionToken();
  if (token) headers.set("authorization", `Bearer ${token}`);
  else if (!clerkEnabled) {
    const workspace = request.cookies.get(WORKSPACE_COOKIE)?.value;
    if (workspace) headers.set("x-workspace", workspace);
  }

  const method = request.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: "manual",
      cache: "no-store",
      signal: request.signal,
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
  } catch (error) {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    const reason = error instanceof Error ? error.message : String(error);
    return Response.json({ detail: `The API is not reachable (${reason}).` }, { status: 502 });
  }

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    const name = key.toLowerCase();
    if (DROP_RESPONSE.has(name)) return;
    out.append(key, name === "location" ? relativeLocation(value) : value);
  });
  return new Response(method === "HEAD" ? null : upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: out });
}

export const GET = forward;
export const HEAD = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
export const OPTIONS = forward;
