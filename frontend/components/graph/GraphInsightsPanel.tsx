"use client";

import React, { useEffect, useState } from "react";
import type { GraphInsightsResponse, GraphNode } from "../../types/graph";
import { graphApi } from "../../lib/api/graph";
import {
  Sparkles,
  X,
  ArrowUpRight,
  ArrowDownLeft,
  Globe,
  FolderTree,
  Loader2,
  AlertCircle,
  TrendingUp,
} from "lucide-react";

interface GraphInsightsPanelProps {
  repoId: string;
  onClose: () => void;
  onSelectNode: (node: GraphNode) => void;
  onAskCortex?: (prompt: string) => void;
}

export function GraphInsightsPanel({
  repoId,
  onClose,
  onSelectNode,
  onAskCortex,
}: GraphInsightsPanelProps) {
  const [insights, setInsights] = useState<GraphInsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    graphApi
      .getInsights(repoId, 12)
      .then((data) => {
        if (!cancelled) setInsights(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Failed to load architectural insights";
          setError(msg);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [repoId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-4xl bg-bg-secondary border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[88vh]">
        {/* Header */}
        <div className="p-5 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-emerald-950/40 via-sky-950/20 to-transparent">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-accent/15 text-accent border border-accent/30 shadow-inner">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
                Architectural & Knowledge Insights
              </h2>
              <p className="text-xs text-text-tertiary">
                High-centrality hubs, primary entrypoints, and structural hotspots across this codebase
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-tertiary hover:text-text-primary hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center gap-3 text-text-tertiary">
              <Loader2 className="w-8 h-8 animate-spin text-accent" />
              <p className="text-xs">Analyzing system topology and centrality metrics...</p>
            </div>
          ) : error || !insights ? (
            <div className="py-12 flex flex-col items-center justify-center gap-2 text-center">
              <AlertCircle className="w-8 h-8 text-red-400" />
              <p className="text-sm text-text-primary">Failed to load insights</p>
              <p className="text-xs text-text-tertiary max-w-sm">{error}</p>
            </div>
          ) : (
            <>
              {/* Domain Stats Row */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div className="p-4 rounded-xl bg-bg-tertiary border border-white/5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
                    Total Entities
                  </span>
                  <div className="text-2xl font-bold text-text-primary mt-1">
                    {insights.total_nodes}
                  </div>
                  <span className="text-[11px] text-text-secondary">
                    {insights.total_edges} verified relationships
                  </span>
                </div>

                <div className="p-4 rounded-xl bg-bg-tertiary border border-sky-500/20">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-sky-400">
                    Code Symbols
                  </span>
                  <div className="text-2xl font-bold text-sky-300 mt-1">
                    {insights.domains.code || 0}
                  </div>
                  <span className="text-[11px] text-text-secondary">Functions, classes & files</span>
                </div>

                <div className="p-4 rounded-xl bg-bg-tertiary border border-emerald-500/20">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400">
                    Architecture
                  </span>
                  <div className="text-2xl font-bold text-emerald-300 mt-1">
                    {insights.domains.architecture || 0}
                  </div>
                  <span className="text-[11px] text-text-secondary">Endpoints, services & tables</span>
                </div>

                <div className="p-4 rounded-xl bg-bg-tertiary border border-amber-500/20">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400">
                    Knowledge Docs
                  </span>
                  <div className="text-2xl font-bold text-amber-300 mt-1">
                    {insights.domains.knowledge || 0}
                  </div>
                  <span className="text-[11px] text-text-secondary">Decisions & spec docs</span>
                </div>
              </div>

              {/* Hub Nodes & Entrypoints Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* Hub Nodes (Highest Centrality) */}
                <div className="p-4 rounded-xl bg-bg-tertiary border border-white/5 flex flex-col">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-amber-400" />
                      <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
                        Core System Hubs (High Centrality)
                      </h3>
                    </div>
                    <span className="text-[10px] text-text-tertiary font-mono">
                      Sorted by degree
                    </span>
                  </div>
                  <p className="text-[11px] text-text-tertiary mb-3">
                    Entities with the most incoming callers and outgoing dependencies. Changes here have the largest blast radius.
                  </p>

                  <div className="space-y-2 flex-1">
                    {insights.hub_nodes.length === 0 ? (
                      <p className="text-xs text-text-tertiary py-4 text-center">No hub nodes found</p>
                    ) : (
                      insights.hub_nodes.slice(0, 6).map((item) => (
                        <div
                          key={item.node.id}
                          onClick={() => {
                            onSelectNode(item.node);
                            onClose();
                          }}
                          className="p-2.5 rounded-lg bg-bg-elevated hover:bg-bg-surface border border-white/5 hover:border-accent/40 transition-all cursor-pointer flex items-center justify-between gap-3 group"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 uppercase">
                                {item.node.node_type}
                              </span>
                              <span className="text-xs font-medium text-text-primary group-hover:text-accent truncate">
                                {item.node.name}
                              </span>
                            </div>
                            <p className="text-[10px] text-text-tertiary font-mono truncate">
                              {item.node.source_uri || item.node.qualified_name}
                            </p>
                          </div>

                          <div className="flex items-center gap-2 text-[10px] font-mono text-text-secondary flex-shrink-0">
                            <span className="flex items-center text-cyan-400" title="Incoming callers">
                              <ArrowDownLeft className="w-3 h-3 mr-0.5" />
                              {item.in_degree}
                            </span>
                            <span className="flex items-center text-emerald-400" title="Outgoing calls">
                              <ArrowUpRight className="w-3 h-3 mr-0.5" />
                              {item.out_degree}
                            </span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Entrypoints & Public Interfaces */}
                <div className="p-4 rounded-xl bg-bg-tertiary border border-white/5 flex flex-col">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Globe className="w-4 h-4 text-emerald-400" />
                      <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
                        Primary System Entrypoints
                      </h3>
                    </div>
                    <span className="text-[10px] text-text-tertiary font-mono">
                      APIs & Root Handlers
                    </span>
                  </div>
                  <p className="text-[11px] text-text-tertiary mb-3">
                    Top-level endpoints and entrypoint routines where external traffic or client calls originate.
                  </p>

                  <div className="space-y-2 flex-1">
                    {insights.entrypoints.length === 0 ? (
                      <p className="text-xs text-text-tertiary py-4 text-center">No entrypoints identified</p>
                    ) : (
                      insights.entrypoints.slice(0, 6).map((item) => (
                        <div
                          key={item.node.id}
                          onClick={() => {
                            onSelectNode(item.node);
                            onClose();
                          }}
                          className="p-2.5 rounded-lg bg-bg-elevated hover:bg-bg-surface border border-white/5 hover:border-emerald-500/40 transition-all cursor-pointer flex items-center justify-between gap-3 group"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 uppercase">
                                {item.node.node_type}
                              </span>
                              <span className="text-xs font-medium text-text-primary group-hover:text-emerald-400 truncate">
                                {item.node.name}
                              </span>
                            </div>
                            <p className="text-[10px] text-text-tertiary font-mono truncate">
                              {item.node.source_uri}
                            </p>
                          </div>

                          <div className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-400 flex-shrink-0">
                            <span>{item.out_degree} deps</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Key Modules / Directory Clusters */}
              <div className="p-4 rounded-xl bg-bg-tertiary border border-white/5">
                <div className="flex items-center gap-2 mb-2">
                  <FolderTree className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wider">
                    Module Footprint & Clusters
                  </h3>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mt-3">
                  {insights.key_modules.map((m) => (
                    <div
                      key={m.module}
                      className="p-2.5 rounded-lg bg-bg-elevated border border-white/5 flex items-center justify-between"
                    >
                      <span className="text-xs font-mono text-text-secondary truncate">{m.module}/</span>
                      <span className="text-xs font-bold text-accent font-mono ml-2">
                        {m.entity_count}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-white/5 bg-bg-primary flex items-center justify-between">
          <button
            onClick={() => {
              onClose();
              onAskCortex?.(
                "Provide an executive architectural breakdown of this repository based on the graph hubs and entrypoints."
              );
            }}
            className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover font-medium cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate Full Architecture Overview in Chat</span>
          </button>

          <button
            onClick={onClose}
            className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-text-primary transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
