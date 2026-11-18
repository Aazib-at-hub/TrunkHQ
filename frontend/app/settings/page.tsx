"use client";

import React, { useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/layout/AppShell";
import { Navbar } from "../../components/Navbar";
import { AuthModal } from "../../components/auth/AuthModal";
import { Button } from "../../components/ui/button";
import { useAuthStore } from "../../lib/store/auth";
import { useThemeStore } from "../../lib/store/theme";
import { Building2, CreditCard, Moon, Shield, Sun, User as UserIcon } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuthStore();
  const { theme, setTheme } = useThemeStore();
  const [authModalOpen, setAuthModalOpen] = useState(false);

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col bg-bg-primary text-text-primary">
        <Navbar onOpenAuth={() => setAuthModalOpen(true)} />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md w-full rounded-2xl border border-border-default bg-bg-secondary p-8 text-center space-y-4">
            <UserIcon className="h-9 w-9 text-emerald-400 mx-auto" />
            <h1 className="text-lg font-bold text-text-primary">Sign In Required</h1>
            <p className="text-xs text-text-secondary">
              Sign in to view your profile, workspace preferences, and theme settings.
            </p>
            <Button variant="primary" size="md" onClick={() => setAuthModalOpen(true)}>
              Sign In
            </Button>
          </div>
        </main>
        <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      </div>
    );
  }

  return (
    <AppShell pageTitle="Account & Workspace Settings">
      <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 space-y-6">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary">Settings</h1>
          <p className="text-xs text-text-secondary mt-0.5">
            Manage your account profile, interface theme, and workspace overview.
          </p>
        </div>

        {/* Profile */}
        <section className="rounded-xl border border-border-default bg-bg-secondary/70 p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <UserIcon className="h-4 w-4 text-emerald-400" />
            Profile
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="rounded-lg border border-border-default bg-bg-primary/60 p-3">
              <p className="text-text-tertiary">Username</p>
              <p className="mt-1 font-medium text-text-primary">{user.username}</p>
            </div>
            <div className="rounded-lg border border-border-default bg-bg-primary/60 p-3">
              <p className="text-text-tertiary">Email</p>
              <p className="mt-1 font-medium text-text-primary">{user.email}</p>
            </div>
            <div className="rounded-lg border border-border-default bg-bg-primary/60 p-3">
              <p className="text-text-tertiary">Access Level</p>
              <p className="mt-1 font-medium text-text-primary flex items-center gap-1.5">
                <Shield className="h-3.5 w-3.5 text-emerald-400" />
                {user.is_admin ? "System Administrator" : "Workspace Member"}
              </p>
            </div>
            <div className="rounded-lg border border-border-default bg-bg-primary/60 p-3">
              <p className="text-text-tertiary">Member Since</p>
              <p className="mt-1 font-mono text-text-primary">
                {new Date(user.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        </section>

        {/* Appearance */}
        <section className="rounded-xl border border-border-default bg-bg-secondary/70 p-5 space-y-3">
          <div className="text-sm font-semibold text-text-primary">Appearance</div>
          <p className="text-xs text-text-secondary">
            Choose between Day (light) and Night (dark) interface modes.
          </p>
          <div className="flex items-center gap-3 pt-1">
            <button
              type="button"
              onClick={() => setTheme("light")}
              className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-xs font-medium transition ${
                theme === "light"
                  ? "border-emerald-500/60 bg-emerald-500/15 text-emerald-400"
                  : "border-border-default bg-bg-primary/60 text-text-secondary hover:text-text-primary"
              }`}
            >
              <Sun className="h-3.5 w-3.5" />
              Day Mode
            </button>
            <button
              type="button"
              onClick={() => setTheme("dark")}
              className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-xs font-medium transition ${
                theme === "dark"
                  ? "border-emerald-500/60 bg-emerald-500/15 text-emerald-400"
                  : "border-border-default bg-bg-primary/60 text-text-secondary hover:text-text-primary"
              }`}
            >
              <Moon className="h-3.5 w-3.5" />
              Night Mode
            </button>
          </div>
        </section>

        {/* Workspace & Plan */}
        <section className="rounded-xl border border-border-default bg-bg-secondary/70 p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
              <Building2 className="h-4 w-4 text-emerald-400" />
              Workspace & Subscription
            </div>
            <p className="text-xs text-text-secondary">
              Currently operating in shared Project Storage House mode. Multi-organization
              isolation, team invites, and BYOK key management arrive in upcoming phases.
            </p>
          </div>
          <Link href="/pricing" className="shrink-0">
            <Button variant="outline" size="sm" className="gap-1.5">
              <CreditCard className="h-3.5 w-3.5" />
              View Plans
            </Button>
          </Link>
        </section>
      </div>
    </AppShell>
  );
}
