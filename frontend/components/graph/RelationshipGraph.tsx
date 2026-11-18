"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Node,
  type Edge,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { CustomNode, type CustomNodeData } from "./CustomNode";
import { ClusterGroupNode } from "./ClusterGroupNode";
import { GraphToolbar } from "./GraphToolbar";
import { GraphNodeDetails } from "./GraphNodeDetails";
import { ImpactPanel } from "./ImpactPanel";
import { GraphInsightsPanel } from "./GraphInsightsPanel";
import { graphApi } from "../../lib/api/graph";
import {
  computeConnectivity,
  computeOrganicForceLayout,
  computeHierarchicalLayout,
  determineMacroCluster,
  CLUSTER_CONFIGS,
  type LayoutMode,
  type ClusterBounds,
  type MacroClusterId,
} from "../../lib/graph/layout";
import type { GraphNode, GraphEdge, NodeDomain } from "../../types/graph";
import { Loader2, AlertCircle, Network, Sparkles } from "lucide-react";

interface RelationshipGraphProps {
  repositoryId: string;
  onAskCortex?: (question: string) => void;
}

const nodeTypes = {
  custom: CustomNode,
  clusterGroup: ClusterGroupNode,
};

export function RelationshipGraph({
  repositoryId,
  onAskCortex,
}: RelationshipGraphProps) {
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const [rawNodes, setRawNodes] = useState<GraphNode[]>([]);
  const [rawEdges, setRawEdges] = useState<GraphEdge[]>([]);
  const [totalRepoNodes, setTotalRepoNodes] = useState<number>(0);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeDomain, setActiveDomain] = useState<NodeDomain>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [serverSearchResults, setServerSearchResults] = useState<GraphNode[]>([]);
  const [searchingNodes, setSearchingNodes] = useState(false);

  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [impactRootNode, setImpactRootNode] = useState<GraphNode | null>(null);
  const [showInsights, setShowInsights] = useState(false);

  // Trace Path mode state
  const [tracePathMode, setTracePathMode] = useState(false);
  const [pathSourceNode, setPathSourceNode] = useState<GraphNode | null>(null);
  const [pathTargetNode, setPathTargetNode] = useState<GraphNode | null>(null);
  const [pathNodeIds, setPathNodeIds] = useState<Set<string>>(new Set());
  const [pathEdgeIds, setPathEdgeIds] = useState<Set<string>>(new Set());
  const [pathStatusMsg, setPathStatusMsg] = useState<string | null>(null);
  const [findingPath, setFindingPath] = useState(false);

  // Blast radius canvas highlight state
  const [impactNodeIds, setImpactNodeIds] = useState<Set<string>>(new Set());
  const [impactEdgeIds, setImpactEdgeIds] = useState<Set<string>>(new Set());

  // Layout, Cluster & Focus states
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("organic");
  const [focusNeighborhood, setFocusNeighborhood] = useState(false);
  const [activeClusterFilter, setActiveClusterFilter] = useState<MacroClusterId | "all">("all");

  const filteredRawNodes = useMemo(() => {
    return rawNodes.filter((n) => {
      if (activeDomain !== "all" && n.source_kind !== activeDomain) {
        return false;
      }
      if (
        activeClusterFilter !== "all" &&
        determineMacroCluster(n) !== activeClusterFilter
      ) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = n.name.toLowerCase().includes(q);
        const matchesQual = n.qualified_name?.toLowerCase().includes(q);
        const matchesType = n.node_type.toLowerCase().includes(q);
        const matchesDesc = n.description?.toLowerCase().includes(q);
        if (!matchesName && !matchesQual && !matchesType && !matchesDesc) return false;
      }
      return true;
    });
  }, [rawNodes, activeDomain, activeClusterFilter, searchQuery]);

  const filteredNodeCount = filteredRawNodes.length;

  const filteredRawEdges = useMemo(() => {
    const nodeIds = new Set(filteredRawNodes.map((n) => n.id));
    return rawEdges.filter(
      (e) => nodeIds.has(e.source_node_id) && nodeIds.has(e.target_node_id)
    );
  }, [filteredRawNodes, rawEdges]);

  const layoutResult = useMemo(() => {
    return layoutMode === "organic"
      ? computeOrganicForceLayout(filteredRawNodes, filteredRawEdges)
      : computeHierarchicalLayout(filteredRawNodes, filteredRawEdges);
  }, [layoutMode, filteredRawNodes, filteredRawEdges]);

  const clusters = layoutResult.clusters;

  // Zoom to Cluster Island
  const handleZoomToCluster = useCallback(
    (cb: ClusterBounds) => {
      if (rfInstance) {
        rfInstance.fitBounds(
          {
            x: cb.x,
            y: cb.y,
            width: cb.width,
            height: cb.height,
          },
          { padding: 0.18, duration: 650 }
        );
      }
    },
    [rfInstance]
  );

  // Load Graph Data
  const loadGraph = useCallback(async () => {
    try {
      const data = await graphApi.getGraph(repositoryId, undefined, 450);
      setRawNodes(data.nodes);
      setRawEdges(data.edges);
      setTotalRepoNodes(data.total_nodes);
      setError(null);
    } catch (err: unknown) {
      console.error("Failed to load graph:", err);
      const msg = err instanceof Error ? err.message : "Failed to load relationship graph.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [repositoryId]);

  const [reindexing, setReindexing] = useState(false);

  const handleReindexGraph = async () => {
    setReindexing(true);
    try {
      await graphApi.reindex(repositoryId);
      await loadGraph();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError("Failed to build graph: " + msg);
    } finally {
      setReindexing(false);
    }
  };

  useEffect(() => {
    let isCancelled = false;
    graphApi
      .getGraph(repositoryId, undefined, 450)
      .then((data) => {
        if (!isCancelled) {
          setRawNodes(data.nodes);
          setRawEdges(data.edges);
          setTotalRepoNodes(data.total_nodes);
          setError(null);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          const msg = err instanceof Error ? err.message : "Failed to load relationship graph.";
          setError(msg);
          setLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [repositoryId]);

  // Debounced server-side node search
  useEffect(() => {
    const q = searchQuery.trim();
    let cancelled = false;
    const timer = setTimeout(() => {
      if (q.length < 2) {
        if (!cancelled) {
          setServerSearchResults([]);
          setSearchingNodes(false);
        }
        return;
      }
      if (!cancelled) setSearchingNodes(true);
      graphApi
        .searchNodes(repositoryId, q, undefined, 20)
        .then((results) => {
          if (!cancelled) setServerSearchResults(results);
        })
        .catch(() => {
          if (!cancelled) setServerSearchResults([]);
        })
        .finally(() => {
          if (!cancelled) setSearchingNodes(false);
        });
    }, q.length < 2 ? 0 : 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [repositoryId, searchQuery]);

  // Compute Layout, Degrees & Neighborhood Filtering
  useEffect(() => {
    const filteredNodes = filteredRawNodes;
    const filteredEdges = filteredRawEdges;

    // 3. Pre-calculate connectivity metrics
    const { inDegree, outDegree, neighbors } = computeConnectivity(
      filteredNodes,
      filteredEdges
    );

    // 4. Determine focused neighborhood
    const connectedNodeIds = new Set<string>();
    const connectedEdgeIds = new Set<string>();

    if (selectedNode) {
      connectedNodeIds.add(selectedNode.id);
      const directNeighbors = neighbors.get(selectedNode.id);
      if (directNeighbors) {
        directNeighbors.forEach((nid) => connectedNodeIds.add(nid));
      }

      for (const e of filteredEdges) {
        if (
          e.source_node_id === selectedNode.id ||
          e.target_node_id === selectedNode.id
        ) {
          connectedEdgeIds.add(e.id);
        }
      }
    }

    // 5. Position nodes via physics or hierarchy + extract macro clusters
    const { positions, clusters: layoutClusters, nodeClusterMap, unconnectedNodeIds } = layoutResult;

    // 6. Generate Cluster Hull Background Nodes (Graphify / CodeGraph style)
    const clusterGroupNodes: Node[] = layoutClusters.map((cb) => ({
      id: `cluster-group-${cb.clusterId}`,
      type: "clusterGroup",
      position: { x: cb.x, y: cb.y },
      data: {
        cluster: cb.cluster,
        nodeCount: cb.nodeCount,
        connectedCount: cb.connectedCount,
        unconnectedCount: cb.unconnectedCount,
        unconnectedSection: cb.unconnectedSection,
        width: cb.width,
        height: cb.height,
        onZoomCluster: () => handleZoomToCluster(cb),
      },
      selectable: false,
      draggable: false,
      style: {
        width: cb.width,
        height: cb.height,
        zIndex: -1,
      },
    }));

    const layoutNodes: Node[] = filteredNodes.map((node) => {
      const pos = positions.get(node.id) || { x: 400, y: 300 };
      const inDeg = inDegree.get(node.id) || 0;
      const outDeg = outDegree.get(node.id) || 0;
      const totDeg = inDeg + outDeg;

      let role = "standard";
      if (totDeg >= 5) role = "hub";
      else if (inDeg === 0 && outDeg > 0) role = "entrypoint";

      const isSelected = selectedNode?.id === node.id;
      const isNeighbor = selectedNode ? connectedNodeIds.has(node.id) : false;
      const isPathNode = pathNodeIds.has(node.id);
      const isImpactNode = impactNodeIds.has(node.id);
      const hasPathHighlight = pathNodeIds.size > 0;
      const hasImpactHighlight = !hasPathHighlight && impactNodeIds.size > 0;

      const isDimmed = hasPathHighlight
        ? !isPathNode
        : hasImpactHighlight
        ? !isImpactNode
        : Boolean(focusNeighborhood && selectedNode && !isNeighbor);

      const clusterId = nodeClusterMap.get(node.id) || "backend";
      const clusterMeta = CLUSTER_CONFIGS[clusterId];
      const isUnconnected = unconnectedNodeIds.has(node.id);

      const nodeData: CustomNodeData = {
        node,
        isSelected: isSelected || pathSourceNode?.id === node.id || pathTargetNode?.id === node.id,
        isHighlighted:
          isPathNode ||
          isImpactNode ||
          (isNeighbor && !isSelected),
        isDimmed,
        inDegree: inDeg,
        outDegree: outDeg,
        role,
        cluster: clusterMeta,
        isUnconnected,
      };

      return {
        id: node.id,
        type: "custom",
        position: pos,
        data: nodeData as unknown as Record<string, unknown>,
      };
    });

    // 7. Formatted Edges with 4-way handle routing
    const posMap = positions;
    const layoutEdges: Edge[] = filteredEdges.map((e) => {
      const isIncident = connectedEdgeIds.has(e.id);
      const isPathEdge = pathEdgeIds.has(e.id);
      const isImpactEdge = impactEdgeIds.has(e.id);
      const hasPathHighlight = pathNodeIds.size > 0;
      const hasImpactHighlight = !hasPathHighlight && impactNodeIds.size > 0;
      const isDimmed = hasPathHighlight
        ? !isPathEdge
        : hasImpactHighlight
        ? !isImpactEdge
        : Boolean(focusNeighborhood && selectedNode && !isIncident);

      let strokeColor = "#64748b";
      let animated = false;

      if (e.edge_type === "CALLS") strokeColor = "#38bdf8";
      else if (e.edge_type === "IMPORTS") strokeColor = "#818cf8";
      else if (e.edge_type === "DEPENDS_ON" || e.edge_type === "EXPOSES")
        strokeColor = "#10b981";
      else if (e.edge_type === "TESTS") {
        strokeColor = "#c084fc";
        animated = true;
      } else if (e.edge_type === "DOCUMENTS") strokeColor = "#f59e0b";

      if (isPathEdge) {
        strokeColor = "#22d3ee";
        animated = true;
      } else if (isImpactEdge) {
        strokeColor = "#f97316";
        animated = true;
      } else if (isIncident) {
        strokeColor = "#38bdf8";
        animated = true;
      }

      // Compute natural 4-way connection handles
      const srcPos = posMap.get(e.source_node_id);
      const tgtPos = posMap.get(e.target_node_id);
      let sourceHandle = "b";
      let targetHandle = "t";

      if (srcPos && tgtPos) {
        const dx = tgtPos.x - srcPos.x;
        const dy = tgtPos.y - srcPos.y;

        if (Math.abs(dx) > Math.abs(dy)) {
          if (dx > 0) {
            sourceHandle = "r";
            targetHandle = "l";
          } else {
            sourceHandle = "l";
            targetHandle = "r";
          }
        } else {
          if (dy > 0) {
            sourceHandle = "b";
            targetHandle = "t";
          } else {
            sourceHandle = "t";
            targetHandle = "b";
          }
        }
      }

      return {
        id: e.id,
        source: e.source_node_id,
        target: e.target_node_id,
        sourceHandle,
        targetHandle,
        animated,
        label: isPathEdge || isImpactEdge || isIncident ? e.edge_type : undefined,
        labelStyle: {
          fill: "#93c5fd",
          fontSize: 9,
          fontFamily: "monospace",
          fontWeight: 600,
        },
        labelBgStyle: { fill: "#0f172a", fillOpacity: 0.85 },
        labelBgPadding: [4, 2] as [number, number],
        labelBgBorderRadius: 4,
        style: {
          stroke: isDimmed ? "#1e293b" : strokeColor,
          strokeWidth: isPathEdge ? 3 : isImpactEdge || isIncident ? 2.5 : 1.4,
          opacity: isDimmed ? 0.15 : 1,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isDimmed ? "#1e293b" : strokeColor,
          width: isPathEdge || isImpactEdge || isIncident ? 16 : 12,
          height: isPathEdge || isImpactEdge || isIncident ? 16 : 12,
        },
      };
    });

    setNodes([...clusterGroupNodes, ...layoutNodes]);
    setEdges(layoutEdges);
  }, [
    filteredRawNodes,
    filteredRawEdges,
    layoutResult,
    selectedNode,
    focusNeighborhood,
    pathNodeIds,
    pathEdgeIds,
    pathSourceNode,
    pathTargetNode,
    impactNodeIds,
    impactEdgeIds,
    handleZoomToCluster,
    setNodes,
    setEdges,
  ]);

  const handleClearPath = useCallback(() => {
    setPathSourceNode(null);
    setPathTargetNode(null);
    setPathNodeIds(new Set());
    setPathEdgeIds(new Set());
    setPathStatusMsg(null);
  }, []);

  const handleToggleTracePathMode = useCallback(() => {
    setTracePathMode((prev) => {
      if (prev) {
        handleClearPath();
      }
      return !prev;
    });
  }, [handleClearPath]);

  const handleImpactComputed = useCallback(
    (
      nodeIds: Set<string>,
      edgeIds: Set<string>,
      impactedNodes: GraphNode[],
      impactedEdges: GraphEdge[]
    ) => {
      setImpactNodeIds(nodeIds);
      setImpactEdgeIds(edgeIds);
      if (impactedNodes.length > 0) {
        setRawNodes((prev) => {
          const seen = new Set(prev.map((n) => n.id));
          const additions = impactedNodes.filter((n) => !seen.has(n.id));
          return additions.length > 0 ? [...prev, ...additions] : prev;
        });
      }
      if (impactedEdges.length > 0) {
        setRawEdges((prev) => {
          const seen = new Set(prev.map((e) => e.id));
          const additions = impactedEdges.filter((e) => !seen.has(e.id));
          return additions.length > 0 ? [...prev, ...additions] : prev;
        });
      }
    },
    []
  );

  // Click handler
  const handleNodeClick = useCallback(
    (_: React.MouseEvent, flowNode: Node) => {
      const found = rawNodes.find((n) => n.id === flowNode.id);
      if (!found) return;

      if (tracePathMode) {
        if (!pathSourceNode || pathTargetNode) {
          setPathSourceNode(found);
          setPathTargetNode(null);
          setPathNodeIds(new Set([found.id]));
          setPathEdgeIds(new Set());
          setPathStatusMsg("Select target node...");
        } else if (found.id !== pathSourceNode.id) {
          setPathTargetNode(found);
          setFindingPath(true);
          setPathStatusMsg(null);
          graphApi
            .findPath(repositoryId, pathSourceNode.id, found.id, 6)
            .then((res) => {
              if (res.found) {
                const nIds = new Set<string>();
                const eIds = new Set<string>();
                const newNodes: GraphNode[] = [];
                const newEdges: GraphEdge[] = [];
                for (const step of res.steps) {
                  if (step.node) {
                    nIds.add(step.node.id);
                    newNodes.push(step.node);
                  }
                  if (step.edge) {
                    eIds.add(step.edge.id);
                    newEdges.push(step.edge);
                  }
                }
                if (newNodes.length > 0) {
                  setRawNodes((prev) => {
                    const seen = new Set(prev.map((n) => n.id));
                    const add = newNodes.filter((n) => !seen.has(n.id));
                    return add.length > 0 ? [...prev, ...add] : prev;
                  });
                }
                if (newEdges.length > 0) {
                  setRawEdges((prev) => {
                    const seen = new Set(prev.map((e) => e.id));
                    const add = newEdges.filter((e) => !seen.has(e.id));
                    return add.length > 0 ? [...prev, ...add] : prev;
                  });
                }
                setPathNodeIds(nIds);
                setPathEdgeIds(eIds);
                setPathStatusMsg(`Path found (${res.length} hops)`);
              } else {
                setPathNodeIds(new Set([pathSourceNode.id, found.id]));
                setPathEdgeIds(new Set());
                setPathStatusMsg("No path found within 6 hops");
              }
            })
            .catch((err: unknown) => {
              setPathStatusMsg(err instanceof Error ? err.message : "Failed to trace path");
            })
            .finally(() => setFindingPath(false));
        }
        return;
      }

      setSelectedNode(found);
    },
    [rawNodes, tracePathMode, pathSourceNode, pathTargetNode, repositoryId]
  );

  // Focus & Center helper
  const handleSelectAndCenterNode = useCallback(
    (targetNode: GraphNode) => {
      setRawNodes((prev) => {
        if (prev.some((n) => n.id === targetNode.id)) return prev;
        return [...prev, targetNode];
      });
      setSelectedNode(targetNode);
      if (rfInstance) {
        const found = nodes.find((n) => n.id === targetNode.id);
        if (found) {
          rfInstance.setCenter(found.position.x + 110, found.position.y + 40, {
            zoom: 1.15,
            duration: 650,
          });
        }
      }
    },
    [nodes, rfInstance]
  );

  return (
    <div className="relative w-full h-full flex overflow-hidden bg-bg-primary">
      {/* Main Canvas Area */}
      <div className="flex-1 flex flex-col relative h-full">
        {/* Top Controls Toolbar */}
        <div className="absolute top-4 left-4 right-4 z-10">
          <GraphToolbar
            activeDomain={activeDomain}
            onDomainChange={setActiveDomain}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            serverSearchResults={serverSearchResults}
            searchingNodes={searchingNodes}
            onSelectSearchResult={handleSelectAndCenterNode}
            nodeCount={filteredNodeCount}
            edgeCount={edges.length}
            loadedNodeCount={rawNodes.length}
            totalRepoNodes={totalRepoNodes}
            onFitView={() => rfInstance?.fitView({ duration: 500 })}
            onRefresh={loadGraph}
            isLoading={loading}
            onOpenInsights={() => setShowInsights(true)}
            layoutMode={layoutMode}
            onLayoutModeChange={setLayoutMode}
            focusNeighborhood={focusNeighborhood}
            onToggleFocusNeighborhood={() => setFocusNeighborhood((prev) => !prev)}
            hasSelectedNode={Boolean(selectedNode)}
            tracePathMode={tracePathMode}
            onToggleTracePathMode={handleToggleTracePathMode}
            pathSourceNode={pathSourceNode}
            pathTargetNode={pathTargetNode}
            pathStatusMsg={pathStatusMsg}
            findingPath={findingPath}
            onClearPath={handleClearPath}
            impactHighlightCount={impactNodeIds.size}
            onClearImpactHighlight={() => {
              setImpactNodeIds(new Set());
              setImpactEdgeIds(new Set());
            }}
            clusters={clusters}
            activeClusterFilter={activeClusterFilter}
            onSelectClusterFilter={(cid) => {
              setActiveClusterFilter(cid);
              if (cid !== "all") {
                const target = clusters.find((c) => c.clusterId === cid);
                if (target) handleZoomToCluster(target);
              }
            }}
          />
        </div>

        {/* Loading / Error States */}
        {loading && nodes.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-text-tertiary">
            <Loader2 className="w-8 h-8 animate-spin text-accent" />
            <p className="text-sm">Calculating physics layout & extracting relationship graph...</p>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
            <div className="p-3 rounded-xl bg-red-500/10 text-red-400 border border-red-500/20">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-text-primary">Graph Unavailable</h3>
            <p className="text-xs text-text-tertiary max-w-sm">{error}</p>
            <button
              onClick={loadGraph}
              className="mt-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-lg text-xs text-text-primary transition-colors cursor-pointer"
            >
              Retry
            </button>
          </div>
        ) : nodes.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center text-text-tertiary">
            {rawNodes.length === 0 ? (
              <>
                <div className="p-3.5 rounded-2xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-1 shadow-inner">
                  <Network className="w-8 h-8" />
                </div>
                <h3 className="text-base font-semibold text-text-primary">
                  Relationship Graph Not Indexed Yet
                </h3>
                <p className="text-xs text-text-secondary max-w-md leading-relaxed">
                  Extract symbols, calls, fullstack TypeScript/Python components, and relationships instantly from your codebase.
                </p>
                <button
                  onClick={handleReindexGraph}
                  disabled={reindexing}
                  className="mt-2 flex items-center gap-2 px-5 py-2.5 rounded-xl bg-accent hover:bg-accent-hover text-white text-xs font-semibold shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-50 cursor-pointer"
                >
                  <Sparkles className={`w-4 h-4 ${reindexing ? "animate-spin" : ""}`} />
                  <span>
                    {reindexing
                      ? "Extracting Multi-Language Graph..."
                      : "Build Relationship Graph Now"}
                  </span>
                </button>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-text-primary">
                  No entities found matching current filters.
                </p>
                <button
                  onClick={() => {
                    setActiveDomain("all");
                    setSearchQuery("");
                  }}
                  className="mt-2 px-4 py-2 rounded-lg bg-accent/10 hover:bg-accent/20 text-accent text-xs font-medium border border-accent/20 transition-colors cursor-pointer"
                >
                  Reset Filters ({rawNodes.length} Total Entities)
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="flex-1 w-full h-full">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onInit={setRfInstance}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={handleNodeClick}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.15}
              maxZoom={2.2}
            >
              <Background color="var(--border-subtle)" gap={24} size={1} />
              <Controls className="!bg-bg-secondary !border-border-default !rounded-xl overflow-hidden [&>button]:!bg-bg-secondary [&>button]:!border-b [&>button]:!border-border-default [&>button]:!text-text-primary hover:[&>button]:!bg-bg-tertiary" />
              <MiniMap
                nodeColor={(n: Node) => {
                  const nodeData = n.data as unknown as CustomNodeData;
                  const kind = nodeData?.node?.source_kind;
                  if (kind === "architecture") return "#10b981";
                  if (kind === "knowledge") return "#f59e0b";
                  return "#38bdf8";
                }}
                className="!bg-bg-secondary/90 !border-border-default !rounded-xl overflow-hidden !shadow-2xl"
              />
            </ReactFlow>
          </div>
        )}
      </div>

      {/* Slide-out Node Detail Drawer */}
      {selectedNode && (
        <GraphNodeDetails
          node={selectedNode}
          repoId={repositoryId}
          onClose={() => setSelectedNode(null)}
          onSelectNode={handleSelectAndCenterNode}
          onAnalyzeImpact={(node) => setImpactRootNode(node)}
          onAskAboutNode={(node) => {
            const prompt = `Explain the purpose, role, and callers of ${node.name} (${node.qualified_name || node.source_uri || node.node_type}) in this codebase.`;
            onAskCortex?.(prompt);
          }}
        />
      )}

      {/* Blast Radius Impact Modal */}
      {impactRootNode && (
        <ImpactPanel
          rootNode={impactRootNode}
          repoId={repositoryId}
          onClose={() => setImpactRootNode(null)}
          onAskAboutImpact={(question) => onAskCortex?.(question)}
          onSelectNode={handleSelectAndCenterNode}
          onImpactComputed={handleImpactComputed}
        />
      )}

      {/* Knowledge & Architectural Insights Modal */}
      {showInsights && (
        <GraphInsightsPanel
          repoId={repositoryId}
          onClose={() => setShowInsights(false)}
          onSelectNode={handleSelectAndCenterNode}
          onAskCortex={onAskCortex}
        />
      )}
    </div>
  );
}
