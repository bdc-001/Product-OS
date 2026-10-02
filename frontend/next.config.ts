import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

// `/api/*` is forwarded at runtime by app/api/[...path]/route.ts using BACKEND_URL.
const nextConfig = (phase: string): NextConfig => ({
  // Keep production builds from overwriting a running dev server's output.
  distDir: phase === PHASE_DEVELOPMENT_SERVER ? ".next-dev" : ".next",
  output: "standalone",
  transpilePackages: ["@codesandbox/sandpack-react", "@codesandbox/sandpack-client"],
  async redirects() {
    return ["pipelines", "connections", "repositories"].flatMap((page) => [
      { source: `/${page}`, destination: `/settings/${page}`, permanent: false },
      { source: `/${page}/:rest*`, destination: `/settings/${page}/:rest*`, permanent: false },
    ]).concat({ source: "/settings/codebase", destination: "/settings/repositories", permanent: false });
  },
  experimental: {
    staleTimes: {
      dynamic: 30,
      static: 180,
    },
  },
});

export default nextConfig;
