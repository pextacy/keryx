"use client";

import { createContext, useContext, type ReactNode } from "react";

interface CardProps {
  title: string;
  subtitle: string;
  children: ReactNode;
}

// Set true by an accordion row, which already shows the name + description in its
// header — so the card drops its own chrome and renders just the form body.
export const InAccordion = createContext(false);

export function Card({ title, subtitle, children }: CardProps) {
  if (useContext(InAccordion)) {
    return <>{children}</>;
  }
  return (
    <section className="glass-card p-5 transition-colors hover:border-primary-fixed-dim/30">
      <h2 className="font-headline-md text-[16px] font-semibold text-on-surface">{title}</h2>
      <p className="mt-0.5 text-sm text-on-surface-variant">{subtitle}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="font-label-caps text-[10px] uppercase text-on-surface-variant">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  // Connectivity hiccups read as calm guidance; genuine errors still stand out in red.
  const offline = /failed|fetch|network|unreachable|502|timeout/i.test(message);
  return (
    <p
      className={`mt-3 flex items-center gap-2 rounded border p-2 text-sm ${
        offline
          ? "border-white/10 bg-surface-container-low text-on-surface-variant"
          : "border-error/30 bg-error-container/20 text-error"
      }`}
    >
      <span className="material-symbols-outlined text-[16px]">{offline ? "cloud_off" : "error"}</span>
      {offline ? "Agent offline — start it with make agent to load this." : message}
    </p>
  );
}
