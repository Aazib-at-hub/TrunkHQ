"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Navbar } from "../components/Navbar";
import { AppShell } from "../components/layout/AppShell";
import { AuthModal } from "../components/auth/AuthModal";
import { OnboardingModal } from "../components/auth/OnboardingModal";
import { ImportRepoModal } from "../components/repository/ImportRepoModal";
import { RepoCard } from "../components/repository/RepoCard";
import { Button } from "../components/ui/button";
import { Modal } from "../components/ui/modal";
import { useAuthStore } from "../lib/store/auth";
import { repoApi } from "../lib/api/client";
import type { Repository } from "../lib/api/types";
import {
  Plus,
  Search,
  Sparkles,
  ShieldCheck,
  RefreshCw,
  FolderGit2,
  AlertCircle,
  Network,
  ArrowRight,
  Users,
  Check,
  FileText,
  GitBranch,
  Zap,
} from "lucide-react";

export default function Home() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [importModalOpen, setImportModalOpen] = useState(false);

  const openAuth = (mode: "login" | "register" = "login") => {
    setAuthMode(mode);
    setAuthModalOpen(true);
  };
  const [onboardingDismissed, setOnboardingDismissed] = useState(false);

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [reposError, setReposError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<Repository | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const fetchRepos = useCallback(async () => {
    if (!user) {
      setRepositories([]);
      setReposError(null);
      return;
    }
    setLoadingRepos(true);
    setReposError(null);
    try {
      const data = await repoApi.listRepos();
      setRepositories(data);
    } catch (err: unknown) {
      setReposError(err instanceof Error ? err.message : "Failed to load projects.");
    } finally {
      setLoadingRepos(false);
    }
  }, [user]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchRepos();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchRepos]);

  // Poll when repositories are still processing
  useEffect(() => {
    if (!user) return;
    const hasProcessing = repositories.some(
      (r) => r.status !== "READY" && r.status !== "FAILED"
    );
    if (!hasProcessing) return;

    const interval = setInterval(async () => {
      try {
        const data = await repoApi.listRepos();
        setRepositories(data);
      } catch {
        // Ignore transient polling error
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [user, repositories]);

  const handleSelectRepo = (repo: Repository) => {
    router.push(`/projects/${repo.id}`);
  };

  const handleRequestDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const target = repositories.find((r) => r.id === id) ?? null;
    setDeleteError(null);
    setDeleteTarget(target);
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await repoApi.deleteRepo(deleteTarget.id);
      setRepositories((prev) => prev.filter((r) => r.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete project.");
    } finally {
      setDeleting(false);
    }
  };

  const handleImportSuccess = (newRepo: Repository) => {
    setRepositories((prev) => [newRepo, ...prev]);
    router.push(`/projects/${newRepo.id}`);
  };

  const allTags = Array.from(
    new Set(repositories.flatMap((r) => r.tags ?? []))
  ).sort();

  const filteredRepos = repositories.filter((r) => {
    const q = searchQuery.trim().toLowerCase();
    const matchesSearch =
      !q ||
      r.name.toLowerCase().includes(q) ||
      r.github_url.toLowerCase().includes(q) ||
      (r.description?.toLowerCase().includes(q) ?? false) ||
      (r.notes?.toLowerCase().includes(q) ?? false) ||
      (r.tags?.some((t) => t.toLowerCase().includes(q)) ?? false);
    const matchesTag = !selectedTag || (r.tags?.includes(selectedTag) ?? false);
    return matchesSearch && matchesTag;
  });

  const readyCount = repositories.filter((r) => r.status === "READY").length;
  const failedCount = repositories.filter((r) => r.status === "FAILED").length;
  const processingCount = repositories.length - readyCount - failedCount;

  const dashboardContent = (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-6">
      {/* Header toolbar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-border-default pb-5">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-text-primary">
            Project Storage House
          </h2>
          <p className="text-xs text-text-secondary mt-0.5">
            Browse, search, and access project details, codebases, graphs, and AI Q&amp;A across all stored projects
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-text-tertiary" />
            <input
              type="text"
              placeholder="Search projects, tags, notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-border-default bg-bg-secondary pl-9 pr-3 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setImportModalOpen(true)}
            className="gap-1.5 shrink-0"
          >
            <Plus className="h-4 w-4" /> Store Project
          </Button>
        </div>
      </div>

      {/* Real-data Workspace Summary Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded-xl border border-border-default bg-bg-secondary/60 px-4 py-3">
          <p className="text-[11px] text-text-tertiary">Total Projects</p>
          <p className="mt-1 text-lg font-bold font-mono text-text-primary">{repositories.length}</p>
        </div>
        <div className="rounded-xl border border-border-default bg-bg-secondary/60 px-4 py-3">
          <p className="text-[11px] text-text-tertiary">Ready</p>
          <p className="mt-1 text-lg font-bold font-mono text-emerald-400">{readyCount}</p>
        </div>
        <div className="rounded-xl border border-border-default bg-bg-secondary/60 px-4 py-3">
          <p className="text-[11px] text-text-tertiary">Indexing</p>
          <p className="mt-1 text-lg font-bold font-mono text-amber-400">{processingCount}</p>
        </div>
        <div className="rounded-xl border border-border-default bg-bg-secondary/60 px-4 py-3">
          <p className="text-[11px] text-text-tertiary">Failed</p>
          <p className="mt-1 text-lg font-bold font-mono text-rose-400">{failedCount}</p>
        </div>
      </div>

      {allTags.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setSelectedTag(null)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium border transition-colors ${
              selectedTag === null
                ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-300"
                : "border-border-default bg-bg-secondary text-text-secondary hover:text-text-primary"
            }`}
          >
            All ({repositories.length})
          </button>
          {allTags.map((tag) => (
            <button
              key={tag}
              onClick={() => setSelectedTag(selectedTag === tag ? null : tag)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium border transition-colors ${
                selectedTag === tag
                  ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-300"
                  : "border-border-default bg-bg-secondary text-text-secondary hover:text-text-primary"
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {/* Repositories grid */}
      {reposError ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-rose-500/20 bg-rose-500/5 py-12 text-center space-y-3">
          <AlertCircle className="h-7 w-7 text-rose-400" />
          <p className="text-xs text-rose-300">{reposError}</p>
          <Button variant="outline" size="sm" onClick={fetchRepos}>
            Retry
          </Button>
        </div>
      ) : loadingRepos ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <RefreshCw className="h-6 w-6 animate-spin text-emerald-400" />
          <p className="mt-2 text-xs text-text-secondary">Loading projects...</p>
        </div>
      ) : filteredRepos.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredRepos.map((repo) => (
            <RepoCard
              key={repo.id}
              repository={repo}
              currentUserId={user?.id}
              onSelect={handleSelectRepo}
              onDelete={handleRequestDelete}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border-default bg-bg-secondary/40 py-16 text-center">
          <FolderGit2 className="h-10 w-10 text-text-tertiary" />
          <h3 className="mt-3 text-sm font-semibold text-text-primary">
            No projects found
          </h3>
          <p className="mt-1 text-xs text-text-secondary max-w-sm">
            {searchQuery || selectedTag
              ? "No stored projects matched your filter."
              : "No projects have been stored yet. Add one to get started."}
          </p>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setImportModalOpen(true)}
            className="mt-4 gap-1.5"
          >
            <Plus className="h-4 w-4" /> Store First Project
          </Button>
        </div>
      )}
    </div>
  );

  return (
    <>
      {user ? (
        <AppShell repositories={repositories} pageTitle="Projects Workspace">
          {dashboardContent}
        </AppShell>
      ) : (
        <div className="min-h-screen flex flex-col bg-bg-primary text-text-primary">
          <Navbar onOpenAuth={openAuth} />

          <main className="flex-1 flex flex-col">
            <div className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8 space-y-12">
              {/* Split Hero */}
              <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center rounded-2xl border border-border-default bg-bg-secondary/60 p-6 sm:p-10">
                <div className="lg:col-span-7 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>Engineering Intelligence Cloud</span>
                  </div>

                  <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-text-primary leading-[1.12]">
                    Onboard Engineers in{" "}
                    <span className="text-emerald-400">
                      Minutes, Not Weeks
                    </span>
                  </h1>

                  <p className="text-sm sm:text-base text-text-secondary leading-relaxed max-w-xl">
                    TrunkHQ is your team’s central project storage hub. Connect GitHub repositories
                    and technical specs once—give new hires instant, line-cited answers, AST
                    dependency graphs, and blast-radius visibility.
                  </p>

                  <div className="flex flex-wrap items-center gap-3 pt-1">
                    <Link
                      href="/auth?mode=register"
                      className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-6 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 transition"
                    >
                      Get Started — Sign In / Up <ArrowRight className="h-4 w-4" />
                    </Link>
                    <Link
                      href="/pricing"
                      className="inline-flex h-11 items-center justify-center rounded-lg border border-border-default bg-bg-tertiary/60 px-5 text-sm font-medium text-text-primary hover:bg-bg-elevated transition"
                    >
                      View Pricing
                    </Link>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-5 gap-y-2 pt-2 text-xs text-text-secondary">
                    <span className="inline-flex items-center gap-1.5">
                      <Check className="h-3.5 w-3.5 text-emerald-400" /> Free tier · No card required
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Check className="h-3.5 w-3.5 text-emerald-400" /> Exact file &amp; line citations
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Check className="h-3.5 w-3.5 text-emerald-400" /> Org-isolated &amp; BYOK ready
                    </span>
                  </div>
                </div>

                {/* Product Preview Card */}
                <div className="lg:col-span-5 rounded-xl border border-border-default bg-bg-primary/90 p-4 space-y-3 shadow-lg">
                  <div className="flex items-center justify-between border-b border-border-default pb-2.5">
                    <div className="flex items-center gap-2 text-xs font-mono text-text-secondary">
                      <GitBranch className="h-3.5 w-3.5 text-emerald-400" />
                      <span>acme-payments · main</span>
                    </div>
                    <span className="rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
                      READY · 142 files
                    </span>
                  </div>

                  <div className="rounded-lg border border-border-default bg-bg-secondary/70 p-3 space-y-1.5">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                      Developer Question
                    </p>
                    <p className="text-xs text-text-primary">
                      &ldquo;Where is tenant authorization checked before graph reindex?&rdquo;
                    </p>
                  </div>

                  <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-3 space-y-2">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                      TrunkHQ Cited Answer
                    </p>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      Organization membership is verified via{" "}
                      <code className="font-mono text-text-primary">get_tenant_context</code>, and
                      ownership is enforced before re-indexing.
                    </p>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      <span className="rounded border border-border-default bg-bg-secondary px-2 py-0.5 font-mono text-[10px] text-sky-400">
                        api/v1/graph.py:356-364
                      </span>
                      <span className="rounded border border-border-default bg-bg-secondary px-2 py-0.5 font-mono text-[10px] text-emerald-400">
                        Impact: 3 callers
                      </span>
                    </div>
                  </div>
                </div>
              </section>

              {/* How It Works (3 Steps) */}
              <section className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold tracking-tight text-text-primary">
                    From Scattered Repos to Shared Intelligence in 3 Steps
                  </h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="rounded-xl border border-border-default bg-bg-secondary/50 p-5 space-y-2">
                    <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                      <FolderGit2 className="h-4 w-4 text-emerald-400" />
                      1. Store Projects &amp; Docs
                    </div>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      Connect GitHub repos and upload PDF, DOCX, Markdown, OpenAPI, or SQL specs
                      under one tenant-isolated project.
                    </p>
                  </div>
                  <div className="rounded-xl border border-border-default bg-bg-secondary/50 p-5 space-y-2">
                    <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                      <Zap className="h-4 w-4 text-emerald-400" />
                      2. Hybrid Vector + AST Index
                    </div>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      TrunkHQ builds pgvector embeddings, full-text search indexes, and verified AST
                      call/import graphs automatically.
                    </p>
                  </div>
                  <div className="rounded-xl border border-border-default bg-bg-secondary/50 p-5 space-y-2">
                    <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                      <Network className="h-4 w-4 text-emerald-400" />
                      3. Ask, Cite &amp; Trace Impact
                    </div>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      Freshers and engineers get grounded answers with exact line ranges and
                      blast-radius previews before changing code.
                    </p>
                  </div>
                </div>
              </section>

              {/* Built For Segments */}
              <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-xl border border-border-default bg-bg-secondary/40 p-5 space-y-1.5">
                  <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                    <Users className="h-4 w-4 text-emerald-400" />
                    Startups
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    Stop pulling senior devs out of sprints to explain legacy modules to new hires.
                  </p>
                </div>
                <div className="rounded-xl border border-border-default bg-bg-secondary/40 p-5 space-y-1.5">
                  <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                    <FileText className="h-4 w-4 text-emerald-400" />
                    Software Agencies
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    Keep every client codebase, SRS, and architecture map isolated in its own
                    workspace.
                  </p>
                </div>
                <div className="rounded-xl border border-border-default bg-bg-secondary/40 p-5 space-y-1.5">
                  <div className="flex items-center gap-2 text-sm font-semibold text-text-primary">
                    <ShieldCheck className="h-4 w-4 text-emerald-400" />
                    Freelancers &amp; Teams
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    Switch between client projects cleanly with role-based permissions and BYOK
                    control.
                  </p>
                </div>
              </section>

              {/* Conversion Pricing Strip */}
              <section className="rounded-2xl border border-emerald-500/30 bg-bg-secondary/80 p-6 sm:p-8 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
                <div className="space-y-2">
                  <span className="inline-block rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-400">
                    Launch Offer · Up to 50% Off
                  </span>
                  <h2 className="text-xl font-bold text-text-primary">
                    Pro at{" "}
                    <span className="text-text-tertiary line-through font-normal text-base mr-1">
                      ₹999
                    </span>
                    ₹499/mo · Team (4–10) at{" "}
                    <span className="text-text-tertiary line-through font-normal text-base mr-1">
                      ₹7,999
                    </span>
                    ₹4,999/mo
                  </h2>
                  <p className="text-xs text-text-secondary max-w-2xl">
                    Start free with 1 repository, or upgrade your 4–10 person engineering team with
                    shared workspaces, RBAC, and Bring Your Own API Key (BYOK).
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3 shrink-0">
                  <Link
                    href="/auth?mode=register"
                    className="inline-flex h-10 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-5 text-xs font-semibold text-white hover:bg-emerald-500 transition"
                  >
                    Claim Launch Offer <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                  <Link
                    href="/pricing"
                    className="inline-flex h-10 items-center justify-center rounded-lg border border-border-default bg-bg-primary px-4 text-xs font-medium text-text-primary hover:bg-bg-tertiary transition"
                  >
                    Compare Plans
                  </Link>
                </div>
              </section>
            </div>
          </main>

          <footer className="border-t border-border-default bg-bg-secondary/40 py-4 px-4 text-center text-xs text-text-tertiary">
            TrunkHQ · Engineering Intelligence Platform ·{" "}
            <Link href="/pricing" className="text-emerald-400 hover:underline">
              Plans &amp; Pricing
            </Link>
          </footer>
        </div>
      )}

      {/* Modals */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        defaultMode={authMode}
      />

      <OnboardingModal
        isOpen={Boolean(user && user.onboarding_completed === false && !onboardingDismissed)}
        onClose={() => setOnboardingDismissed(true)}
      />

      <ImportRepoModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImportSuccess={handleImportSuccess}
      />

      <Modal
        isOpen={Boolean(deleteTarget)}
        onClose={() => !deleting && setDeleteTarget(null)}
        title="Delete Project"
        description={`Are you sure you want to delete "${deleteTarget?.name ?? ""}" and its vector & graph index?`}
        maxWidth="sm"
      >
        <div className="space-y-4 pt-2">
          {deleteError && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-300">
              {deleteError}
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              isLoading={deleting}
              onClick={handleConfirmDelete}
            >
              Delete Project
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
