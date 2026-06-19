import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Keryx — citation-toll layer for the agent web",
  description:
    "Ask a question; watch a research agent pay every source it genuinely cites, live on Arc.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
