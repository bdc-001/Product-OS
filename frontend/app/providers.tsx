"use client";

import { AppRouterCacheProvider } from "@mui/material-nextjs/v15-appRouter";
import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import { RefreshProvider } from "@/app/refresh";
import { CopilotProvider } from "@/app/copilot/context";
import { theme } from "@/app/theme";
import { WorkspaceProvider } from "@/app/workspace";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AppRouterCacheProvider options={{ enableCssLayer: true }}>
      <ThemeProvider theme={theme} defaultMode="light" modeStorageKey="pos-mode" disableTransitionOnChange>
        <CssBaseline />
        <WorkspaceProvider>
          <RefreshProvider>
            <CopilotProvider>{children}</CopilotProvider>
          </RefreshProvider>
        </WorkspaceProvider>
      </ThemeProvider>
    </AppRouterCacheProvider>
  );
}
