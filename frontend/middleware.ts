import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";

// API routes authenticate in FastAPI, which answers 401 with a JSON detail the UI understands.
const isPublic = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/api(.*)"]);

const withClerk = clerkMiddleware(async (auth, request) => {
  if (!isPublic(request)) await auth.protect();
});

export default function middleware(request: NextRequest, event: NextFetchEvent) {
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    if (/^\/sign-(in|up)(\/|$)/.test(request.nextUrl.pathname)) return NextResponse.redirect(new URL("/", request.url));
    return NextResponse.next();
  }
  return withClerk(request, event);
}

export const config = {
  matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest|mp4|mp3|wav)).*)", "/(api|trpc)(.*)"],
};
