"use client";

import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { GraphNode } from "../../types/graph";
import {
  Code2,
  Box,
  Cpu,
  FileCode,
  FileText,
  ShieldCheck,
  Globe,
  Database,
  Layers,
  Terminal,
  ArrowDownLeft,
  ArrowUpRight,
  BookOpen,
} from "lucide-react";

export interface CustomNodeData {
  node: GraphNode;
  isSelected?: boolean;
  isHighlighted?: boolean;
  isDimmed?: boolean;
  inDegree?: number;
  outDegree?: number;
  role?: string;
  onSelect?: (node: GraphNode) => void;
}

interface CustomNodeProps {
  data: CustomNodeData;
}

function getIcon(type: string, sourceKind: string) {
  switch (type) {
    case "function":
    case "method":
      return <Code2 className="w-3.5 h-3.5 text-sky-400" />;
    case "class":
      return <Box className="w-3.5 h-3.5 text-indigo-400" />;
    case "file":
      return <FileCode className="w-3.5 h-3.5 text-blue-400" />;
    case "service":
      return <Cpu className="w-3.5 h-3.5 text-emerald-400" />;
    case "api_endpoint":
      return <Globe className="w-3.5 h-3.5 text-teal-400" />;
    case "database":
    case "table":
      return <Database className="w-3.5 h-3.5 text-cyan-400" />;
    case "document":
      return <FileText className="w-3.5 h-3.5 text-amber-400" />;
    case "test":
      return <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />;
    default:
      return sourceKind === "architecture" ? (
        <Layers className="w-3.5 h-3.5 text-emerald-400" />
      ) : (
        <Terminal className="w-3.5 h-3.5 text-slate-400" />
      );
  }
}

function getDomainColor(sourceKind: string, type: string) {
  if (type === "test") {
    return {
      border: "border-purple-500/40 hover:border-purple-400",
      badge: "bg-purple-500/10 text-purple-300 border-purple-500/20",
      glow: "hover:shadow-[0_0_15px_rgba(168,85,247,0.25)]",
    };
  }
  switch (sourceKind) {
    case "architecture":
      return {
        border: "border-emerald-500/40 hover:border-emerald-400",
        badge: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
        glow: "hover:shadow-[0_0_15px_rgba(16,185,129,0.25)]",
      };
    case "knowledge":
      return {
        border: "border-amber-500/40 hover:border-amber-400",
        badge: "bg-amber-500/10 text-amber-300 border-amber-500/20",
        glow: "hover:shadow-[0_0_15px_rgba(245,158,11,0.25)]",
      };
    case "code":
    default:
      return {
        border: "border-sky-500/40 hover:border-sky-400",
        badge: "bg-sky-500/10 text-sky-300 border-sky-500/20",
        glow: "hover:shadow-[0_0_15px_rgba(14,165,233,0.25)]",
      };
  }
}

export const CustomNode = memo(({ data }: CustomNodeProps) => {
  const {
    node,
    isSelected,
    isHighlighted,
    isDimmed,
    inDegree = 0,
    outDegree = 0,
    role,
  } = data;
  const colors = getDomainColor(node.source_kind, node.node_type);

  const totalDegree = inDegree + outDegree;
  const isHub = role === "hub" || totalDegree >= 6;
  const isEntrypoint = role === "entrypoint" || (inDegree === 0 && outDegree > 0 && node.node_type === "api_endpoint");

  return (
    <div
      className={`relative px-3.5 py-2.5 rounded-xl bg-[#101118]/95 backdrop-blur-md border transition-all duration-300 cursor-pointer min-w-[210px] max-w-[280px] shadow-lg ${
        colors.border
      } ${colors.glow} ${
        isDimmed
          ? "opacity-25 filter blur-[0.4px] scale-95"
          : isSelected
          ? "ring-2 ring-indigo-400 border-indigo-400 shadow-[0_0_24px_rgba(99,102,241,0.55)] scale-[1.03] z-30"
          : isHighlighted
          ? "ring-2 ring-cyan-400/80 border-cyan-400 shadow-[0_0_18px_rgba(6,182,212,0.4)] scale-[1.02] z-20"
          : "hover:scale-[1.01]"
      }`}
    >
      {/* 4-way connection handles */}
      <Handle
        type="target"
        position={Position.Top}
        id="t"
        className="!w-2 !h-2 !bg-slate-400 !border-none"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="l"
        className="!w-2 !h-2 !bg-slate-400 !border-none"
      />

      {/* Header: Icon, Name & Type */}
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 truncate">
          <div className="p-1 rounded-md bg-[#181926] border border-white/5">
            {getIcon(node.node_type, node.source_kind)}
          </div>
          <span className="text-xs font-semibold text-text-primary truncate" title={node.name}>
            {node.name}
          </span>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          {isHub && (
            <span className="text-[8px] font-bold uppercase tracking-wider font-mono px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
              HUB
            </span>
          )}
          {isEntrypoint && (
            <span className="text-[8px] font-bold uppercase tracking-wider font-mono px-1 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
              ENTRY
            </span>
          )}
          <span
            className={`text-[9px] uppercase tracking-wider font-mono px-1.5 py-0.5 rounded border ${colors.badge}`}
          >
            {node.node_type}
          </span>
        </div>
      </div>

      {/* Qualified / Module name */}
      {node.qualified_name && node.qualified_name !== node.name && (
        <p className="text-[10px] text-text-tertiary truncate font-mono mb-1">
          {node.qualified_name}
        </p>
      )}

      {/* Description Snippet preview */}
      {node.description && (
        <div className="flex items-start gap-1 text-[10px] text-slate-300/80 line-clamp-1 italic mb-1 bg-white/[0.02] px-1.5 py-0.5 rounded border border-white/5">
          <BookOpen className="w-2.5 h-2.5 mt-0.5 text-amber-400/80 flex-shrink-0" />
          <span className="truncate">{node.description}</span>
        </div>
      )}

      {/* Footer: Source File & Degree metrics */}
      <div className="mt-1 flex items-center justify-between text-[10px] text-text-tertiary border-t border-white/5 pt-1.5">
        <span className="truncate max-w-[130px]" title={node.source_uri || ""}>
          {node.source_uri ? node.source_uri.split("/").slice(-2).join("/") : "global"}
        </span>

        <div className="flex items-center gap-2 font-mono text-[9px]">
          {inDegree > 0 && (
            <span className="flex items-center text-cyan-400" title={`${inDegree} incoming callers/dependents`}>
              <ArrowDownLeft className="w-2.5 h-2.5 mr-0.5" />
              {inDegree}
            </span>
          )}
          {outDegree > 0 && (
            <span className="flex items-center text-indigo-400" title={`${outDegree} outgoing dependencies/calls`}>
              <ArrowUpRight className="w-2.5 h-2.5 mr-0.5" />
              {outDegree}
            </span>
          )}
          {Boolean(node.properties?.start_line) && (
            <span className="text-slate-500">
              L{String(node.properties?.start_line)}
            </span>
          )}
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        id="b"
        className="!w-2 !h-2 !bg-accent !border-none"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="r"
        className="!w-2 !h-2 !bg-accent !border-none"
      />
    </div>
  );
});

CustomNode.displayName = "CustomNode";
