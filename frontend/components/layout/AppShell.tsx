"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Building2,
  ChevronDown,
  CreditCard,
  FolderGit2,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  Sun,
  Users,
  X,
} from "lucide-react";
import { healthApi } from "../../lib/api/client";
import type { HealthResponse, Repository } from "../../lib/api/types";
import { useAuthStore } from "../../lib/store/auth";
import { useOrgStore } from "../../lib/store/org";
import { useThemeStore } from "../../lib/store/theme";
import { CommandPalette } from "./CommandPalette";

interface AppShellProps {
  children: React.ReactNode;
  repositories?: Repository[];
  pageTitle?: string;
}

export function AppShell({ children, repositories, pageTitle }: AppShellProps) {
  const pathname = usePathname();
  const { user, logout, initialize } = useAuthStore();
  const { organizations, activeOrgId, loadOrgs, setActiveOrg, createOrg, clearOrgs } = useOrgStore();
  const { theme, initTheme, toggleTheme } = useThemeStore();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [creatingOrg, setCreatingOrg] = useState(false);
  const [rawHealth, setHealth] = useState<HealthResponse | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(false);

  const isAdmin = Boolean(user?.is_admin);
  const health = isAdmin ? rawHealth : null;

  useEffect(() => {
    initialize();
    initTheme();
  }, [initialize, initTheme]);

  useEffect(() => {
    if (!user) return;
    const timer = setTimeout(() => {
      void loadOrgs();
    }, 0);
    return () => clearTimeout(timer);
  }, [user, loadOrgs]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    let ignore = false;
    if (!isAdmin) return;
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

  const navItems = [
    { label: "Projects", href: "/", icon: FolderGit2, active: pathname === "/" || pathname.startsWith("/projects") },
    { label: "Team", href: "/team", icon: Users, active: pathname === "/team" },
    { label: "Billing", href: "/billing", icon: CreditCard, active: pathname === "/billing" },
    { label: "Pricing", href: "/pricing", icon: CreditCard, active: pathname === "/pricing" },
    { label: "Settings", href: "/settings", icon: Settings, active: pathname === "/settings" },
    ...(isAdmin
      ? [{ label: "System", href: "/system", icon: Activity, active: pathname === "/system" }]
      : []),
  ];

  const activeOrg = organizations.find((o) => o.id === activeOrgId) ?? organizations[0];
  const workspaceLabel = activeOrg?.name ?? (user ? `${user.username}'s Workspace` : "Personal Workspace");
  const workspaceSub = activeOrg ? `${activeOrg.account_type} · ${activeOrg.role}` : "Tenant Workspace";

  const handleSelectOrg = (orgId: string) => {
    setActiveOrg(orgId);
    setWorkspaceMenuOpen(false);
    window.location.reload();
  };

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newOrgName.trim();
    if (trimmed.length < 2) return;
    setCreatingOrg(true);
    try {
      await createOrg(trimmed, user?.account_type ?? "startup");
      setNewOrgName("");
      setWorkspaceMenuOpen(false);
      window.location.reload();
    } finally {
      setCreatingOrg(false);
    }
  };

  const sidebarContent = (
    <div className="flex h-full flex-col justify-between">
      <div className="space-y-4">
        {/* Brand */}
        <div className="flex h-14 items-center justify-between border-b border-border-default px-3">
          <Link href="/" className="flex items-center gap-2.5 min-w-0">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border-default bg-white p-1">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/trunkhq-icon.png" alt="TrunkHQ" className="h-full w-full object-contain" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-bold tracking-tight text-text-primary truncate">
                    Trunk<span className="text-emerald-400">HQ</span>
                  </span>
                </div>
                <p className="text-[10px] text-text-tertiary truncate">Engineering Intelligence</p>
              </div>
            )}
          </Link>
          <button
            type="button"
            onClick={() => setCollapsed((prev) => !prev)}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden lg:flex rounded-md p-1 text-text-tertiary hover:bg-bg-tertiary hover:text-text-primary transition"
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            className="lg:hidden rounded-md p-1 text-text-tertiary hover:bg-bg-tertiary hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Workspace Switcher */}
        {!collapsed && (
          <div className="px-3 relative">
            <button
              type="button"
              onClick={() => setWorkspaceMenuOpen((prev) => !prev)}
              className="flex w-full items-center justify-between rounded-lg border border-border-default bg-bg-tertiary/60 px-2.5 py-2 text-left text-xs hover:border-text-tertiary transition"
            >
              <div className="flex items-center gap-2 min-w-0">
                <Building2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium text-text-primary truncate">{workspaceLabel}</p>
                  <p className="text-[10px] text-text-tertiary capitalize">{workspaceSub}</p>
                </div>
              </div>
              <ChevronDown className="h-3.5 w-3.5 text-text-tertiary shrink-0" />
            </button>

            {workspaceMenuOpen && (
              <div className="absolute left-3 right-3 top-full mt-1 z-30 rounded-lg border border-border-default bg-bg-elevated p-2 shadow-lg text-xs space-y-2">
                <p className="px-2 pt-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                  Organizations
                </p>
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {organizations.map((org) => (
                    <button
                      key={org.id}
                      type="button"
                      onClick={() => handleSelectOrg(org.id)}
                      className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left transition ${
                        org.id === activeOrg?.id
                          ? "bg-emerald-500/15 text-emerald-400 font-medium"
                          : "text-text-primary hover:bg-bg-tertiary"
                      }`}
                    >
                      <span className="truncate">{org.name}</span>
                      <span className="text-[10px] text-text-tertiary uppercase ml-2">{org.role}</span>
                    </button>
                  ))}
                </div>
                <form onSubmit={handleCreateOrg} className="border-t border-border-default pt-2 space-y-1.5">
                  <input
                    type="text"
                    value={newOrgName}
                    onChange={(e) => setNewOrgName(e.target.value)}
                    placeholder="New workspace name..."
                    className="w-full rounded-md border border-border-default bg-bg-primary px-2 py-1 text-xs text-text-primary placeholder:text-text-tertiary focus:border-emerald-500 focus:outline-none"
                  />
                  <button
                    type="submit"
                    disabled={creatingOrg || newOrgName.trim().length < 2}
                    className="w-full rounded-md bg-emerald-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
                  >
                    {creatingOrg ? "Creating..." : "+ Create Organization"}
                  </button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <nav className="px-2 space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                title={collapsed ? item.label : undefined}
                className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs font-medium transition ${
                  item.active
                    ? "bg-emerald-500/12 text-emerald-400 border border-emerald-500/20"
                    : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary border border-transparent"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* User Footer */}
      {user && (
        <div className="border-t border-border-default p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border-default bg-bg-surface text-xs font-semibold text-text-primary">
                {user.username.charAt(0).toUpperCase()}
              </div>
              {!collapsed && (
                <div className="min-w-0">
                  <p className="text-xs font-medium text-text-primary truncate">{user.username}</p>
                  <p className="text-[10px] text-text-tertiary truncate">{user.email}</p>
                </div>
              )}
            </div>
            {!collapsed && (
              <button
                type="button"
                onClick={() => {
                  clearOrgs();
                  logout();
                }}
                title="Sign out"
                className="rounded-md p-1.5 text-text-tertiary hover:bg-bg-tertiary hover:text-text-primary transition shrink-0"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen flex bg-bg-primary text-text-primary">
      {/* Desktop Sidebar */}
      <aside
        className={`hidden lg:flex flex-col shrink-0 border-r border-border-default bg-bg-secondary/70 transition-all duration-150 ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Sidebar Drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 flex lg:hidden bg-black/60"
          onClick={() => setMobileOpen(false)}
        >
          <aside
            className="w-64 bg-bg-secondary border-r border-border-default h-full"
            onClick={(e) => e.stopPropagation()}
          >
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main Column */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border-default bg-bg-secondary/80 backdrop-blur-md px-4 sm:px-6">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              className="lg:hidden rounded-md p-1.5 text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
            >
              <Menu className="h-4 w-4" />
            </button>
            {pageTitle && (
              <span className="text-sm font-semibold text-text-primary truncate">
                {pageTitle}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2.5">
            {/* Global Search / Command Trigger */}
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="flex items-center gap-2 rounded-lg border border-border-default bg-bg-tertiary/70 px-3 py-1.5 text-xs text-text-secondary hover:border-text-tertiary hover:text-text-primary transition"
            >
              <Search className="h-3.5 w-3.5 text-text-tertiary" />
              <span className="hidden sm:inline">Quick search...</span>
              <kbd className="hidden md:inline rounded border border-border-default bg-bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary">
                Ctrl K
              </kbd>
            </button>

            {/* Day / Night Mode */}
            <button
              type="button"
              onClick={toggleTheme}
              title={theme === "dark" ? "Switch to Day Mode" : "Switch to Night Mode"}
              aria-label={theme === "dark" ? "Switch to Day Mode" : "Switch to Night Mode"}
              className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-border-default bg-bg-tertiary/70 px-2.5 py-1.5 text-xs font-medium text-text-secondary transition hover:border-text-tertiary hover:text-text-primary"
            >
              {theme === "dark" ? (
                <Sun className="h-3.5 w-3.5 text-amber-400" />
              ) : (
                <Moon className="h-3.5 w-3.5 text-emerald-500" />
              )}
              <span className="hidden sm:inline">{theme === "dark" ? "Day" : "Night"}</span>
            </button>

            {/* Admin-only Health Indicator */}
            {isAdmin && (
              <button
                type="button"
                onClick={checkHealth}
                title={health ? `Backend: ${health.status} (${health.database})` : "Backend offline — click to recheck"}
                className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-border-default bg-bg-tertiary/70 px-2.5 py-1.5 text-xs text-text-secondary transition hover:border-text-tertiary"
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
            )}
          </div>
        </header>

        <main className="flex-1 flex flex-col min-w-0">{children}</main>
      </div>

      <CommandPalette
        isOpen={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        repositories={repositories}
      />
    </div>
  );
}
