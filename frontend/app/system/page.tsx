"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Cpu,
  Database,
  ExternalLink,
  GitBranch,
  Layers,
  Loader2,
  RefreshCw,
  Server,
} from "lucide-react";
import { Navbar } from "../../components/Navbar";
import { AppShell } from "../../components/layout/AppShell";
import { AuthModal } from "../../components/auth/AuthModal";
import { Button } from "../../components/ui/button";
import { healthApi, repoApi } from "../../lib/api/client";
import { graphApi } from "../../lib/api/graph";
import { useAuthStore } from "../../lib/store/auth";
import type { HealthResponse, Repository } from "../../lib/api/types";
import type { GraphStatusResponse } from "../../types/graph";

interface RepoDiagnostic {
  repo: Repository;
  graphStatus: GraphStatusResponse | null;
}

function StatusBadge({ status }: { status: string }) {
  const upper = status.toUpperCase();
  const styles =
    upper === "READY" || upper === "HEALTHY"
      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
      : upper === "FAILED" || upper === "UNHEALTHY"
      ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
      : upper === "NOT_INDEXED"
      ? "bg-bg-tertiary text-text-tertiary border-border-default"
      : "bg-amber-500/10 text-amber-300 border-amber-500/30";

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-mono border ${styles}`}>
      {status}
    </span>
  );
}

export default function SystemIntelligencePage() {
  const { user } = useAuthStore();
  const [authModalOpen, setAuthModalOpen] = useState(false);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [diagnostics, setDiagnostics] = useState<RepoDiagnostic[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadDiagnostics = useCallback(async () => {
    if (!user || !user.is_admin) {
      setHealth(null);
      setDiagnostics([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setHealthError(null);

    try {
      const h = await healthApi.checkHealth();
      setHealth(h);
    } catch (err: unknown) {
      setHealth(null);
      setHealthError(err instanceof Error ? err.message : "Backend health check failed.");
    }

    try {
      const repos = await repoApi.listRepos();
      const statusResults = await Promise.allSettled(
        repos.map((r) => graphApi.getStatus(r.id))
      );
      const rows: RepoDiagnostic[] = repos.map((repo, idx) => {
        const res = statusResults[idx];
        return {
          repo,
          graphStatus: res.status === "fulfilled" ? res.value : null,
        };
      });
      setDiagnostics(rows);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load repository diagnostics.");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadDiagnostics();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadDiagnostics]);

  const mainBody = (
    <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 rounded-lg border border-border-default bg-bg-secondary px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Command Center</span>
            </Link>
            <div>
              <h1 className="text-xl font-bold text-text-primary flex items-center gap-2">
                <Activity className="w-5 h-5 text-emerald-400" />
                <span>System Intelligence</span>
              </h1>
              <p className="text-xs text-text-tertiary">
                Backend health, provider configuration, and repository/graph indexing diagnostics.
              </p>
            </div>
          </div>

          <Button variant="secondary" onClick={loadDiagnostics} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {!user ? (
          <div className="rounded-xl border border-border-default bg-bg-secondary p-8 text-center space-y-3">
            <p className="text-sm font-medium text-text-primary">Admin Sign-In Required</p>
            <p className="text-xs text-text-secondary">
              System health and indexing diagnostics are restricted to administrators.
            </p>
            <Button onClick={() => setAuthModalOpen(true)}>Sign In</Button>
          </div>
        ) : !user.is_admin ? (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-8 text-center space-y-3">
            <p className="text-sm font-semibold text-rose-300">Admin Access Required</p>
            <p className="text-xs text-text-secondary">
              Your account ({user.email}) does not have administrator privileges to view system diagnostics.
            </p>
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 rounded-lg border border-border-default bg-bg-secondary px-3 py-1.5 text-xs text-text-primary hover:bg-bg-tertiary transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Return to Command Center</span>
            </Link>
          </div>
        ) : (
          <>
            {/* Backend Health Diagnostics */}
            <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Backend Health & Providers
          </h2>

          {healthError ? (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{healthError}</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              <div className="rounded-xl border border-border-default bg-bg-secondary p-4 space-y-1.5">
                <div className="flex items-center justify-between text-xs text-text-tertiary">
                  <span>API Status</span>
                  <Server className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <StatusBadge status={health?.status || "checking"} />
                </div>
              </div>

              <div className="rounded-xl border border-border-default bg-bg-secondary p-4 space-y-1.5">
                <div className="flex items-center justify-between text-xs text-text-tertiary">
                  <span>PostgreSQL / pgvector</span>
                  <Database className="w-4 h-4 text-emerald-400" />
                </div>
                <div>
                  <StatusBadge status={health?.database || "unknown"} />
                </div>
              </div>

              <div className="rounded-xl border border-border-default bg-bg-secondary p-4 space-y-1">
                <div className="flex items-center justify-between text-xs text-text-tertiary">
                  <span>Embedding Provider</span>
                  <Layers className="w-4 h-4 text-sky-400" />
                </div>
                <p className="text-sm font-mono font-semibold text-text-primary">
                  {health?.embedding_provider || "—"}
                </p>
              </div>

              <div className="rounded-xl border border-border-default bg-bg-secondary p-4 space-y-1">
                <div className="flex items-center justify-between text-xs text-text-tertiary">
                  <span>LLM Provider</span>
                  <Cpu className="w-4 h-4 text-sky-400" />
                </div>
                <p className="text-sm font-mono font-semibold text-text-primary">
                  {health?.llm_provider || "—"}
                </p>
              </div>

              <div className="rounded-xl border border-border-default bg-bg-secondary p-4 space-y-1">
                <div className="flex items-center justify-between text-xs text-text-tertiary">
                  <span>Version</span>
                  <CheckCircle2 className="w-4 h-4 text-text-tertiary" />
                </div>
                <p className="text-sm font-mono font-semibold text-text-primary">
                  {health?.version || "—"}
                </p>
              </div>
            </div>
          )}
        </section>

        {/* Repository & Graph Indexing Diagnostics */}
        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">
            Repository & GraphIndexRun Metrics
          </h2>

          {!user ? (
            <div className="rounded-xl border border-border-default bg-bg-secondary p-6 text-center space-y-3">
              <p className="text-xs text-text-secondary">
                Sign in to inspect workspace repository indexing status and graph run metrics.
              </p>
              <Button onClick={() => setAuthModalOpen(true)}>Sign In</Button>
            </div>
          ) : errorMsg ? (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300">
              {errorMsg}
            </div>
          ) : loading && diagnostics.length === 0 ? (
            <div className="rounded-xl border border-border-default bg-bg-secondary p-10 flex items-center justify-center gap-2 text-xs text-text-tertiary">
              <Loader2 className="w-4 h-4 animate-spin text-accent" />
              <span>Loading repository diagnostics...</span>
            </div>
          ) : diagnostics.length === 0 ? (
            <div className="rounded-xl border border-border-default bg-bg-secondary p-8 text-center text-xs text-text-tertiary">
              No repositories indexed in this workspace yet.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-border-default bg-bg-secondary">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-border-default bg-bg-tertiary text-[11px] font-mono uppercase text-text-tertiary">
                  <tr>
                    <th className="px-4 py-3">Repository</th>
                    <th className="px-4 py-3">Repo Status</th>
                    <th className="px-4 py-3">Files / Chunks</th>
                    <th className="px-4 py-3">Graph Status</th>
                    <th className="px-4 py-3">Nodes Created</th>
                    <th className="px-4 py-3">Edges Created</th>
                    <th className="px-4 py-3">Extractor</th>
                    <th className="px-4 py-3">Completed At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {diagnostics.map(({ repo, graphStatus }) => {
                    const nodesCreated = graphStatus?.nodes_created ?? graphStatus?.nodes_count ?? 0;
                    const edgesCreated = graphStatus?.edges_created ?? graphStatus?.edges_count ?? 0;
                    const completedAt = graphStatus?.completed_at
                      ? new Date(graphStatus.completed_at).toLocaleString()
                      : "—";

                    return (
                      <tr key={repo.id} className="hover:bg-bg-tertiary/50 transition-colors">
                        <td className="px-4 py-3">
                          <Link
                            href={`/projects/${repo.id}`}
                            className="font-medium text-text-primary hover:text-accent inline-flex items-center gap-1"
                          >
                            <span>{repo.name}</span>
                            <ExternalLink className="w-3 h-3 text-text-tertiary" />
                          </Link>
                          <div className="text-[11px] font-mono text-text-tertiary flex items-center gap-1 mt-0.5">
                            <GitBranch className="w-3 h-3" />
                            <span>{repo.branch || "main"}</span>
                          </div>
                          {(repo.error_message || graphStatus?.error_summary) && (
                            <p className="text-[11px] text-rose-400 mt-1 max-w-xs truncate" title={repo.error_message || graphStatus?.error_summary || ""}>
                              {repo.error_message || graphStatus?.error_summary}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={repo.status} />
                        </td>
                        <td className="px-4 py-3 font-mono text-text-secondary">
                          {repo.file_count} / {repo.chunk_count}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={graphStatus?.status || "UNKNOWN"} />
                        </td>
                        <td className="px-4 py-3 font-mono text-text-primary">{nodesCreated}</td>
                        <td className="px-4 py-3 font-mono text-text-primary">{edgesCreated}</td>
                        <td className="px-4 py-3 font-mono text-text-secondary">
                          {graphStatus?.extractor_version || "—"}
                        </td>
                        <td className="px-4 py-3 font-mono text-text-tertiary whitespace-nowrap">
                          {completedAt}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
          </>
        )}
    </div>
  );

  return (
    <>
      {user ? (
        <AppShell pageTitle="System Intelligence">{mainBody}</AppShell>
      ) : (
        <div className="min-h-screen flex flex-col bg-bg-primary text-text-primary">
          <Navbar onOpenAuth={() => setAuthModalOpen(true)} />
          <main className="flex-1 flex flex-col">{mainBody}</main>
        </div>
      )}

      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </>
  );
}
