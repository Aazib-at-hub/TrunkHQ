"use client";

import React, { memo } from "react";
import {
  Server,
  Layout,
  Database,
  BookOpen,
  Maximize2,
  Layers,
  Boxes,
} from "lucide-react";
import type { MacroClusterMeta, UnconnectedSection } from "../../lib/graph/layout";

export interface ClusterGroupNodeData {
  cluster: MacroClusterMeta;
  nodeCount: number;
  connectedCount: number;
  unconnectedCount: number;
  width: number;
  height: number;
  unconnectedSection?: UnconnectedSection;
  onZoomCluster?: () => void;
}

interface ClusterGroupNodeProps {
  data: ClusterGroupNodeData;
}

function getClusterIcon(iconType: string) {
  switch (iconType) {
    case "server":
      return <Server className="w-4 h-4" />;
    case "layout":
      return <Layout className="w-4 h-4" />;
    case "database":
      return <Database className="w-4 h-4" />;
    case "book":
      return <BookOpen className="w-4 h-4" />;
    default:
      return <Layers className="w-4 h-4" />;
  }
}

export const ClusterGroupNode = memo(({ data }: ClusterGroupNodeProps) => {
  const {
    cluster,
    nodeCount,
    connectedCount,
    unconnectedCount,
    width,
    height,
    unconnectedSection,
    onZoomCluster,
  } = data;

  return (
    <div
      style={{
        width,
        height,
        backgroundColor: cluster.color.bg,
        borderColor: cluster.color.border,
        boxShadow: `0 0 50px ${cluster.color.glow}`,
      }}
      className="relative rounded-3xl border-2 border-dashed pointer-events-none transition-all duration-300"
    >
      {/* Cluster Header Banner */}
      <div className="absolute top-4 left-6 right-6 flex items-center justify-between gap-3 pointer-events-auto select-none">
        <div className="flex items-center gap-3">
          <div
            style={{
              backgroundColor: cluster.color.badgeBg,
              color: cluster.color.accent,
              borderColor: cluster.color.borderHighlight,
            }}
            className="p-2.5 rounded-xl border shadow-sm backdrop-blur-md"
          >
            {getClusterIcon(cluster.iconType)}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2
                style={{ color: cluster.color.accent }}
                className="text-sm font-bold tracking-wider uppercase font-mono"
              >
                {cluster.label}
              </h2>
              <span
                style={{
                  backgroundColor: cluster.color.badgeBg,
                  color: cluster.color.badgeText,
                  borderColor: cluster.color.border,
                }}
                className="px-2 py-0.5 rounded-full text-[10px] font-semibold border font-mono"
              >
                {nodeCount} {nodeCount === 1 ? "entity" : "entities"}
              </span>

              {/* Sub-counts */}
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-400 ml-1">
                <span className="text-emerald-400">● {connectedCount} connected</span>
                {unconnectedCount > 0 && (
                  <span className="text-slate-400">
                    • <span className="text-amber-400">{unconnectedCount} standalone</span>
                  </span>
                )}
              </div>
            </div>
            <p className="text-[11px] text-slate-400 font-sans mt-0.5">
              {cluster.tagline}
            </p>
          </div>
        </div>

        {/* Zoom to Cluster Action */}
        {onZoomCluster && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onZoomCluster();
            }}
            title={`Focus ${cluster.label}`}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#141520]/80 hover:bg-[#1a1c2c] border border-white/10 hover:border-white/20 text-xs text-slate-300 hover:text-white transition-all shadow-md cursor-pointer backdrop-blur-sm"
          >
            <Maximize2 className="w-3.5 h-3.5" />
            <span className="font-mono text-[11px]">Frame Cluster</span>
          </button>
        )}
      </div>

      {/* Dedicated Compartment for Unconnected Nodes */}
      {unconnectedSection && unconnectedCount > 0 && (
        <div
          style={{
            left: `${unconnectedSection.x}px`,
            top: `${unconnectedSection.y}px`,
            width: `${unconnectedSection.width}px`,
            height: `${unconnectedSection.height}px`,
            borderColor: cluster.color.border,
            backgroundColor: "rgba(10, 12, 20, 0.65)",
          }}
          className="absolute rounded-2xl border border-dashed backdrop-blur-sm pointer-events-none p-3.5 shadow-inner"
        >
          <div className="flex items-center gap-2 select-none">
            <span
              style={{
                backgroundColor: cluster.color.badgeBg,
                color: cluster.color.accent,
                borderColor: cluster.color.border,
              }}
              className="px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold border flex items-center gap-1.5"
            >
              <Boxes className="w-3 h-3 text-slate-400" />
              STANDALONE & UTILITIES ({unconnectedCount})
            </span>
            <span className="text-[10px] text-slate-400 font-sans">
              — Isolated symbols with no active dependencies
            </span>
          </div>
        </div>
      )}

      {/* Decorative Corner Glow */}
      <div
        style={{
          background: `radial-gradient(circle at top left, ${cluster.color.glow} 0%, transparent 70%)`,
        }}
        className="absolute inset-0 rounded-3xl pointer-events-none opacity-40"
      />
    </div>
  );
});

ClusterGroupNode.displayName = "ClusterGroupNode";
