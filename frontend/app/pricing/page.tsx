"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Navbar } from "../../components/Navbar";
import { AuthModal } from "../../components/auth/AuthModal";
import { Button } from "../../components/ui/button";
import { useAuthStore } from "../../lib/store/auth";
import {
  Check,
  Sparkles,
  Building2,
  Users,
  Rocket,
  KeyRound,
  ArrowRight,
  Layers,
} from "lucide-react";

interface PricingTier {
  name: string;
  badge: string;
  originalPrice?: string;
  price: string;
  period: string;
  discountNote?: string;
  description: string;
  highlighted?: boolean;
  cta: string;
  features: string[];
}

const TIERS: PricingTier[] = [
  {
    name: "Free — Individual",
    badge: "Developer Funnel",
    price: "₹0",
    period: "/month",
    description: "Explore how TrunkHQ turns a repository into instant, cited engineering knowledge.",
    cta: "Start Free",
    features: [
      "1 stored repository",
      "Monthly AI query allowance",
      "Hybrid vector + keyword RAG",
      "Exact file & line citations",
      "Community support",
    ],
  },
  {
    name: "Pro — Individual",
    badge: "Solo & Freelance · 50% OFF",
    originalPrice: "₹999",
    price: "₹499",
    period: "/month",
    discountNote: "Launch offer · Save ₹500/mo",
    description: "For developers and freelancers juggling multiple client or personal codebases.",
    cta: "Get Pro",
    features: [
      "Multiple stored repositories",
      "Higher indexing & chunk limits",
      "Persistent conversation history",
      "AST & dependency graph explorer",
      "Priority indexing queue",
    ],
  },
  {
    name: "Team (4–10 Members)",
    badge: "Recommended · Save ₹3,000/mo",
    originalPrice: "₹7,999",
    price: "₹4,999",
    period: "/month",
    discountNote: "Built for a team of 4–10 engineers",
    highlighted: true,
    description:
      "Central project storage center so startups & agencies onboard 4–10 engineers in minutes, not weeks.",
    cta: "Start Team Pilot",
    features: [
      "4–10 team seats included",
      "Shared team project storage house",
      "Relationship & blast-radius graph",
      "Role-based access controls",
      "Usage dashboard & BYOK support",
    ],
  },
  {
    name: "Enterprise",
    badge: "Custom Annual Contract",
    price: "₹2L–15L+",
    period: "/year (ACV)",
    description:
      "Dedicated cloud SaaS isolation, custom integrations, and security compliance for large orgs.",
    cta: "Request Pilot",
    features: [
      "Dedicated isolated cloud instance",
      "SSO (SAML/OIDC) & audit logs",
      "Custom knowledge graph connectors",
      "BYOK or dedicated AI inference",
      "Dedicated SLA & onboarding support",
    ],
  },
];

export default function PricingPage() {
  const { user } = useAuthStore();
  const [authModalOpen, setAuthModalOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-bg-primary text-text-primary">
      <Navbar onOpenAuth={() => setAuthModalOpen(true)} />

      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 space-y-14">
          {/* Header */}
          <div className="mx-auto max-w-3xl text-center space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Cloud SaaS · Engineering Intelligence as a Service</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-text-primary">
              Stop Walking Freshers Through{" "}
              <span className="text-emerald-400">
                Raw Codebases
              </span>
            </h1>

            <p className="text-sm sm:text-base text-text-secondary leading-relaxed">
              TrunkHQ is a Cloud SaaS project storage center for engineering teams. Store your
              repositories once, and give startups, agencies, and engineering teams instant
              architecture visibility and cited answers.
            </p>
          </div>

          {/* Pricing Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {TIERS.map((tier) => (
              <div
                key={tier.name}
                className={`relative flex flex-col rounded-2xl border p-6 transition ${
                  tier.highlighted
                    ? "border-emerald-500/60 bg-bg-secondary shadow-xl shadow-emerald-500/10"
                    : "border-border-default bg-bg-secondary/70"
                }`}
              >
                <div className="space-y-2">
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider border ${
                      tier.highlighted
                        ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-400"
                        : "border-border-default bg-bg-tertiary text-text-secondary"
                    }`}
                  >
                    {tier.badge}
                  </span>
                  <h2 className="text-lg font-bold text-text-primary">{tier.name}</h2>
                  <div className="pt-1 space-y-0.5">
                    <div className="flex items-baseline gap-2">
                      {tier.originalPrice && (
                        <span className="text-sm font-medium text-text-tertiary line-through">
                          {tier.originalPrice}
                        </span>
                      )}
                      <span className="text-2xl font-extrabold text-text-primary">{tier.price}</span>
                      <span className="text-xs text-text-tertiary">{tier.period}</span>
                    </div>
                    {tier.discountNote && (
                      <p className="text-[11px] font-medium text-emerald-400">
                        {tier.discountNote}
                      </p>
                    )}
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed min-h-[3rem]">
                    {tier.description}
                  </p>
                </div>

                <ul className="mt-5 flex-1 space-y-2.5 border-t border-border-default pt-5">
                  {tier.features.map((feat) => (
                    <li key={feat} className="flex items-start gap-2 text-xs text-text-secondary">
                      <Check className="h-4 w-4 shrink-0 text-emerald-400 mt-0.5" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-6">
                  {user ? (
                    <Link href="/" className="block">
                      <Button
                        variant={tier.highlighted ? "primary" : "outline"}
                        size="sm"
                        className="w-full justify-center gap-1.5"
                      >
                        Open Project Storage <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                    </Link>
                  ) : (
                    <Link href="/auth?mode=register" className="block">
                      <Button
                        variant={tier.highlighted ? "primary" : "outline"}
                        size="sm"
                        className="w-full justify-center gap-1.5"
                      >
                        {tier.cta} <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Pricing Model Principles */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-2xl border border-border-default bg-bg-secondary/60 p-5 space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                <KeyRound className="h-4 w-4 text-emerald-400" />
                Bring Your Own Key (BYOK)
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">
                Team and Enterprise customers can connect their own LLM API keys to control AI
                inference spend while using TrunkHQ’s indexing, RAG, and graph engine.
              </p>
            </div>

            <div className="rounded-2xl border border-border-default bg-bg-secondary/60 p-5 space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                <Layers className="h-4 w-4 text-emerald-400" />
                Hybrid Seat + Usage Fairness
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">
                Every tier includes a generous monthly AI query allowance. Pay extra only when
                repository indexing volume, vector storage, or heavy inference scales up.
              </p>
            </div>

            <div className="rounded-2xl border border-border-default bg-bg-secondary/60 p-5 space-y-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                <Rocket className="h-4 w-4 text-emerald-400" />
                Built for Startups & Agencies
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">
                Start with a controlled team pilot on 1–2 repositories and cut new-hire or
                client-handover onboarding time from days to minutes.
              </p>
            </div>
          </div>

          {/* Target Segments */}
          <div className="rounded-2xl border border-border-default bg-bg-secondary/50 p-6 sm:p-8">
            <h3 className="text-base font-bold text-text-primary mb-4">
              Who Uses TrunkHQ?
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="flex items-start gap-3">
                <Rocket className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-text-primary">Startups</p>
                  <p className="text-xs text-text-secondary mt-0.5">
                    Preserve tribal engineering knowledge and get new hires productive without
                    pulling senior engineers out of sprint work.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Users className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-text-primary">Software Agencies</p>
                  <p className="text-xs text-text-secondary mt-0.5">
                    Centralize multiple client codebases so rotating developers understand
                    architecture and blast radius immediately.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Building2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-text-primary">Enterprise Teams</p>
                  <p className="text-xs text-text-secondary mt-0.5">
                    Scale into isolated cloud deployments with RBAC, SSO, audit logs, and custom
                    architecture knowledge graphs.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-border-default bg-bg-secondary/40 py-5 px-4 text-center text-xs text-text-tertiary">
        TrunkHQ · Cloud SaaS Project Knowledge & Onboarding Hub
      </footer>

      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </div>
  );
}

