import type { Metadata } from "next";
import "../styles/globals.css";
import { ThemeProvider } from "@/components/landing/theme-provider";

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
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
