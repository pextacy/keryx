import type { ReactNode } from "react";

interface CardProps {
  title: string;
  subtitle: string;
  children: ReactNode;
}

export function Card({ title, subtitle, children }: CardProps) {
  return (
    <section className="rounded-lg border border-gray-200 p-5">
      <h2 className="text-lg font-medium">{title}</h2>
      <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="text-gray-600">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{message}</p>;
}
