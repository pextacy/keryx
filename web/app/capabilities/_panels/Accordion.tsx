"use client";

import { useEffect, useState, type ReactNode } from "react";
import { InAccordion } from "./Card";

// The verb is carried by colour, not repeated text: cyan rows write (POST),
// emerald rows read (GET). The group header above already names the method.
type Tone = "POST" | "GET";

const TONE: Record<Tone, { icon: string; openBorder: string }> = {
  POST: { icon: "text-primary-fixed-dim", openBorder: "border-primary-fixed-dim/40" },
  GET: { icon: "text-secondary-fixed-dim", openBorder: "border-secondary-fixed-dim/40" },
};

interface RowProps {
  name: string;
  desc: string;
  icon: string;
  tone: Tone;
  storageKey: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function AccordionRow({ name, desc, icon, tone, storageKey, defaultOpen = false, children }: RowProps) {
  const [open, setOpen] = useState(defaultOpen);

  // Remember each row's state across visits, after mount so SSR markup matches.
  useEffect(() => {
    const saved = localStorage.getItem(`keryx.row.${storageKey}`);
    if (saved !== null) setOpen(saved === "1");
  }, [storageKey]);

  const toggle = () => {
    setOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(`keryx.row.${storageKey}`, next ? "1" : "0");
      } catch {
        /* storage disabled — toggle still works, just not sticky */
      }
      return next;
    });
  };

  const t = TONE[tone];
  const bodyId = `row-${storageKey}`;

  return (
    <div className={`glass-card overflow-hidden transition-colors ${open ? t.openBorder : "hover:border-white/15"}`}>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={bodyId}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <span className={`material-symbols-outlined text-[20px] ${t.icon}`}>{icon}</span>
        <span className="min-w-0 flex-1">
          <span className="block font-medium text-on-surface">{name}</span>
          <span className="mt-0.5 block truncate text-xs text-on-surface-variant">{desc}</span>
        </span>
        <span
          className={`material-symbols-outlined shrink-0 text-on-surface-variant transition-transform duration-300 motion-reduce:transition-none ${
            open ? "rotate-180" : ""
          }`}
        >
          expand_more
        </span>
      </button>

      <div
        id={bodyId}
        className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="border-t border-white/5 px-4 pb-5 pt-4">
            <InAccordion.Provider value={true}>{children}</InAccordion.Provider>
          </div>
        </div>
      </div>
    </div>
  );
}
