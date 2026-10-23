import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TruthGuard — Adversarial document verification",
  description:
    "Multi-agent document Q&A that retrieves competing evidence, challenges contradictions, and abstains when precedence cannot be established.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
