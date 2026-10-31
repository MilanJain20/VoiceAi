"use client";

export function ComingSoon({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-md text-center">
        <p className="text-xs uppercase tracking-wider text-[var(--color-text-dim)] mb-2">Coming soon</p>
        <h1 className="text-lg font-semibold mb-2">{title}</h1>
        <p className="text-sm text-[var(--color-text-muted)]">{detail}</p>
      </div>
    </div>
  );
}
