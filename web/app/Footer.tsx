import { ARC_EXPLORER } from "@/lib/types";

const GITHUB = "https://github.com/pextacy/keryx";

export function Footer() {
  return (
    <footer className="mt-auto w-full border-t border-white/10 bg-surface-dim py-8">
      <div className="mx-auto flex max-w-container-max flex-col items-center justify-between space-y-4 px-gutter md:flex-row md:space-y-0">
        <div className="flex items-center gap-4">
          <span className="font-mono-data text-mono-data text-on-surface">KERYX_PROTOCOL_CORE</span>
          <span className="font-label-caps text-label-caps text-on-surface-variant opacity-80">
            © 2026 Keryx Protocol
          </span>
        </div>
        <div className="flex gap-8">
          <a
            href={GITHUB}
            target="_blank"
            className="font-label-caps text-label-caps text-on-surface-variant transition-colors hover:text-secondary-fixed-dim"
          >
            Github
          </a>
          <a
            href={ARC_EXPLORER}
            target="_blank"
            className="font-label-caps text-label-caps text-on-surface-variant transition-colors hover:text-secondary-fixed-dim"
          >
            Arc Explorer
          </a>
          <a
            href="/audit"
            className="font-label-caps text-label-caps text-on-surface-variant transition-colors hover:text-secondary-fixed-dim"
          >
            Audit
          </a>
        </div>
      </div>
    </footer>
  );
}
