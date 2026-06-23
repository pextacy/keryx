import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "./Nav";
import { Footer } from "./Footer";

export const metadata: Metadata = {
  title: {
    default: "Keryx — citation-toll payment layer for the agent web",
    template: "%s · Keryx",
  },
  description:
    "Your work earns every time an agent cites it. A research agent pays every source it " +
    "genuinely cites — sub-cent USDC, live on Arc, pay-on-citation not pay-on-fetch.",
  openGraph: {
    title: "Keryx — citation-toll payment layer for the agent web",
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
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block"
          rel="stylesheet"
        />
      </head>
      <body className="overflow-x-hidden antialiased">
        <Nav />
        {children}
        <Footer />
      </body>
    </html>
  );
}
