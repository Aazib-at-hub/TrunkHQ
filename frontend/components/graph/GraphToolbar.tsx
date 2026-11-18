"use client";

import React, { useState } from "react";
import type { GraphNode, NodeDomain } from "../../types/graph";
import type { ClusterBounds, MacroClusterId } from "../../lib/graph/layout";
import {
  Search,
  Maximize2,
  RefreshCw,
  Layers,
  Code2,
  Cpu,
  BookOpen,
  Sparkles,
  GitFork,
  Compass,
  Focus,
  Server,
  Layout,
  Database,
  SlidersHorizontal,
  Route,
  X,
  Loader2,
} from "lucide-react";

interface GraphToolbarProps {
  activeDomain: NodeDomain;
  onDomainChange: (domain: NodeDomain) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  serverSearchResults?: GraphNode[];
  searchingNodes?: boolean;
  onSelectSearchResult?: (node: GraphNode) => void;
  nodeCount: number;
  edgeCount: number;
  loadedNodeCount?: number;
  totalRepoNodes?: number;
  onFitView: () => void;
  onRefresh: () => void;
  isLoading: boolean;
  onOpenInsights: () => void;
  layoutMode: "organic" | "hierarchical";
  onLayoutModeChange: (mode: "organic" | "hierarchical") => void;
  focusNeighborhood: boolean;
  onToggleFocusNeighborhood: () => void;
  hasSelectedNode: boolean;
  tracePathMode?: boolean;
  onToggleTracePathMode?: () => void;
  pathSourceNode?: GraphNode | null;
  pathTargetNode?: GraphNode | null;
  pathStatusMsg?: string | null;
  findingPath?: boolean;
  onClearPath?: () => void;
  impactHighlightCount?: number;
  onClearImpactHighlight?: () => void;
  clusters?: ClusterBounds[];
  activeClusterFilter?: MacroClusterId | "all";
  onSelectClusterFilter?: (clusterId: MacroClusterId | "all") => void;
}

function getClusterIcon(iconType: string) {
  switch (iconType) {
    case "server":
      return <Server className="w-3.5 h-3.5" />;
    case "layout":
      return <Layout className="w-3.5 h-3.5" />;
    case "database":
      return <Database className="w-3.5 h-3.5" />;
    case "book":
      return <BookOpen className="w-3.5 h-3.5" />;
    default:
      return <Layers className="w-3.5 h-3.5" />;
  }
}

export function GraphToolbar({
  activeDomain,
  onDomainChange,
  searchQuery,
  onSearchChange,
  serverSearchResults = [],
  searchingNodes = false,
  onSelectSearchResult,
  nodeCount,
  edgeCount,
  loadedNodeCount,
  totalRepoNodes,
  onFitView,
  onRefresh,
  isLoading,
  onOpenInsights,
  layoutMode,
  onLayoutModeChange,
  focusNeighborhood,
  onToggleFocusNeighborhood,
  hasSelectedNode,
  tracePathMode = false,
  onToggleTracePathMode,
  pathSourceNode,
  pathTargetNode,
  pathStatusMsg,
  findingPath = false,
  onClearPath,
  impactHighlightCount = 0,
  onClearImpactHighlight,
  clusters = [],
  activeClusterFilter = "all",
  onSelectClusterFilter,
}: GraphToolbarProps) {
  const [showViewOptions, setShowViewOptions] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const isSliced = Boolean(
    totalRepoNodes && loadedNodeCount && totalRepoNodes > loadedNodeCount
  );

  const domains: { id: NodeDomain; label: string; icon: React.ReactNode }[] = [
    { id: "all", label: "All", icon: <Layers className="w-3.5 h-3.5" /> },
    { id: "code", label: "Code", icon: <Code2 className="w-3.5 h-3.5" /> },
    { id: "architecture", label: "Architecture", icon: <Cpu className="w-3.5 h-3.5" /> },
    { id: "knowledge", label: "Knowledge", icon: <BookOpen className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="flex flex-col gap-2 p-2.5 bg-bg-secondary/95 backdrop-blur-md border border-border-default rounded-2xl shadow-2xl">
      {/* Primary Bar: Search, Domain Filter, View Options, Fit & Refresh */}
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        {/* Search Input with Server-Side Search Dropdown */}
        <div className="relative min-w-[220px] max-w-xs flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
          <input
            type="text"
            value={searchQuery}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setTimeout(() => setSearchFocused(false), 180)}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search symbols, files, services..."
            className="w-full bg-bg-tertiary border border-border-default rounded-lg pl-8 pr-7 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent transition-colors"
          />
          {searchingNodes && (
            <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3 h-3 animate-spin text-accent" />
          )}

          {searchFocused && searchQuery.trim().length >= 2 && serverSearchResults.length > 0 && (
            <div className="absolute left-0 right-0 top-full mt-1.5 z-50 bg-bg-secondary border border-border-default rounded-xl shadow-2xl max-h-60 overflow-y-auto divide-y divide-border-subtle">
              <div className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary bg-bg-tertiary">
                Repository Search ({serverSearchResults.length})
              </div>
              {serverSearchResults.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    onSelectSearchResult?.(item);
                    setSearchFocused(false);
                  }}
                  className="w-full px-2.5 py-1.5 text-left hover:bg-bg-elevated flex items-center justify-between gap-2 text-xs cursor-pointer transition-colors"
                >
                  <div className="truncate">
                    <span className="font-medium text-text-primary">{item.name}</span>
                    {item.source_uri && (
                      <p className="text-[10px] font-mono text-text-tertiary truncate">
                        {item.source_uri}
                      </p>
                    )}
                  </div>
                  <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded bg-bg-tertiary text-text-tertiary border border-border-default flex-shrink-0">
                    {item.node_type}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Domain Filters */}
        <div className="flex items-center gap-1 bg-bg-tertiary p-1 rounded-lg border border-border-default">
          {domains.map((d) => (
            <button
              key={d.id}
              onClick={() => onDomainChange(d.id)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                activeDomain === d.id
                  ? "bg-accent text-white shadow-sm"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-elevated"
              }`}
            >
              {d.icon}
              <span>{d.label}</span>
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {isSliced && (
            <span
              title={`Graph canvas loaded ${loadedNodeCount} of ${totalRepoNodes} repository nodes. Use search to find any node.`}
              className="hidden sm:inline-flex items-center px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-[11px] font-mono text-amber-300"
            >
              Showing {loadedNodeCount} of {totalRepoNodes} nodes
            </span>
          )}

          {impactHighlightCount > 0 && onClearImpactHighlight && (
            <button
              type="button"
              onClick={onClearImpactHighlight}
              className="flex items-center gap-1 px-2 py-1 rounded-md bg-red-500/15 border border-red-500/30 text-[11px] font-mono text-red-300 hover:bg-red-500/25 cursor-pointer"
            >
              <span>Blast Radius ({impactHighlightCount})</span>
              <X className="w-3 h-3" />
            </button>
          )}

          {onToggleTracePathMode && (
            <button
              type="button"
              onClick={onToggleTracePathMode}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all cursor-pointer ${
                tracePathMode
                  ? "bg-cyan-500/15 text-cyan-300 border-cyan-500/40"
                  : "bg-bg-tertiary text-text-secondary border-border-default hover:text-text-primary"
              }`}
            >
              <Route className="w-3.5 h-3.5" />
              <span>Trace Path</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setShowViewOptions((prev) => !prev)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all cursor-pointer ${
              showViewOptions
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/40"
                : "bg-bg-tertiary text-text-secondary border-border-default hover:text-text-primary"
            }`}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>View Options</span>
          </button>

          <button
            onClick={onFitView}
            title="Fit graph to view"
            aria-label="Fit graph to view"
            className="p-1.5 rounded-lg bg-bg-tertiary hover:bg-bg-elevated text-text-secondary hover:text-text-primary border border-border-default transition-colors cursor-pointer"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onRefresh}
            disabled={isLoading}
            title="Reload graph data"
            aria-label="Reload graph data"
            className="p-1.5 rounded-lg bg-bg-tertiary hover:bg-bg-elevated text-text-secondary hover:text-text-primary border border-border-default transition-colors disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Trace Path Mode Bar */}
      {tracePathMode && (
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-1.5 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-cyan-300 font-semibold">Trace Path:</span>
            <span className="px-2 py-0.5 rounded bg-bg-secondary border border-border-default text-text-primary font-mono">
              1. Source: {pathSourceNode ? pathSourceNode.name : "Click a node"}
            </span>
            <span className="text-text-tertiary">→</span>
            <span className="px-2 py-0.5 rounded bg-bg-secondary border border-border-default text-text-primary font-mono">
              2. Target: {pathTargetNode ? pathTargetNode.name : "Click a node"}
            </span>
            {findingPath && <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-300" />}
            {pathStatusMsg && !findingPath && (
              <span className="font-mono text-[11px] text-cyan-200">{pathStatusMsg}</span>
            )}
          </div>
          {onClearPath && (
            <button
              type="button"
              onClick={onClearPath}
              className="px-2 py-0.5 rounded bg-bg-secondary hover:bg-bg-elevated border border-border-default text-text-secondary hover:text-text-primary text-[11px] cursor-pointer"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* Collapsible Secondary Controls: Layout, Focus, Insights, Clusters */}
      {showViewOptions && (
        <div className="flex flex-col gap-2 pt-2 border-t border-border-default/60">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {/* Layout Mode Toggle */}
            <div className="flex items-center gap-1 bg-bg-tertiary p-1 rounded-lg border border-border-default">
              <button
                onClick={() => onLayoutModeChange("organic")}
                title="Cluster Islands: Organic force-directed layout with separated macro clusters"
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                  layoutMode === "organic"
                    ? "bg-emerald-600/20 text-emerald-400 border border-emerald-500/40"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                <Compass className="w-3.5 h-3.5" />
                <span>Cluster Islands</span>
              </button>
              <button
                onClick={() => onLayoutModeChange("hierarchical")}
                title="Column Hierarchy: Grouped columns by cluster domain"
                className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
                  layoutMode === "hierarchical"
                    ? "bg-emerald-600/20 text-emerald-400 border border-emerald-500/40"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                <GitFork className="w-3.5 h-3.5" />
                <span>Hierarchy</span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              {hasSelectedNode && (
                <button
                  onClick={onToggleFocusNeighborhood}
                  title="Dim unrelated nodes and spotlight connected paths"
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all cursor-pointer ${
                    focusNeighborhood
                      ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
                      : "bg-bg-tertiary text-text-secondary border-border-default hover:text-text-primary"
                  }`}
                >
                  <Focus className="w-3.5 h-3.5" />
                  <span>{focusNeighborhood ? "Focus: ON" : "Focus Paths"}</span>
                </button>
              )}

              <button
                onClick={onOpenInsights}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 border border-emerald-500/40 text-xs font-semibold transition-all cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Insights</span>
              </button>

              <div className="flex items-center gap-1.5 text-xs font-mono text-text-tertiary px-2 py-1 bg-bg-tertiary rounded-lg border border-border-default">
                <span>
                  <strong className="text-text-primary">{nodeCount}</strong> nodes
                </span>
                <span>•</span>
                <span>
                  <strong className="text-text-primary">{edgeCount}</strong> edges
                </span>
              </div>
            </div>
          </div>

          {clusters.length > 0 && onSelectClusterFilter && (
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
              <span className="text-[11px] font-mono uppercase tracking-wider text-text-tertiary pl-1 flex items-center gap-1">
                <Layers className="w-3 h-3 text-accent" />
                Clusters:
              </span>

              <button
                onClick={() => onSelectClusterFilter("all")}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono transition-all cursor-pointer ${
                  activeClusterFilter === "all"
                    ? "bg-bg-elevated text-text-primary border border-border-default shadow-sm"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
                }`}
              >
                <span>All Clusters</span>
                <span className="text-[10px] opacity-70">({nodeCount})</span>
              </button>

              {clusters.map((c) => {
                const isActive = activeClusterFilter === c.clusterId;
                return (
                  <button
                    key={c.clusterId}
                    onClick={() => onSelectClusterFilter(c.clusterId)}
                    style={
                      isActive
                        ? {
                            backgroundColor: c.cluster.color.badgeBg,
                            color: c.cluster.color.accent,
                            borderColor: c.cluster.color.borderHighlight,
                          }
                        : undefined
                    }
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono transition-all border cursor-pointer ${
                      isActive
                        ? "shadow-sm font-semibold"
                        : "border-transparent text-text-secondary hover:text-text-primary hover:bg-bg-tertiary"
                    }`}
                  >
                    {getClusterIcon(c.cluster.iconType)}
                    <span>{c.cluster.shortLabel}</span>
                    <span
                      style={{
                        backgroundColor: c.cluster.color.badgeBg,
                        color: c.cluster.color.accent,
                      }}
                      className="px-1.5 py-0.2 rounded-full text-[10px] font-bold"
                    >
                      {c.nodeCount}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
