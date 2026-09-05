import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="mt-1 text-slate-400">{description}</p>
    </header>
  );
}

export function Card({ children }: { children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-700 bg-navy-900 p-6 shadow">
      {children}
    </section>
  );
}
