"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useIntersections } from "@/lib/intersectionContext";
import { api } from "@/lib/api";

const NAV_ITEMS = [
  {
    href: "/",
    label: "Dashboard",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
  },
  {
    href: "/classify",
    label: "Image Classifier",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    href: "/intersections",
    label: "Intersections",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
  {
    href: "/analytics",
    label: "Analytics",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    href: "/emergencies",
    label: "Emergencies",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
    ),
  },
  {
    href: "/safety",
    label: "Road Safety",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    href: "/simulation",
    label: "Simulation",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { logout } = useAuth();
  const { intersections, selectedId, setSelectedId } = useIntersections();
  const [health, setHealth] = useState<{ status: string; intersection_count: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.health().then((h) => {
      if (!cancelled) setHealth(h);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return (
    <aside className="w-64 shrink-0 border-r border-surface-border bg-surface-raised flex flex-col justify-between p-4 select-none transition-colors duration-300">
      <div className="space-y-6">
        {/* Brand / Logo matching the mockup header style */}
        <div className="flex items-center gap-3 px-2 pt-1">
          <div className="w-9 h-9 rounded-xl border border-surface-border bg-surface-pill flex items-center justify-center font-mono font-bold text-sm text-text-primary shadow-inner">
            D
          </div>
          <div>
            <div className="text-base font-extrabold tracking-tight text-text-primary">DHAARA</div>
            <div className="text-[10px] text-text-muted italic -mt-0.5">smart traffic • its</div>
          </div>
        </div>

        {/* Navigation list: Active item is a solid pill button */}
        <nav className="space-y-1.5">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  "btn-tactile flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all duration-200",
                  isActive
                    ? "dark:bg-white dark:text-gray-950 bg-slate-900 text-white shadow-md transform scale-[1.02]"
                    : "text-text-secondary hover:text-text-primary hover:bg-surface-cardHover hover:translate-x-1"
                )}
              >
                <span className={clsx(isActive ? "dark:text-gray-950 text-white" : "text-text-muted")}>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Sub-panel: Active Intersections / Nodes */}
        <div className="card p-3 space-y-2.5 bg-surface-card border border-surface-border">
          <div className="flex items-center justify-between text-[11px] font-semibold text-text-muted uppercase tracking-wider px-1">
            <span>Live Nodes</span>
            <span className="text-[10px] font-mono text-accent flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              {intersections.length} Active
            </span>
          </div>

          <div className="space-y-1.5">
            {intersections.slice(0, 3).map((node) => {
              const isSelected = selectedId === node.id;
              return (
                <button
                  key={node.id}
                  onClick={() => setSelectedId(node.id)}
                  className={clsx(
                    "btn-tactile w-full flex items-center gap-2.5 p-2 rounded-xl text-left transition-all",
                    isSelected ? "bg-surface-pill border border-surface-border shadow-sm" : "hover:bg-surface-cardHover hover:translate-x-0.5"
                  )}
                >
                  <div className="w-7 h-7 rounded-lg bg-surface-pill border border-surface-border flex items-center justify-center text-[10px] font-mono text-text-primary shadow-inner">
                    {node.id.split("-").pop() || "01"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-text-primary truncate">{node.name}</div>
                    <div className="text-[10px] text-text-muted truncate">{node.location}</div>
                  </div>
                  <div className="relative flex items-center justify-center w-2 h-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-status-online" />
                    <span className="absolute inset-0 rounded-full bg-status-online animate-ping opacity-75" />
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bottom Section: Settings & Logout */}
      <div className="pt-4 border-t border-surface-border space-y-1 text-xs">
        <Link
          href="/settings"
          className={clsx(
            "btn-tactile flex items-center gap-3 px-3.5 py-2 rounded-xl text-text-secondary hover:text-text-primary hover:bg-surface-cardHover transition-colors",
            pathname === "/settings" && "bg-surface-pill text-text-primary font-semibold border border-surface-border"
          )}
        >
          <svg className="w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span>Settings</span>
        </Link>

        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3.5 py-2 rounded-xl text-rose-500 hover:text-rose-600 hover:bg-rose-500/10 transition-colors"
        >
          <svg className="w-4 h-4 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span className="font-medium">Logout</span>
        </button>
      </div>
    </aside>
  );
}
