import Link from "next/link";
import { HealthDot } from "./HealthDot";

const LINKS: { href: string; label: string }[] = [
  { href: "/", label: "Ask" },
  { href: "/capabilities", label: "Capabilities" },
  { href: "/ledger", label: "Ledger" },
  { href: "/audit", label: "Audit" },
];

export function Nav() {
  return (
    <nav className="border-b border-gray-200">
      <div className="mx-auto flex max-w-5xl items-center gap-5 px-8 py-3 text-sm">
        <Link href="/" className="font-semibold">
          Keryx
        </Link>
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className="text-gray-600 hover:text-black">
            {l.label}
          </Link>
        ))}
        <span className="ml-auto flex items-center gap-1.5 text-xs text-gray-400">
          <HealthDot />
          agent
        </span>
      </div>
    </nav>
  );
}
