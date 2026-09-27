"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { IntersectionProvider } from "@/lib/intersectionContext";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { role, isLoading } = useAuth();

  if (pathname === "/login") {
    return <div className="min-h-screen bg-surface">{children}</div>;
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface text-text-secondary text-sm">
        Loading DHAARA...
      </div>
    );
  }

  if (!role) {
    // AuthProvider will redirect to /login; render nothing meanwhile.
    return null;
  }

  return (
    <IntersectionProvider>
      <div className="min-h-screen p-2 sm:p-6 flex flex-col justify-center relative overflow-hidden transition-colors duration-400">
        {/* Floating Ambient Atmosphere Orbs */}
        <div aria-hidden="true" className="fixed inset-0 pointer-events-none overflow-hidden z-0">
          <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full bg-indigo-300/40 dark:bg-purple-600/20 blur-[130px] animate-float-slow transition-colors duration-700" />
          <div className="absolute top-[25%] right-[-5%] w-[450px] h-[450px] rounded-full bg-sky-300/45 dark:bg-cyan-500/15 blur-[140px] animate-float-slow-reverse transition-colors duration-700" />
          <div className="absolute bottom-[-10%] left-[35%] w-[550px] h-[550px] rounded-full bg-amber-200/35 dark:bg-emerald-500/15 blur-[150px] animate-float-slow transition-colors duration-700" />
        </div>

        <div className="dashboard-cockpit overflow-hidden flex min-h-[94vh] relative z-10 backdrop-blur-[2px]">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0 bg-transparent transition-colors duration-300">
            <TopBar />
            <main className="flex-1 p-5 overflow-x-hidden overflow-y-auto">{children}</main>
          </div>
        </div>
      </div>
    </IntersectionProvider>
  );
}
