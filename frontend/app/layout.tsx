import { ClerkProvider } from "@clerk/nextjs";
import InitColorSchemeScript from "@mui/material/InitColorSchemeScript";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { clerkAppearance } from "./auth-frame";
import { AppProviders } from "./providers";
import { Shell } from "./shell";
import { clerkEnabled } from "@/lib/session";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Product OS",
  description: "Connect your product tools once and run briefings, releases, marketing and video pipelines per workspace.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const app = (
    <AppProviders>
      <Shell>{children}</Shell>
    </AppProviders>
  );
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body>
        <InitColorSchemeScript attribute="class" defaultMode="light" modeStorageKey="pos-mode" />
        {clerkEnabled ? (
          <ClerkProvider appearance={clerkAppearance} signInUrl="/sign-in" signUpUrl="/sign-up">
            {app}
          </ClerkProvider>
        ) : (
          app
        )}
      </body>
    </html>
  );
}
