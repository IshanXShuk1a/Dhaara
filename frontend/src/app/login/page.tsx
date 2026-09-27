"use client";

import { useState, FormEvent } from "react";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form onSubmit={handleSubmit} className="card w-full max-w-sm p-8 space-y-5">
        <div>
          <div className="text-xl font-bold text-text-primary">DHAARA</div>
          <div className="text-sm text-text-muted mt-1">Adaptive Traffic Intelligence</div>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs text-text-secondary block mb-1">Username</label>
            <input
              value={username}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUsername(e.target.value)}
              className="w-full bg-surface-card border border-surface-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-text-secondary block mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
              className="w-full bg-surface-card border border-surface-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>
        </div>

        {error && <div className="text-xs text-status-congested">{error}</div>}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-accent hover:bg-accent-soft transition-colors text-white text-sm font-medium rounded-lg py-2.5 disabled:opacity-60"
        >
          {isSubmitting ? "Signing in..." : "Sign in"}
        </button>

        <div className="text-xs text-text-muted text-center pt-2">
          Default dev credentials: <span className="text-text-secondary">admin / dhaara-admin</span>
        </div>
      </form>
    </div>
  );
}
