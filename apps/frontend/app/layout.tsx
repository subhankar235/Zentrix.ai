import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import "../styles/globals.css";
import { ThemeProvider } from "@/components/landing/theme-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { ClerkAuthSync } from "@/components/providers/clerk-auth-sync";

const title = "Zentrix — AI-Powered Database Intelligence";
const description =
  "An autonomous AI platform that collects deterministic evidence, diagnoses root causes with specialist agents, and statistically verifies every fix before you approve it.";

export const metadata: Metadata = {
  title,
  description,
  openGraph: {
    title,
    description,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      signInFallbackRedirectUrl="/dashboard"
      signUpFallbackRedirectUrl="/dashboard"
    >
      <html lang="en" className="dark" suppressHydrationWarning>
        <body className="min-h-screen bg-background font-sans antialiased">
          <QueryProvider>
            <ClerkAuthSync>
              <ThemeProvider>{children}</ThemeProvider>
            </ClerkAuthSync>
          </QueryProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
