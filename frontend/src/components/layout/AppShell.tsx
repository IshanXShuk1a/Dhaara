"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { IntersectionProvider } from "@/lib/intersectionContext";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { role, isLoading } = useAuth();

  if (pathname === "/login") return <div className="min-h-screen bg-surface-canvas px-4">{children}</div>;
  if (isLoading) return <div className="flex min-h-screen items-center justify-center bg-surface-canvas text-sm text-text-secondary" role="status">Loading DHAARA...</div>;
  if (!role) return null;

  return (
    <IntersectionProvider>
      <div className="app-shell flex h-dvh flex-col overflow-hidden bg-surface-canvas md:flex-row">
        <a href="#main-content" className="skip-link">Skip to content</a>
        <Sidebar />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <TopBar />
          <main id="main-content" tabIndex={-1} className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-3 md:p-4">{children}</main>
        </div>
      </div>
    </IntersectionProvider>
  );
}
