"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, LogIn, LogOut, Moon, Sun } from "lucide-react";
import { useAuthStore } from "../lib/store/auth";
import { useThemeStore } from "../lib/store/theme";
import { healthApi } from "../lib/api/client";
import type { HealthResponse } from "../lib/api/types";

interface NavbarProps {
  onOpenAuth: (mode?: "login" | "register") => void;
  onOpenImport?: () => void;
}

export function Navbar({ onOpenAuth }: NavbarProps) {
  const { user, logout, initialize } = useAuthStore();
  const { theme, initTheme, toggleTheme } = useThemeStore();
  const [rawHealth, setHealth] = useState<HealthResponse | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(false);

  const isAdmin = Boolean(user?.is_admin);
  const health = isAdmin ? rawHealth : null;

  const checkHealth = async () => {
    if (!isAdmin) return;
    setIsHealthLoading(true);
    try {
      const data = await healthApi.checkHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setIsHealthLoading(false);
    }
  };

  useEffect(() => {
    initialize();
    initTheme();
  }, [initialize, initTheme]);

  useEffect(() => {
    let ignore = false;
    if (!isAdmin) {
      return;
    }
    healthApi
      .checkHealth()
      .then((data) => {
        if (!ignore) setHealth(data);
      })
      .catch(() => {
        if (!ignore) setHealth(null);
      });

    return () => {
      ignore = true;
    };
  }, [isAdmin]);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border-default bg-bg-secondary/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border-default bg-white p-1.5 shadow-xs">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/trunkhq-icon.png" alt="TrunkHQ" className="h-full w-full object-contain" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-lg font-bold tracking-tight text-text-primary">
                Trunk<span className="text-emerald-400">HQ</span>
              </span>
            </div>
            <p className="text-xs text-text-tertiary">Engineering Intelligence</p>
          </div>
        </Link>

        {/* Status & Actions */}
        <div className="flex items-center gap-3">
          <Link
            href="/pricing"
            className="rounded-full border border-border-default bg-bg-tertiary px-3 py-1.5 text-xs font-medium text-text-secondary transition hover:border-text-tertiary hover:text-text-primary"
          >
            Pricing
          </Link>

          {/* Day / Night Mode Toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to Day Mode" : "Switch to Night Mode"}
            aria-label={theme === "dark" ? "Switch to Day Mode" : "Switch to Night Mode"}
            className="flex cursor-pointer items-center gap-1.5 rounded-full border border-border-default bg-bg-tertiary px-2.5 py-1.5 text-xs font-medium text-text-secondary transition hover:border-text-tertiary hover:text-text-primary"
          >
            {theme === "dark" ? (
              <Sun className="h-3.5 w-3.5 text-amber-400" />
            ) : (
              <Moon className="h-3.5 w-3.5 text-emerald-500" />
            )}
            <span className="hidden sm:inline">{theme === "dark" ? "Day" : "Night"}</span>
          </button>

          {isAdmin && (
            <>
              <Link
                href="/system"
                title="System Intelligence & Indexing Diagnostics"
                className="flex items-center gap-1.5 rounded-full border border-border-default bg-bg-tertiary px-2.5 py-1.5 text-xs font-medium text-text-secondary transition hover:border-text-tertiary hover:text-text-primary"
              >
                <Activity className="h-3.5 w-3.5 text-emerald-400" />
                <span className="hidden sm:inline">System</span>
              </Link>

              {/* Subtle Health Dot (admin-only) */}
              <button
                type="button"
                onClick={checkHealth}
                title={health ? `Backend: ${health.status} (${health.database})` : "Backend offline — click to recheck"}
                className="flex cursor-pointer items-center gap-1.5 rounded-full border border-border-default bg-bg-tertiary px-2.5 py-1.5 text-xs text-text-secondary transition hover:border-text-tertiary"
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    health?.status === "healthy"
                      ? "bg-emerald-400"
                      : health?.status === "degraded"
                      ? "bg-amber-400 animate-pulse"
                      : "bg-red-400"
                  }`}
                />
                {health?.status !== "healthy" && (
                  <span className="hidden sm:inline font-mono">
                    {health?.status === "degraded" ? `DB ${health.database}` : isHealthLoading ? "Checking..." : "Offline"}
                  </span>
                )}
              </button>
            </>
          )}

          {/* Auth Button */}
          {user ? (
            <div className="flex items-center gap-3 pl-2 border-l border-border-default">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-bg-surface text-text-primary border border-border-default text-xs font-semibold">
                  {user.username.charAt(0).toUpperCase()}
                </div>
                <div className="hidden md:block text-left">
                  <p className="text-xs font-medium text-text-primary leading-none">{user.username}</p>
                  <p className="text-[10px] text-text-tertiary">{user.email}</p>
                </div>
              </div>
              <button
                onClick={() => logout()}
                title="Sign out"
                className="rounded-lg p-1.5 text-text-tertiary hover:bg-bg-tertiary hover:text-text-primary transition"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <Link
              href="/auth?mode=login"
              className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 transition"
            >
              <LogIn className="h-3.5 w-3.5" />
              <span>Sign In / Up</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
