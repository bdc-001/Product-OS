"use client";

import { AppRouterCacheProvider } from "@mui/material-nextjs/v15-appRouter";
import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider } from "@mui/material/styles";
import { RefreshProvider } from "@/app/refresh";
import { CopilotProvider } from "@/app/copilot/context";
import { theme } from "@/app/theme";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AppRouterCacheProvider options={{ enableCssLayer: true }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <RefreshProvider>
          <CopilotProvider>{children}</CopilotProvider>
        </RefreshProvider>
      </ThemeProvider>
    </AppRouterCacheProvider>
  );
}
