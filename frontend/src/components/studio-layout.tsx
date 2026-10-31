"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavSection {
  title: string;
  items: { href: string; label: string; icon: string }[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Build",
    items: [
      { href: "/agents", label: "Agents", icon: "🤖" },
      { href: "/agents/create", label: "Create Agent", icon: "➕" },
      { href: "/workflows", label: "Workflows", icon: "🔀" },
      { href: "/knowledge", label: "Knowledge", icon: "📚" },
    ],
  },
  {
    title: "Observe",
    items: [
      { href: "/analytics", label: "Analytics", icon: "📊" },
      { href: "/calls", label: "Call Replay", icon: "📞" },
      { href: "/evaluations", label: "Evaluations", icon: "🎯" },
      { href: "/coaching", label: "Live Coaching", icon: "🧠" },
    ],
  },
  {
    title: "Discover",
    items: [
      { href: "/marketplace", label: "Marketplace", icon: "🏪" },
    ],
  },
];

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen bg-[var(--color-bg)]">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 border-r border-[var(--color-border)] flex flex-col">
        {/* Logo */}
        <div className="px-4 py-4 border-b border-[var(--color-border)]">
          <Link href="/agents" className="flex items-center gap-2">
            <span className="text-xl">🎙️</span>
            <div>
              <h1 className="text-sm font-bold tracking-tight">
                Voice <span className="text-[var(--color-primary)]">AI</span>
              </h1>
              <p className="text-[9px] text-[var(--color-text-dim)] uppercase tracking-widest">
                Agent OS
              </p>
            </div>
          </Link>
        </div>

        {/* Nav sections */}
        <nav className="flex-1 py-2 px-2 overflow-y-auto space-y-4">
          {NAV_SECTIONS.map((section) => (
            <div key={section.title}>
              <p className="px-3 mb-1 text-[9px] font-semibold uppercase tracking-widest text-[var(--color-text-dim)]">
                {section.title}
              </p>
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const isActive =
                    item.href === "/agents"
                      ? pathname === "/agents"
                      : pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-[13px] transition-colors ${
                        isActive
                          ? "bg-[var(--color-primary)]/15 text-[var(--color-primary)]"
                          : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
                      }`}
                    >
                      <span className="text-sm">{item.icon}</span>
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[var(--color-border)]">
          <p className="text-[10px] text-[var(--color-text-dim)]">
            Voice AI — Agent OS v3.0
          </p>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
