"use client";

import React, { useEffect, useState } from "react";
import type { GraphNode, ImpactResponse } from "../../types/graph";
import { graphApi } from "../../lib/api/graph";
import {
  ShieldAlert,
  X,
  Loader2,
  AlertTriangle,
  Layers,
  ShieldCheck,
  Code2,
  MessageSquare,
} from "lucide-react";

interface ImpactPanelProps {
  rootNode: GraphNode | null;
  repoId: string;
  onClose: () => void;
  onAskAboutImpact: (question: string) => void;
}

export function ImpactPanel({
  rootNode,
  repoId,
  onClose,
  onAskAboutImpact,
}: ImpactPanelProps) {
  const [data, setData] = useState<ImpactResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [maxDepth, setMaxDepth] = useState(3);

  useEffect(() => {
    let isCancelled = false;
    if (!rootNode) return;

    const fetchImpact = async () => {
      setLoading(true);
      try {
        const res = await graphApi.getImpact(repoId, rootNode.id, maxDepth);
        if (!isCancelled) {
          setData(res);
        }
      } catch (err) {
        console.error("Impact calculation error:", err);
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    fetchImpact();

    return () => {
      isCancelled = true;
    };
  }, [rootNode, repoId, maxDepth]);

  if (!rootNode) return null;

  const testNodes = data?.impacted_nodes.filter((n) => n.node_type === "test") || [];
  const codeNodes = data?.impacted_nodes.filter((n) => n.node_type !== "test") || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-2xl bg-[#12131a] border border-border-default rounded-xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-red-500/10 via-transparent to-transparent">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-text-primary flex items-center gap-2">
                Blast Radius & Impact Analysis
              </h2>
              <p className="text-xs text-text-tertiary">
                Direct and transitive callers affected by changing{" "}
                <span className="font-mono text-accent font-semibold">{rootNode.name}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-text-tertiary hover:text-text-primary hover:bg-white/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Depth Selector & Summary */}
        <div className="px-5 py-3 border-b border-white/5 flex items-center justify-between bg-[#1a1b25]/50">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-text-secondary font-medium">Traversal Depth:</span>
            {[1, 2, 3, 4].map((d) => (
              <button
                key={d}
                onClick={() => setMaxDepth(d)}
                className={`px-2.5 py-1 rounded text-xs font-mono font-medium transition-all ${
                  maxDepth === d
                    ? "bg-accent text-white"
                    : "bg-[#12131a] text-text-tertiary hover:text-text-primary border border-border-default"
                }`}
              >
                {d} {d === 1 ? "hop" : "hops"}
              </button>
            ))}
          </div>

          {data && (
            <div className="text-xs font-mono text-text-secondary">
              <strong className="text-red-400 font-bold">{data.total_impacted}</strong> entities at risk
            </div>
          )}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center gap-3 text-text-tertiary">
              <Loader2 className="w-6 h-6 animate-spin text-accent" />
              <span className="text-xs">Computing blast radius traversal...</span>
            </div>
          ) : data ? (
            <>
              {/* Summary Stats Cards */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-[#1a1b25] border border-border-default">
                  <div className="flex items-center gap-1.5 text-xs text-text-tertiary mb-1">
                    <Code2 className="w-3.5 h-3.5 text-sky-400" />
                    <span>Upstream Callers</span>
                  </div>
                  <div className="text-lg font-bold font-mono text-text-primary">
                    {codeNodes.length}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-[#1a1b25] border border-border-default">
                  <div className="flex items-center gap-1.5 text-xs text-text-tertiary mb-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                    <span>Affected Tests</span>
                  </div>
                  <div className="text-lg font-bold font-mono text-purple-300">
                    {testNodes.length}
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-[#1a1b25] border border-border-default">
                  <div className="flex items-center gap-1.5 text-xs text-text-tertiary mb-1">
                    <Layers className="w-3.5 h-3.5 text-amber-400" />
                    <span>Relationship Hops</span>
                  </div>
                  <div className="text-lg font-bold font-mono text-text-primary">
                    {Object.values(data.depth_levels).length > 0
                      ? Math.max(...Object.values(data.depth_levels))
                      : 0}
                  </div>
                </div>
              </div>

              {/* Tests Section */}
              {testNodes.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-purple-400" />
                    <span>Tests to Run on Modification ({testNodes.length})</span>
                  </h3>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {testNodes.map((test) => (
                      <div
                        key={test.id}
                        className="flex items-center justify-between p-2 rounded-md bg-purple-500/5 border border-purple-500/20 text-xs"
                      >
                        <span className="font-mono text-purple-200">{test.name}</span>
                        <span className="text-[10px] text-text-tertiary truncate max-w-[200px]">
                          {test.source_uri}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Callers & Downstream List */}
              <div>
                <h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-orange-400" />
                  <span>Potentially Broken Dependencies ({codeNodes.length})</span>
                </h3>
                {codeNodes.length === 0 ? (
                  <p className="text-xs text-text-tertiary italic p-3 bg-[#1a1b25] rounded-lg">
                    No upstream callers or direct dependencies detected within {maxDepth} hops.
                  </p>
                ) : (
                  <div className="space-y-1.5 max-h-60 overflow-y-auto">
                    {codeNodes.map((item) => {
                      const depth = data.depth_levels[item.id] || 1;
                      return (
                        <div
                          key={item.id}
                          className="flex items-center justify-between p-2 rounded-md bg-[#1a1b25] border border-border-default text-xs"
                        >
                          <div className="flex items-center gap-2 truncate flex-1 mr-3">
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-text-tertiary">
                              Hop {depth}
                            </span>
                            <span className="font-medium text-text-primary truncate">
                              {item.name}
                            </span>
                            <span className="text-[10px] font-mono text-text-tertiary uppercase">
                              ({item.node_type})
                            </span>
                          </div>
                          <span className="text-[10px] font-mono text-text-tertiary truncate max-w-[150px]">
                            {item.source_uri}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/5 flex items-center justify-between bg-[#1a1b25]/50">
          <button
            onClick={() => {
              const q = `What might break if I modify ${rootNode.name} (${rootNode.qualified_name || rootNode.source_uri})? Analyze its upstream callers and dependencies.`;
              onAskAboutImpact(q);
              onClose();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-xs font-medium transition-all shadow-md ml-auto"
          >
            <MessageSquare className="w-4 h-4" />
            <span>Ask Cortex to Analyze This Blast Radius</span>
          </button>
        </div>
      </div>
    </div>
  );
}
