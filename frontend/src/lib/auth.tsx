"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api, setToken, setStoredRole, getStoredRole, ApiError } from "./api";

interface AuthContextValue {
  role: string | null;
  username: string | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const storedRole = getStoredRole();
    if (storedRole) {
      setRole(storedRole);
      api
        .me()
        .then((me) => setUsername(me.username))
        .catch(() => {
          // Token expired/invalid - clear and force re-login.
          setToken(null);
          setStoredRole(null);
          setRole(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isLoading && !role && pathname !== "/login") {
      router.replace("/login");
    }
  }, [isLoading, role, pathname, router]);

  async function login(user: string, password: string) {
    const result = await api.login(user, password);
    setToken(result.access_token);
    setStoredRole(result.role);
    setRole(result.role);
    setUsername(user);
    router.replace("/");
  }

  function logout() {
    setToken(null);
    setStoredRole(null);
    setRole(null);
    setUsername(null);
    router.replace("/login");
  }

  return <AuthContext.Provider value={{ role, username, isLoading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function canOperate(role: string | null): boolean {
  return role === "ADMIN" || role === "TRAFFIC_OPERATOR";
}

export { ApiError };
