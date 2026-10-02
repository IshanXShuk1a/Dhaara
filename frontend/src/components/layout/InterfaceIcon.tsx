import type { ReactNode, SVGProps } from "react";

export type IconName = "dashboard" | "intersection" | "emergency" | "simulation" | "settings" | "logout" | "sun" | "moon";

const paths: Record<IconName, ReactNode> = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  intersection: <><path d="M9 3v6H3v6h6v6h6v-6h6V9h-6V3z" /><path d="M12 4v3m0 10v3M4 12h3m10 0h3" /></>,
  emergency: <><path d="M6 16V9a6 6 0 0 1 12 0v7M4 16h16v4H4zM12 6v4m0 2h.01" /><path d="M2 5l2 2m16 0 2-2M12 1v1" /></>,
  simulation: <><path d="m12 3 9 5v8l-9 5-9-5V8z" /><path d="m3 8 9 5 9-5M12 13v8M7.5 5.5l9 5" /></>,
  settings: <><path d="M4 7h16M4 17h16" /><circle cx="8" cy="7" r="3" /><circle cx="16" cy="17" r="3" /></>,
  logout: <><path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5" /></>,
  moon: <path d="M20 14A8 8 0 0 1 10 4a8.2 8.2 0 1 0 10 10Z" />,
};

export function InterfaceIcon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...props}>{paths[name]}</svg>;
}
