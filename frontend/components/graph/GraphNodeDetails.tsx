"use client";

import React, { useEffect, useState } from "react";
import type { GraphNode, NodeNeighborsResponse } from "../../types/graph";
import { graphApi } from "../../lib/api/graph";
import {
  X,
  MessageSquare,
  ArrowUpRight,
  ArrowDownLeft,
  ChevronRight,
  ShieldAlert,
  Loader2,
  BookOpen,
  GitBranch,
} from "lucide-react";

interface GraphNodeDetailsProps {
  node: GraphNode | null;
  repoId: string;
  onClose: () => void;
  onSelectNode: (node: GraphNode) => void;
  onAnalyzeImpact: (node: GraphNode) => void;
  onAskAboutNode: (node: GraphNode) => void;
}

export function GraphNodeDetails({
  node,
  repoId,
  onClose,
  onSelectNode,
  onAnalyzeImpact,
  onAskAboutNode,
}: GraphNodeDetailsProps) {
  const [neighborsData, setNeighborsData] = useState<NodeNeighborsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!node) return;
    let isCancelled = false;
    const timer = setTimeout(() => {
      if (isCancelled) return;
      setLoading(true);
      setErrorMsg(null);

      graphApi
        .getNeighbors(repoId, node.id, "both", 60)
        .then((data) => {
          if (!isCancelled) setNeighborsData(data);
        })
        .catch((err: unknown) => {
          if (!isCancelled) {
            setErrorMsg(err instanceof Error ? err.message : "Failed to load neighbors.");
          }
        })
        .finally(() => {
          if (!isCancelled) setLoading(false);
        });
    }, 0);

    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [node, repoId]);

  if (!node) return null;

  const inCount = neighborsData?.incoming_edges.length || 0;
  const outCount = neighborsData?.outgoing_edges.length || 0;
  const totalRels = inCount + outCount;

  return (
    <aside className="fixed inset-y-0 right-0 z-30 w-84 md:w-96 lg:static bg-bg-secondary/95 backdrop-blur-xl border-l border-border-default flex flex-col h-full shadow-2xl transition-all">
      {/* Header */}
      <div className="p-4 border-b border-white/5 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-accent/15 text-accent border border-accent/25">
              {node.node_type}
            </span>
            <span className="text-[10px] font-mono text-text-tertiary">
              {node.source_kind}
            </span>
            {totalRels >= 5 && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                HUB
              </span>
            )}
          </div>
          <h2 className="text-base font-semibold text-text-primary truncate" title={node.name}>
            {node.name}
          </h2>
          {node.qualified_name && node.qualified_name !== node.name && (
            <p className="text-xs font-mono text-text-tertiary truncate" title={node.qualified_name}>
              {node.qualified_name}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          aria-label="Close node details"
          className="p-1.5 rounded-lg text-text-tertiary hover:text-text-primary hover:bg-bg-tertiary transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Connectivity Metrics Pills */}
      <div className="px-4 py-2.5 border-b border-white/5 bg-bg-tertiary flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-1.5 text-cyan-400">
          <ArrowDownLeft className="w-3.5 h-3.5" />
          <span>{inCount} Callers</span>
        </div>
        <span className="text-white/20">•</span>
        <div className="flex items-center gap-1.5 text-emerald-400">
          <ArrowUpRight className="w-3.5 h-3.5" />
          <span>{outCount} Dependencies</span>
        </div>
        <span className="text-white/20">•</span>
        <div className="flex items-center gap-1 text-slate-400">
          <GitBranch className="w-3.5 h-3.5" />
          <span>{totalRels} Total</span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="p-3 border-b border-white/5 grid grid-cols-2 gap-2">
        <button
          onClick={() => onAnalyzeImpact(node)}
          className="flex items-center justify-center gap-1.5 px-3 py-2 bg-gradient-to-r from-red-500/15 to-orange-500/15 hover:from-red-500/25 hover:to-orange-500/25 text-orange-300 border border-orange-500/30 rounded-xl text-xs font-medium transition-all cursor-pointer"
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Blast Radius</span>
        </button>
        <button
          onClick={() => onAskAboutNode(node)}
          className="flex items-center justify-center gap-1.5 px-3 py-2 bg-accent/15 hover:bg-accent/25 text-accent-hover border border-accent/30 rounded-xl text-xs font-medium transition-all cursor-pointer"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>Ask Cortex</span>
        </button>
      </div>

      {/* Body Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Source Location */}
        {node.source_uri && (
          <div>
            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-1.5">
              Source Location
            </h3>
            <div className="p-2.5 rounded-xl bg-bg-tertiary border border-white/5 flex items-center justify-between text-xs">
              <span className="font-mono text-text-primary truncate" title={node.source_uri}>
                {node.source_uri}
              </span>
              {Boolean(node.properties?.start_line) && (
                <span className="font-mono text-accent text-[11px] ml-2 flex-shrink-0">
                  L{String(node.properties?.start_line)}
                  {node.properties?.end_line ? `-${String(node.properties.end_line)}` : ""}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Description / Docstring Preview */}
        {node.description && (
          <div>
            <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <BookOpen className="w-3.5 h-3.5 text-amber-400" />
              <span>Description / Docstring</span>
            </h3>
            <div className="p-3 rounded-xl bg-bg-tertiary border border-amber-500/20 text-xs text-text-secondary whitespace-pre-wrap font-sans leading-relaxed">
              {node.description}
            </div>
          </div>
        )}

        {/* Neighborhood Relationships */}
        <div>
          <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2">
            Direct Relationships
          </h3>

          {errorMsg ? (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">
              {errorMsg}
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center p-6 text-text-tertiary gap-2 text-xs">
              <Loader2 className="w-4 h-4 animate-spin text-accent" />
              <span>Loading connected entities...</span>
            </div>
          ) : neighborsData ? (
            <div className="space-y-3">
              {/* Outgoing Calls & Dependencies */}
              {neighborsData.outgoing_edges.length > 0 && (
                <div>
                  <div className="flex items-center gap-1 text-[11px] text-text-tertiary mb-1.5 font-mono">
                    <ArrowUpRight className="w-3.5 h-3.5 text-sky-400" />
                    <span>Outgoing ({neighborsData.outgoing_edges.length})</span>
                  </div>
                  <div className="space-y-1.5">
                    {neighborsData.outgoing_edges.map((edge) => {
                      const target = neighborsData.neighbors.find((n) => n.id === edge.target_node_id);
                      const confPct = Math.round((edge.confidence ?? 1) * 100);
                      return (
                        <div
                          key={edge.id}
                          onClick={() => target && onSelectNode(target)}
                          className="flex items-center justify-between p-2 rounded-lg bg-bg-tertiary hover:bg-bg-elevated border border-white/5 hover:border-sky-500/40 cursor-pointer text-xs group transition-all"
                        >
                          <div className="truncate flex-1 mr-2">
                            <div className="flex items-center flex-wrap gap-1 mb-0.5">
                              <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20 uppercase">
                                {edge.edge_type}
                              </span>
                              <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-bg-secondary text-text-tertiary border border-border-default">
                                {confPct}%
                              </span>
                              {edge.evidence_kind && (
                                <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                                  {edge.evidence_kind}
                                </span>
                              )}
                            </div>
                            <span className="text-text-primary group-hover:text-sky-300 font-medium">
                              {target?.name || edge.target_node_id}
                            </span>
                            {target?.source_uri && (
                              <p className="text-[10px] text-text-tertiary font-mono truncate mt-0.5">
                                {target.source_uri}
                              </p>
                            )}
                          </div>
                          <ChevronRight className="w-3.5 h-3.5 text-text-tertiary group-hover:text-text-primary flex-shrink-0" />
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Incoming Callers */}
              {neighborsData.incoming_edges.length > 0 && (
                <div>
                  <div className="flex items-center gap-1 text-[11px] text-text-tertiary mb-1.5 font-mono">
                    <ArrowDownLeft className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Incoming Callers / Upstream ({neighborsData.incoming_edges.length})</span>
                  </div>
                  <div className="space-y-1.5">
                    {neighborsData.incoming_edges.map((edge) => {
                      const source = neighborsData.neighbors.find((n) => n.id === edge.source_node_id);
                      const confPct = Math.round((edge.confidence ?? 1) * 100);
                      return (
                        <div
                          key={edge.id}
                          onClick={() => source && onSelectNode(source)}
                          className="flex items-center justify-between p-2 rounded-lg bg-bg-tertiary hover:bg-bg-elevated border border-white/5 hover:border-emerald-500/40 cursor-pointer text-xs group transition-all"
                        >
                          <div className="truncate flex-1 mr-2">
                            <div className="flex items-center flex-wrap gap-1 mb-0.5">
                              <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 uppercase">
                                {edge.edge_type}
                              </span>
                              <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-bg-secondary text-text-tertiary border border-border-default">
                                {confPct}%
                              </span>
                              {edge.evidence_kind && (
                                <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                                  {edge.evidence_kind}
                                </span>
                              )}
                            </div>
                            <span className="text-text-primary group-hover:text-emerald-300 font-medium">
                              {source?.name || edge.source_node_id}
                            </span>
                            {source?.source_uri && (
                              <p className="text-[10px] text-text-tertiary font-mono truncate mt-0.5">
                                {source.source_uri}
                              </p>
                            )}
                          </div>
                          <ChevronRight className="w-3.5 h-3.5 text-text-tertiary group-hover:text-text-primary flex-shrink-0" />
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {neighborsData.outgoing_edges.length === 0 &&
                neighborsData.incoming_edges.length === 0 && (
                  <p className="text-xs text-text-tertiary italic p-2">
                    No connected relationships found for this entity.
                  </p>
                )}
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
