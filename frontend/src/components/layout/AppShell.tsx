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
        {/* Ambient Atmosphere: Layered Slow Drift Fields & Subtle City Traffic Network */}
        <div aria-hidden="true" className="fixed inset-0 pointer-events-none overflow-hidden z-0">
          {/* Extremely slow ambient light fields (28s, 36s, 32s ease-in-out) */}
          <div className="absolute top-[-15%] left-[-10%] w-[720px] h-[720px] rounded-full bg-[#37D6B0]/[0.035] blur-[160px] animate-ambient-1" />
          <div className="absolute top-[25%] right-[-8%] w-[680px] h-[680px] rounded-full bg-[#5EA7FF]/[0.028] blur-[170px] animate-ambient-2" />
          <div className="absolute bottom-[-15%] left-[28%] w-[760px] h-[760px] rounded-full bg-[#42D392]/[0.022] blur-[180px] animate-ambient-3" />

          {/* Subtle City Traffic Network Corridors & Sparse Deterministic Flow Particles */}
          <svg
            className="absolute inset-0 w-full h-full opacity-60 dark:opacity-35 pointer-events-none select-none"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 1440 900"
            preserveAspectRatio="none"
          >
            {/* Arterial Corridor Lines */}
            <path
              d="M 120 220 L 720 220 L 720 540 L 1320 540"
              fill="none"
              stroke="rgba(55,214,176,0.035)"
              strokeWidth="1"
            />
            <path
              d="M 280 680 L 280 340 L 980 340 L 980 180"
              fill="none"
              stroke="rgba(94,167,255,0.03)"
              strokeWidth="1"
            />
            {/* Intersection Nodes */}
            <circle cx="120" cy="220" r="2" fill="rgba(55,214,176,0.15)" />
            <circle cx="720" cy="220" r="2.5" fill="rgba(55,214,176,0.2)" />
            <circle cx="720" cy="540" r="2.5" fill="rgba(55,214,176,0.2)" />
            <circle cx="1320" cy="540" r="2" fill="rgba(55,214,176,0.15)" />
            <circle cx="280" cy="680" r="2" fill="rgba(94,167,255,0.15)" />
            <circle cx="280" cy="340" r="2.5" fill="rgba(94,167,255,0.2)" />
            <circle cx="980" cy="340" r="2.5" fill="rgba(94,167,255,0.2)" />
            <circle cx="980" cy="180" r="2" fill="rgba(94,167,255,0.15)" />

            {/* Sparse, slow traffic pulse particles (26s & 32s deterministic paths) */}
            <circle r="1.75" fill="#37D6B0" opacity="0.45">
              <animateMotion
                path="M 120 220 L 720 220 L 720 540 L 1320 540"
                dur="26s"
                repeatCount="indefinite"
              />
            </circle>
            <circle r="1.5" fill="#5EA7FF" opacity="0.4">
              <animateMotion
                path="M 280 680 L 280 340 L 980 340 L 980 180"
                dur="32s"
                repeatCount="indefinite"
              />
            </circle>
          </svg>
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
