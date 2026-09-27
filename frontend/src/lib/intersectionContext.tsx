"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api } from "./api";
import type { Intersection } from "./types";
import { useAuth } from "./auth";

interface IntersectionContextValue {
  intersections: Intersection[];
  selectedId: string | null;
  setSelectedId: (id: string) => void;
  isLoading: boolean;
  error: string | null;
  refresh: () => void;
}

const IntersectionContext = createContext<IntersectionContextValue | null>(null);

export function IntersectionProvider({ children }: { children: ReactNode }) {
  const { role } = useAuth();
  const [intersections, setIntersections] = useState<Intersection[]>([]);
  const [selectedId, setSelectedIdState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function setSelectedId(id: string) {
    setSelectedIdState(id);
    if (typeof window !== "undefined") window.localStorage.setItem("dhaara_selected_intersection", id);
  }

  function refresh() {
    if (!role) return;
    setIsLoading(true);
    api
      .listIntersections()
      .then((list) => {
        setIntersections(list);
        setError(null);
        const stored = typeof window !== "undefined" ? window.localStorage.getItem("dhaara_selected_intersection") : null;
        if (stored && list.some((i) => i.id === stored)) {
          setSelectedIdState(stored);
        } else if (list.length > 0) {
          setSelectedIdState(list[0].id);
        }
      })
      .catch((err) => setError(err.message || "Could not load intersections"))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role]);

  return (
    <IntersectionContext.Provider value={{ intersections, selectedId, setSelectedId, isLoading, error, refresh }}>
      {children}
    </IntersectionContext.Provider>
  );
}

export function useIntersections(): IntersectionContextValue {
  const ctx = useContext(IntersectionContext);
  if (!ctx) throw new Error("useIntersections must be used within IntersectionProvider");
  return ctx;
}
