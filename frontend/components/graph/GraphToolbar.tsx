"use client";

import React from "react";
import type { NodeDomain } from "../../types/graph";
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
} from "lucide-react";

interface GraphToolbarProps {
  activeDomain: NodeDomain;
  onDomainChange: (domain: NodeDomain) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  nodeCount: number;
  edgeCount: number;
  onFitView: () => void;
  onRefresh: () => void;
  isLoading: boolean;
  onOpenInsights: () => void;
  layoutMode: "organic" | "hierarchical";
  onLayoutModeChange: (mode: "organic" | "hierarchical") => void;
  focusNeighborhood: boolean;
  onToggleFocusNeighborhood: () => void;
  hasSelectedNode: boolean;
}

export function GraphToolbar({
  activeDomain,
  onDomainChange,
  searchQuery,
  onSearchChange,
  nodeCount,
  edgeCount,
  onFitView,
  onRefresh,
  isLoading,
  onOpenInsights,
  layoutMode,
  onLayoutModeChange,
  focusNeighborhood,
  onToggleFocusNeighborhood,
  hasSelectedNode,
}: GraphToolbarProps) {
  const domains: { id: NodeDomain; label: string; icon: React.ReactNode }[] = [
    { id: "all", label: "All", icon: <Layers className="w-3.5 h-3.5" /> },
    { id: "code", label: "Code", icon: <Code2 className="w-3.5 h-3.5" /> },
    { id: "architecture", label: "Architecture", icon: <Cpu className="w-3.5 h-3.5" /> },
    { id: "knowledge", label: "Knowledge", icon: <BookOpen className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-2.5 bg-[#101118]/90 backdrop-blur-md border border-white/10 rounded-xl shadow-xl">
      {/* Search Input */}
      <div className="relative min-w-[200px] max-w-xs flex-1">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Filter symbols, files, services..."
          className="w-full bg-[#171822] border border-border-default rounded-lg pl-8 pr-3 py-1.5 text-xs text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent transition-colors"
        />
      </div>

      {/* Domain Filters */}
      <div className="flex items-center gap-1 bg-[#171822] p-1 rounded-lg border border-border-default">
        {domains.map((d) => (
          <button
            key={d.id}
            onClick={() => onDomainChange(d.id)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
              activeDomain === d.id
                ? "bg-accent text-white shadow-sm"
                : "text-text-secondary hover:text-text-primary hover:bg-white/5"
            }`}
          >
            {d.icon}
            <span>{d.label}</span>
          </button>
        ))}
      </div>

      {/* Layout Mode Toggle */}
      <div className="flex items-center gap-1 bg-[#171822] p-1 rounded-lg border border-border-default">
        <button
          onClick={() => onLayoutModeChange("organic")}
          title="Force-directed organic network (connected nodes gravitate together)"
          className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
            layoutMode === "organic"
              ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/40"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          <Compass className="w-3.5 h-3.5" />
          <span>Organic</span>
        </button>
        <button
          onClick={() => onLayoutModeChange("hierarchical")}
          title="Grouped column hierarchy by domain"
          className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium transition-all cursor-pointer ${
            layoutMode === "hierarchical"
              ? "bg-indigo-600/30 text-indigo-300 border border-indigo-500/40"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          <GitFork className="w-3.5 h-3.5" />
          <span>Hierarchy</span>
        </button>
      </div>

      {/* Neighborhood Focus Toggle */}
      {hasSelectedNode && (
        <button
          onClick={onToggleFocusNeighborhood}
          title="Dim unrelated nodes and spotlight connected paths"
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all cursor-pointer ${
            focusNeighborhood
              ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-[0_0_12px_rgba(6,182,212,0.3)]"
              : "bg-[#171822] text-text-secondary border-border-default hover:text-text-primary"
          }`}
        >
          <Focus className="w-3.5 h-3.5" />
          <span>{focusNeighborhood ? "Focus: ON" : "Focus Paths"}</span>
        </button>
      )}

      {/* Knowledge Insights Trigger */}
      <button
        onClick={onOpenInsights}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-indigo-500/20 to-purple-500/20 hover:from-indigo-500/30 hover:to-purple-500/30 text-indigo-200 border border-indigo-500/40 text-xs font-semibold shadow-sm transition-all cursor-pointer"
      >
        <Sparkles className="w-3.5 h-3.5 text-accent" />
        <span>Insights</span>
      </button>

      {/* Stats & Actions */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5 text-xs font-mono text-text-tertiary px-2 py-1 bg-[#171822] rounded-lg border border-white/5">
          <span>
            <strong className="text-text-primary">{nodeCount}</strong> nodes
          </span>
          <span className="text-white/20">•</span>
          <span>
            <strong className="text-text-primary">{edgeCount}</strong> edges
          </span>
        </div>

        <button
          onClick={onFitView}
          title="Fit graph to view"
          className="p-1.5 rounded-lg bg-[#171822] hover:bg-white/10 text-text-secondary hover:text-text-primary border border-border-default transition-colors cursor-pointer"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={onRefresh}
          disabled={isLoading}
          title="Reload graph data"
          className="p-1.5 rounded-lg bg-[#171822] hover:bg-white/10 text-text-secondary hover:text-text-primary border border-border-default transition-colors disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
        </button>
      </div>
    </div>
  );
}
