import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "./Nav";

export const metadata: Metadata = {
  title: {
    default: "Keryx — citation-toll layer for the agent web",
    template: "%s · Keryx",
  },
  description:
    "Your work earns every time an agent cites it. A research agent pays every source it " +
    "genuinely cites — sub-cent USDC, live on Arc, pay-on-citation not pay-on-fetch.",
  openGraph: {
    title: "Keryx — citation-toll layer for the agent web",
    description: "A research agent pays every source it genuinely cites, live on Arc.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}
