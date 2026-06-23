"use client";

import { useEffect, useState, type ReactNode } from "react";

// Sections are tagged by HTTP verb because that is the honest split for this page:
// POST moves money / changes state, GET reads it, DOCS is reference. The header reads
// like a request line so the taxonomy is the design, not decoration.
type Method = "POST" | "GET" | "DOCS";

const METHOD: Record<Method, { text: string; border: string; bg: string }> = {
  POST: {
    text: "text-primary-fixed-dim",
    border: "border-primary-fixed-dim/40",
    bg: "bg-primary-fixed-dim/10",
  },
  GET: {
    text: "text-secondary-fixed-dim",
    border: "border-secondary-fixed-dim/40",
    bg: "bg-secondary-fixed-dim/10",
  },
  DOCS: {
    text: "text-on-surface-variant",
    border: "border-white/15",
    bg: "bg-white/5",
  },
};

interface SectionProps {
  method: Method;
  title: string;
  subtitle: string;
  count: number;
  noun: string;
  defaultOpen?: boolean;
  storageKey: string;
  layout?: "stack" | "single";
  children: ReactNode;
}

export function Section({
  method,
  title,
  subtitle,
  count,
  noun,
  defaultOpen = true,
  storageKey,
  layout = "stack",
  children,
}: SectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  // Restore the reader's last choice — but only after mount, so SSR markup matches.
  useEffect(() => {
    const saved = localStorage.getItem(`keryx.section.${storageKey}`);
    if (saved !== null) setOpen(saved === "1");
  }, [storageKey]);

  const toggle = () => {
    setOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(`keryx.section.${storageKey}`, next ? "1" : "0");
      } catch {
        /* private mode / storage disabled — collapse still works, just not sticky */
      }
      return next;
    });
  };

  const m = METHOD[method];
  const bodyId = `section-${storageKey}`;

  return (
    <section className="mt-6">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={bodyId}
        className={`glass-card flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:border-white/20 ${
          open ? m.border : ""
        }`}
      >
        <span
          className={`font-mono-data rounded border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${m.text} ${m.border} ${m.bg}`}
        >
          {method}
        </span>
        <span className="min-w-0">
          <span className="block font-headline-md text-[15px] font-semibold text-on-surface">{title}</span>
          <span className="block truncate text-xs text-on-surface-variant">{subtitle}</span>
        </span>
        <span className="ml-auto flex shrink-0 items-center gap-3">
          <span className="hidden font-label-caps text-[10px] uppercase text-on-surface-variant sm:inline">
            {count} {noun}
          </span>
          <span
            className={`material-symbols-outlined text-on-surface-variant transition-transform duration-300 ${
              open ? "rotate-180" : ""
            }`}
          >
            expand_more
          </span>
        </span>
      </button>

      <div
        id={bodyId}
        className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className={layout === "stack" ? "space-y-2 pt-3" : "pt-4"}>{children}</div>
        </div>
      </div>
    </section>
  );
}
