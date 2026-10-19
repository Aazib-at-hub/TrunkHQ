/**
 * Cortex Engineering — Graph Layout & Physics Engine.
 *
 * Implements high-performance force-directed relaxation, collision avoidance,
 * and modular clustering for organic, readable graph visualizations.
 */

import type { GraphNode, GraphEdge } from "../../types/graph";

export interface NodePosition {
  x: number;
  y: number;
}

export type LayoutMode = "organic" | "hierarchical";

interface SimNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  cluster: string;
  degree: number;
}

export interface NodeConnectivityMap {
  inDegree: Map<string, number>;
  outDegree: Map<string, number>;
  neighbors: Map<string, Set<string>>;
}

/**
 * Pre-computes fast lookup maps for degree and direct 1-hop adjacency.
 */
export function computeConnectivity(
  nodes: GraphNode[],
  edges: GraphEdge[]
): NodeConnectivityMap {
  const inDegree = new Map<string, number>();
  const outDegree = new Map<string, number>();
  const neighbors = new Map<string, Set<string>>();

  for (const n of nodes) {
    inDegree.set(n.id, 0);
    outDegree.set(n.id, 0);
    neighbors.set(n.id, new Set<string>());
  }

  for (const e of edges) {
    if (neighbors.has(e.source_node_id) && neighbors.has(e.target_node_id)) {
      outDegree.set(e.source_node_id, (outDegree.get(e.source_node_id) || 0) + 1);
      inDegree.set(e.target_node_id, (inDegree.get(e.target_node_id) || 0) + 1);
      neighbors.get(e.source_node_id)!.add(e.target_node_id);
      neighbors.get(e.target_node_id)!.add(e.source_node_id);
    }
  }

  return { inDegree, outDegree, neighbors };
}

/**
 * Force-Directed Organic Network Layout with Collision Avoidance & Cluster Gravitation.
 */
export function computeOrganicForceLayout(
  nodes: GraphNode[],
  edges: GraphEdge[],
  width: number = 1400,
  height: number = 900
): Map<string, NodePosition> {
  if (nodes.length === 0) return new Map();

  const { inDegree, outDegree } = computeConnectivity(nodes, edges);

  // Derive cluster identity for each node (directory or domain)
  const getCluster = (n: GraphNode) => {
    if (n.source_kind === "architecture") return "arch";
    if (n.source_kind === "knowledge") return "know";
    if (n.source_uri) {
      const parts = n.source_uri.split("/");
      return parts.length > 1 ? parts[0] + "/" + (parts[1] || "") : parts[0];
    }
    return "code";
  };

  const clusters = Array.from(new Set(nodes.map(getCluster)));
  const clusterAngles = new Map<string, number>();
  clusters.forEach((c, idx) => {
    clusterAngles.set(c, (idx / Math.max(1, clusters.length)) * Math.PI * 2);
  });

  // Dynamically scale simulation bounds with node count so large graphs don't collapse into a clump
  const scale = Math.max(1, Math.sqrt(nodes.length / 16));
  const simWidth = Math.max(width, width * scale);
  const simHeight = Math.max(height, height * scale);

  const clusterRadius = Math.min(simWidth, simHeight) * 0.42;
  const centerX = simWidth / 2;
  const centerY = simHeight / 2;

  // Initialize nodes in cluster rings with jitter
  const simNodes: SimNode[] = nodes.map((n, i) => {
    const cluster = getCluster(n);
    const angle = (clusterAngles.get(cluster) || 0) + ((i % 12) - 6) * 0.15;
    const dist = clusterRadius * (0.6 + ((i % 7) * 0.08));
    const totDegree = (inDegree.get(n.id) || 0) + (outDegree.get(n.id) || 0);

    return {
      id: n.id,
      x: centerX + Math.cos(angle) * dist + ((i % 7) - 3) * 50,
      y: centerY + Math.sin(angle) * dist + ((i % 5) - 2) * 50,
      vx: 0,
      vy: 0,
      cluster,
      degree: totDegree,
    };
  });

  const nodeIndexMap = new Map<string, number>();
  simNodes.forEach((sn, idx) => nodeIndexMap.set(sn.id, idx));

  // Build edge pair indices
  const edgePairs: { s: number; t: number; weight: number }[] = [];
  for (const e of edges) {
    const s = nodeIndexMap.get(e.source_node_id);
    const t = nodeIndexMap.get(e.target_node_id);
    if (s !== undefined && t !== undefined && s !== t) {
      const isDefines = e.edge_type === "DEFINES";
      const isCalls = e.edge_type === "CALLS";
      const weight = isDefines ? 1.4 : isCalls ? 1.0 : 0.8;
      edgePairs.push({ s, t, weight });
    }
  }

  // Simulation parameters scaled for rectangular cards
  const iterations = Math.min(100, Math.max(50, Math.floor(nodes.length * 0.5)));
  const idealEdgeLength = 260;
  const cardRadius = 150; // Card separation threshold

  let temperature = 1.0;
  const coolingRate = 0.95;

  for (let iter = 0; iter < iterations; iter++) {
    // 1. Repulsion between all node pairs (strong collision push)
    for (let i = 0; i < simNodes.length; i++) {
      for (let j = i + 1; j < simNodes.length; j++) {
        const a = simNodes[i];
        const b = simNodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distSq = dx * dx + dy * dy || 0.01;
        const dist = Math.sqrt(distSq);

        const minDist = cardRadius * 2;
        let force = 0;
        if (dist < minDist) {
          // Strong collision separation when cards intersect
          force = ((minDist - dist) / minDist) * 26 * temperature;
        } else {
          // Normal Coulomb repulsion
          force = (4500 / distSq) * temperature;
        }

        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }

    // 2. Attraction along edges (Hooke's spring)
    for (const ep of edgePairs) {
      const a = simNodes[ep.s];
      const b = simNodes[ep.t];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;

      const displacement = dist - idealEdgeLength;
      const springForce = displacement * 0.035 * ep.weight * temperature;

      const fx = (dx / dist) * springForce;
      const fy = (dy / dist) * springForce;

      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }

    // 3. Cluster & Center Gravitation
    for (const n of simNodes) {
      // Cluster gravity
      const clusterAngle = clusterAngles.get(n.cluster) || 0;
      const targetClusterX = centerX + Math.cos(clusterAngle) * (clusterRadius * 0.85);
      const targetClusterY = centerY + Math.sin(clusterAngle) * (clusterRadius * 0.85);

      n.vx += (targetClusterX - n.x) * 0.015 * temperature;
      n.vy += (targetClusterY - n.y) * 0.015 * temperature;

      // Gentle center gravity (loose to avoid clumping)
      n.vx += (centerX - n.x) * 0.001 * temperature;
      n.vy += (centerY - n.y) * 0.001 * temperature;

      // Update positions with friction damping
      const maxSpeed = 35 * temperature;
      const speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
      if (speed > maxSpeed) {
        n.vx = (n.vx / speed) * maxSpeed;
        n.vy = (n.vy / speed) * maxSpeed;
      }

      n.x += n.vx;
      n.y += n.vy;
      n.vx *= 0.78;
      n.vy *= 0.78;
    }

    temperature *= coolingRate;
  }

  const result = new Map<string, NodePosition>();
  for (const sn of simNodes) {
    result.set(sn.id, {
      x: Math.round(sn.x),
      y: Math.round(sn.y),
    });
  }

  return result;
}

/**
 * Hierarchical Clustered Layout: Organizes nodes top-to-bottom by domain & dependencies.
 */
export function computeHierarchicalLayout(
  nodes: GraphNode[],
  edges: GraphEdge[]
): Map<string, NodePosition> {
  const result = new Map<string, NodePosition>();
  const { inDegree } = computeConnectivity(nodes, edges);

  const domainGroups: Record<string, GraphNode[]> = {
    architecture: [],
    code: [],
    knowledge: [],
  };

  for (const n of nodes) {
    const k = n.source_kind in domainGroups ? n.source_kind : "code";
    domainGroups[k].push(n);
  }

  const domainX: Record<string, number> = {
    architecture: 100,
    code: 520,
    knowledge: 1050,
  };

  for (const [dom, list] of Object.entries(domainGroups)) {
    // Sort so entrypoints / roots appear top, internal symbols below
    list.sort((a, b) => (inDegree.get(a.id) || 0) - (inDegree.get(b.id) || 0));

    const baseX = domainX[dom] || 500;
    list.forEach((n, idx) => {
      const col = idx % 2;
      const row = Math.floor(idx / 2);
      result.set(n.id, {
        x: baseX + col * 230,
        y: 80 + row * 110,
      });
    });
  }

  return result;
}
