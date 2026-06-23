"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NetworkStatus } from "./HealthDot";

const LINKS: { href: string; label: string }[] = [
  { href: "/", label: "Ask" },
  { href: "/capabilities", label: "Capabilities" },
  { href: "/ledger", label: "Ledger" },
  { href: "/audit", label: "Audit" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="fixed top-0 z-50 w-full border-b border-white/10 bg-background/80 shadow-[0_0_15px_rgba(0,219,233,0.1)] backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-container-max items-center justify-between px-gutter">
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="font-headline-md text-headline-md font-bold tracking-tight text-primary-fixed-dim"
          >
            Keryx
          </Link>
          <div className="hidden items-center gap-6 md:flex">
            {LINKS.map((l) => {
              const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={
                    active
                      ? "border-b-2 border-primary-fixed-dim pb-1 font-body-md text-body-md font-bold text-primary-fixed-dim"
                      : "font-body-md text-body-md text-on-surface-variant transition-colors hover:text-primary-fixed-dim"
                  }
                >
                  {l.label}
                </Link>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-4">
          <NetworkStatus />
          <button
            type="button"
            className="bg-primary-fixed-dim px-6 py-2 font-label-caps text-label-caps font-bold text-on-primary-fixed shadow-[0_0_20px_rgba(0,219,233,0.3)] transition-all hover:brightness-110 active:scale-95"
          >
            Connect Wallet
          </button>
        </div>
      </div>
    </nav>
  );
}
