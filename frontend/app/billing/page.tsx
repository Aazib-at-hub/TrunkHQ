"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/layout/AppShell";
import { Navbar } from "../../components/Navbar";
import { AuthModal } from "../../components/auth/AuthModal";
import { Button } from "../../components/ui/button";
import { billingApi } from "../../lib/api/client";
import type { SubscriptionDetail } from "../../lib/api/types";
import { useAuthStore } from "../../lib/store/auth";
import { CreditCard, RefreshCw, AlertCircle, ArrowRight } from "lucide-react";

export default function BillingPage() {
  const { user } = useAuthStore();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [sub, setSub] = useState<SubscriptionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadBilling = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await billingApi.getSubscription();
      setSub(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load subscription details.");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadBilling();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadBilling]);

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col bg-bg-primary text-text-primary">
        <Navbar onOpenAuth={() => setAuthModalOpen(true)} />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md w-full rounded-2xl border border-border-default bg-bg-secondary p-8 text-center space-y-4">
            <CreditCard className="h-9 w-9 text-emerald-400 mx-auto" />
            <h1 className="text-lg font-bold text-text-primary">Sign In Required</h1>
            <p className="text-xs text-text-secondary">
              Sign in to view your organization subscription and monthly AI usage.
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

  const aiUsed = sub?.usage?.ai_queries ?? 0;
  const aiLimit = sub?.plan?.limits?.max_ai_queries_per_month ?? 50;

  return (
    <AppShell pageTitle="Usage & Billing">
      <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 space-y-6">
        <div className="flex items-center justify-between gap-4 border-b border-border-default pb-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-text-primary">
              Usage &amp; Billing
            </h1>
            <p className="text-xs text-text-secondary mt-0.5">
              Active organization plan entitlements and current-month metered usage.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void loadBilling()} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {errorMsg && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {sub && (
          <div className="space-y-4">
            <section className="rounded-xl border border-border-default bg-bg-secondary/70 p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1">
                <span className="inline-block rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase text-emerald-400">
                  {sub.status} · {sub.billing_cycle}
                </span>
                <h2 className="text-lg font-bold text-text-primary">{sub.plan.name}</h2>
                <p className="text-xs text-text-secondary">
                  ₹{sub.plan.monthly_price_inr.toLocaleString()} / month
                </p>
              </div>
              <Link href="/pricing">
                <Button variant="primary" size="sm" className="gap-1.5">
                  Compare Plans <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </section>

            <section className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="rounded-xl border border-border-default bg-bg-secondary/60 p-4">
                <p className="text-xs text-text-tertiary">AI Queries (This Month)</p>
                <p className="mt-1 text-xl font-bold font-mono text-text-primary">
                  {aiUsed} / {aiLimit < 0 ? "Unlimited" : aiLimit}
                </p>
              </div>
              <div className="rounded-xl border border-border-default bg-bg-secondary/60 p-4">
                <p className="text-xs text-text-tertiary">Repository Limit</p>
                <p className="mt-1 text-xl font-bold font-mono text-text-primary">
                  {(sub.plan.limits.max_repos ?? 1) < 0 ? "Unlimited" : sub.plan.limits.max_repos}
                </p>
              </div>
              <div className="rounded-xl border border-border-default bg-bg-secondary/60 p-4">
                <p className="text-xs text-text-tertiary">BYOK Support</p>
                <p className="mt-1 text-xl font-bold font-mono text-text-primary">
                  {sub.plan.features.byok_enabled ? "Enabled" : "Team+"}
                </p>
              </div>
            </section>
          </div>
        )}
      </div>
    </AppShell>
  );
}
