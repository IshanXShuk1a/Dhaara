"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { InterfaceIcon, type IconName } from "./InterfaceIcon";

const NAV_ITEMS: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Dashboard", icon: "dashboard" },
  { href: "/intersections", label: "Intersections", icon: "intersection" },
  { href: "/emergencies", label: "Emergencies", icon: "emergency" },
  { href: "/simulation", label: "Simulation", icon: "simulation" },
  { href: "/settings", label: "Settings", icon: "settings" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { logout } = useAuth();
  return (
    <aside className="app-sidebar w-full shrink-0 border-b border-surface-border md:w-[72px] md:border-b-0 md:border-r xl:w-[200px] flex flex-col">
      <div className="flex h-[60px] shrink-0 items-center justify-between gap-3 px-4 md:justify-center md:px-0 xl:justify-start xl:px-5">
        <Link href="/" aria-label="DHAARA dashboard" className="flex items-center gap-3">
          <span className="brand-mark flex h-9 w-9 items-center justify-center rounded-xl" aria-hidden="true"><InterfaceIcon name="intersection" className="h-5 w-5" /></span>
          <span className="md:hidden xl:block"><span className="block text-[15px] font-extrabold tracking-[0.09em] text-text-primary">DHAARA</span><span className="block text-[10px] text-text-secondary">Traffic control</span></span>
        </Link>
        <button onClick={logout} aria-label="Log out" title="Log out" className="rounded-lg p-2 text-text-secondary hover:bg-surface-elevated md:hidden"><InterfaceIcon name="logout" className="h-4 w-4" /></button>
      </div>
      <div className="hidden px-5 pb-3 pt-7 text-[10px] font-semibold uppercase tracking-[0.15em] text-text-muted xl:block">Workspace</div>
      <nav aria-label="Main navigation" className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:overflow-visible md:px-3 md:pb-0 md:pt-5 xl:pt-0">
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
          return <Link key={href} href={href} aria-label={label} aria-current={active ? "page" : undefined} title={label}
            className={`nav-link flex shrink-0 items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-[11px] font-medium md:gap-3 md:py-3 xl:justify-start xl:text-[13px] ${active ? "nav-link-active text-accent" : "text-text-secondary hover:bg-surface-elevated hover:text-text-primary"}`}>
            <InterfaceIcon name={icon} className="h-[18px] w-[18px] shrink-0" />
            <span className="md:hidden xl:inline">{label}</span>
            {href === "/simulation" && <span className="ml-auto hidden rounded border border-current/20 px-1.5 py-0.5 text-[9px] xl:block">3D</span>}
          </Link>;
        })}
      </nav>
      <div className="mt-auto hidden p-3 md:block">
        <div className="border-t border-surface-border pt-3">
          <button onClick={logout} aria-label="Log out" title="Log out" className="flex w-full items-center justify-center gap-3 rounded-xl px-3 py-3 text-xs text-text-secondary hover:bg-surface-elevated hover:text-text-primary xl:justify-start"><InterfaceIcon name="logout" className="h-[18px] w-[18px]" /><span className="hidden xl:inline">Log out</span></button>
        </div>
      </div>
    </aside>
  );
}
