"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, FolderGit2, Settings, CreditCard, Activity, X, ArrowRight } from "lucide-react";
import { repoApi } from "../../lib/api/client";
import type { Repository } from "../../lib/api/types";
import { useAuthStore } from "../../lib/store/auth";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  repositories?: Repository[];
}

export function CommandPalette({ isOpen, onClose, repositories }: CommandPaletteProps) {
  const router = useRouter();
  const { user } = useAuthStore();
  const [query, setQuery] = useState("");
  const [fetchedRepos, setFetchedRepos] = useState<Repository[]>([]);

  useEffect(() => {
    if (!isOpen || repositories || !user) return;
    let cancelled = false;
    repoApi
      .listRepos()
      .then((data) => {
        if (!cancelled) setFetchedRepos(data);
      })
      .catch(() => {
        // Ignore fetch errors in quick palette
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, repositories, user]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onClose]);

  const activeRepos = repositories ?? fetchedRepos;

  const navItems = useMemo(() => {
    const base = [
      { label: "Projects Workspace", href: "/", icon: FolderGit2 },
      { label: "Plans & Pricing", href: "/pricing", icon: CreditCard },
      { label: "Account & Workspace Settings", href: "/settings", icon: Settings },
    ];
    if (user?.is_admin) {
      base.push({ label: "System Diagnostics (Admin)", href: "/system", icon: Activity });
    }
    return base;
  }, [user?.is_admin]);

  const q = query.trim().toLowerCase();

  const filteredNav = useMemo(
    () => navItems.filter((item) => !q || item.label.toLowerCase().includes(q)),
    [navItems, q]
  );

  const filteredRepos = useMemo(
    () =>
      activeRepos
        .filter(
          (r) =>
            !q ||
            r.name.toLowerCase().includes(q) ||
            r.github_url.toLowerCase().includes(q) ||
            (r.tags?.some((t) => t.toLowerCase().includes(q)) ?? false)
        )
        .slice(0, 8),
    [activeRepos, q]
  );

  if (!isOpen) return null;

  const navigate = (href: string) => {
    setQuery("");
    onClose();
    router.push(href);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 backdrop-blur-xs pt-20 px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-border-default bg-bg-secondary shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 border-b border-border-default px-3.5 py-2.5">
          <Search className="h-4 w-4 text-text-tertiary shrink-0" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search projects, repositories, or pages..."
            className="w-full bg-transparent text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close command palette"
            className="rounded p-1 text-text-tertiary hover:bg-bg-tertiary hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-80 overflow-y-auto p-2 space-y-3">
          {filteredRepos.length > 0 && (
            <div>
              <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                Projects
              </p>
              <div className="space-y-0.5">
                {filteredRepos.map((repo) => (
                  <button
                    key={repo.id}
                    type="button"
                    onClick={() => navigate(`/projects/${repo.id}`)}
                    className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs text-text-primary hover:bg-bg-tertiary transition"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <FolderGit2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                      <span className="font-medium truncate">{repo.name}</span>
                      <span className="font-mono text-[10px] text-text-tertiary truncate">
                        {repo.branch}
                      </span>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-text-tertiary shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {filteredNav.length > 0 && (
            <div>
              <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                Navigation
              </p>
              <div className="space-y-0.5">
                {filteredNav.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.href}
                      type="button"
                      onClick={() => navigate(item.href)}
                      className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs text-text-primary hover:bg-bg-tertiary transition"
                    >
                      <div className="flex items-center gap-2.5">
                        <Icon className="h-3.5 w-3.5 text-text-secondary" />
                        <span>{item.label}</span>
                      </div>
                      <ArrowRight className="h-3.5 w-3.5 text-text-tertiary" />
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {filteredRepos.length === 0 && filteredNav.length === 0 && (
            <p className="py-6 text-center text-xs text-text-tertiary">
              No matching projects or pages.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
