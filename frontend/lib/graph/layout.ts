/**
 * TrunkHQ — Graph Layout & Modular Clustering Physics Engine.
 *
 * Implements Graphify & CodeGraph-style macro clustering (Backend, Frontend,
 * Data & Models, Architecture & Knowledge) with isolated island physics,
 * dedicated compartments for unconnected nodes, and strict inter-cluster
 * anti-overlap collision resolution.
 */

import type { GraphNode, GraphEdge } from "../../types/graph";

export interface NodePosition {
  x: number;
  y: number;
}

export type LayoutMode = "organic" | "hierarchical";

export type MacroClusterId = "backend" | "frontend" | "data" | "architecture";

export interface MacroClusterMeta {
  id: MacroClusterId;
  label: string;
  shortLabel: string;
  tagline: string;
  color: {
    border: string;
    borderHighlight: string;
    bg: string;
    badgeBg: string;
    badgeText: string;
    accent: string;
    glow: string;
  };
  iconType: "server" | "layout" | "database" | "book";
}

export const CLUSTER_CONFIGS: Record<MacroClusterId, MacroClusterMeta> = {
  backend: {
    id: "backend",
    label: "Backend & API Services",
    shortLabel: "Backend",
    tagline: "API routes, business services, controllers & workers",
    color: {
      border: "rgba(56, 189, 248, 0.3)",
      borderHighlight: "rgba(56, 189, 248, 0.65)",
      bg: "rgba(14, 165, 233, 0.04)",
      badgeBg: "rgba(56, 189, 248, 0.12)",
      badgeText: "#7dd3fc",
      accent: "#38bdf8",
      glow: "rgba(56, 189, 248, 0.18)",
    },
    iconType: "server",
  },
  frontend: {
    id: "frontend",
    label: "Frontend & UI Layer",
    shortLabel: "Frontend",
    tagline: "React components, interfaces, routing & design system",
    color: {
      border: "rgba(129, 140, 248, 0.3)",
      borderHighlight: "rgba(129, 140, 248, 0.65)",
      bg: "rgba(99, 102, 241, 0.04)",
      badgeBg: "rgba(129, 140, 248, 0.12)",
      badgeText: "#a5b4fc",
      accent: "#818cf8",
      glow: "rgba(129, 140, 248, 0.18)",
    },
    iconType: "layout",
  },
  data: {
    id: "data",
    label: "Data, Storage & Models",
    shortLabel: "Data & Storage",
    tagline: "Database schemas, models, migrations & repositories",
    color: {
      border: "rgba(52, 211, 153, 0.3)",
      borderHighlight: "rgba(52, 211, 153, 0.65)",
      bg: "rgba(16, 185, 129, 0.04)",
      badgeBg: "rgba(52, 211, 153, 0.12)",
      badgeText: "#6ee7b7",
      accent: "#34d399",
      glow: "rgba(52, 211, 153, 0.18)",
    },
    iconType: "database",
  },
  architecture: {
    id: "architecture",
    label: "Architecture & Knowledge",
    shortLabel: "Architecture",
    tagline: "System specifications, requirements & domain docs",
    color: {
      border: "rgba(251, 191, 36, 0.3)",
      borderHighlight: "rgba(251, 191, 36, 0.65)",
      bg: "rgba(245, 158, 11, 0.04)",
      badgeBg: "rgba(251, 191, 36, 0.12)",
      badgeText: "#fcd34d",
      accent: "#fbbf24",
      glow: "rgba(251, 191, 36, 0.18)",
    },
    iconType: "book",
  },
};

export interface UnconnectedSection {
  x: number; // relative to cluster container top-left
  y: number;
  width: number;
  height: number;
}

export interface ClusterBounds {
  clusterId: MacroClusterId;
  cluster: MacroClusterMeta;
  x: number;
  y: number;
  width: number;
  height: number;
  nodeCount: number;
  connectedCount: number;
  unconnectedCount: number;
  unconnectedSection?: UnconnectedSection;
  nodeIds: string[];
}

export interface LayoutResult {
  positions: Map<string, NodePosition>;
  clusters: ClusterBounds[];
  nodeClusterMap: Map<string, MacroClusterId>;
  unconnectedNodeIds: Set<string>;
}

interface SimNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  cluster: MacroClusterId;
  degree: number;
}

export interface NodeConnectivityMap {
  inDegree: Map<string, number>;
  outDegree: Map<string, number>;
  neighbors: Map<string, Set<string>>;
}

/**
 * Pre-computes lookup maps for node degree and direct 1-hop adjacency.
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
 * Categorizes a node deterministically into one of 2-4 primary macro clusters.
 */
export function determineMacroCluster(node: GraphNode): MacroClusterId {
  // 1. Architecture & Knowledge specs
  if (
    node.source_kind === "architecture" ||
    node.source_kind === "knowledge" ||
    ["document", "requirement", "decision", "spec"].includes(node.node_type)
  ) {
    return "architecture";
  }

  const uri = (node.source_uri || "").toLowerCase().replace(/\\/g, "/");
  const qual = (node.qualified_name || "").toLowerCase();
  const name = node.name.toLowerCase();
  const type = node.node_type.toLowerCase();

  // 2. Data & Storage: Models, Schemas, Tables, Repositories, Migrations
  const isDataMatch =
    ["database", "table", "schema"].includes(type) ||
    uri.includes("/models/") ||
    uri.includes("/schemas/") ||
    uri.includes("/repositories/") ||
    uri.includes("/database/") ||
    uri.includes("/alembic/") ||
    uri.includes("/migrations/") ||
    uri.includes("/db/") ||
    uri.includes("prisma") ||
    qual.includes("models.") ||
    qual.includes("schemas.") ||
    qual.includes("repositories.") ||
    name.endsWith("repository") ||
    name.endsWith("schema") ||
    name.endsWith("model");

  if (isDataMatch) {
    return "data";
  }

  // 3. Frontend & UI Layer
  const isFrontendMatch =
    uri.startsWith("frontend/") ||
    uri.includes("/frontend/") ||
    uri.includes("/components/") ||
    uri.includes("/views/") ||
    uri.includes("/pages/") ||
    uri.endsWith(".tsx") ||
    uri.endsWith(".jsx") ||
    uri.endsWith(".css") ||
    uri.includes("tailwind") ||
    qual.includes("components.") ||
    ["component", "view", "page"].includes(type);

  if (isFrontendMatch) {
    return "frontend";
  }

  // 4. Backend & API Services (FastAPI, Python endpoints, controllers, services)
  return "backend";
}

/**
 * Calculates dynamic anchor centers for clusters with ample inter-cluster distance
 * based on estimated footprint of each cluster island.
 */
function getClusterAnchors(
  clusterFootprints: Map<MacroClusterId, { width: number; height: number; radius: number }>
): Map<MacroClusterId, { x: number; y: number }> {
  const anchors = new Map<MacroClusterId, { x: number; y: number }>();
  const activeIds = Array.from(clusterFootprints.keys());
  const count = activeIds.length;

  if (count <= 1) {
    if (count === 1) anchors.set(activeIds[0], { x: 0, y: 0 });
    return anchors;
  }

  let maxRadius = 500;
  for (const fp of clusterFootprints.values()) {
    maxRadius = Math.max(maxRadius, fp.radius);
  }

  // 2 Clusters: Left vs Right with substantial gap
  if (count === 2) {
    const r1 = clusterFootprints.get(activeIds[0])?.radius || 500;
    const r2 = clusterFootprints.get(activeIds[1])?.radius || 500;
    const span = r1 + r2 + 750;
    anchors.set(activeIds[0], { x: -Math.round(span / 2), y: 0 });
    anchors.set(activeIds[1], { x: +Math.round(span / 2), y: 0 });
    return anchors;
  }

  // 3 Clusters: Triangular constellation with generous orbit
  if (count === 3) {
    const orbit = Math.max(1500, Math.round(maxRadius * 1.8 + 650));
    const triangularSlots: Record<string, { x: number; y: number }> = {
      backend: { x: -Math.round(orbit * 0.95), y: -Math.round(orbit * 0.55) },
      frontend: { x: +Math.round(orbit * 0.95), y: -Math.round(orbit * 0.55) },
      data: { x: 0, y: +Math.round(orbit * 0.85) },
      architecture: { x: 0, y: -Math.round(orbit * 1.25) },
    };

    activeIds.forEach((id, idx) => {
      if (triangularSlots[id]) {
        anchors.set(id, triangularSlots[id]);
      } else {
        const angle = (idx / 3) * Math.PI * 2 - Math.PI / 2;
        anchors.set(id, {
          x: Math.round(Math.cos(angle) * orbit),
          y: Math.round(Math.sin(angle) * orbit),
        });
      }
    });
    return anchors;
  }

  // 4 Clusters: 2x2 Grid with huge gutters
  const stepX = Math.max(1400, Math.round(maxRadius * 1.6 + 600));
  const stepY = Math.max(1200, Math.round(maxRadius * 1.5 + 500));

  const gridSlots: Record<MacroClusterId, { x: number; y: number }> = {
    backend: { x: -stepX, y: -stepY },
    frontend: { x: +stepX, y: -stepY },
    data: { x: -stepX, y: +stepY },
    architecture: { x: +stepX, y: +stepY },
  };

  activeIds.forEach((id, idx) => {
    anchors.set(id, gridSlots[id] || {
      x: (idx % 2 === 0 ? -stepX : stepX),
      y: (Math.floor(idx / 2) === 0 ? -stepY : stepY),
    });
  });

  return anchors;
}

/**
 * Organic Force-Directed Layout with Island Cohesion, Dedicated Unconnected
 * Compartment, and Rigorous Anti-Overlap Collision Resolution.
 */
export function computeOrganicForceLayout(
  nodes: GraphNode[],
  edges: GraphEdge[]
): LayoutResult {
  if (nodes.length === 0) {
    return {
      positions: new Map(),
      clusters: [],
      nodeClusterMap: new Map(),
      unconnectedNodeIds: new Set(),
    };
  }

  const { inDegree, outDegree } = computeConnectivity(nodes, edges);

  // 1. Group nodes by cluster and partition into Connected vs Unconnected
  const nodeClusterMap = new Map<string, MacroClusterId>();
  const connectedByCluster = new Map<MacroClusterId, GraphNode[]>();
  const unconnectedByCluster = new Map<MacroClusterId, GraphNode[]>();
  const unconnectedNodeIds = new Set<string>();

  for (const n of nodes) {
    const c = determineMacroCluster(n);
    nodeClusterMap.set(n.id, c);

    if (!connectedByCluster.has(c)) connectedByCluster.set(c, []);
    if (!unconnectedByCluster.has(c)) unconnectedByCluster.set(c, []);

    const deg = (inDegree.get(n.id) || 0) + (outDegree.get(n.id) || 0);
    if (deg > 0) {
      connectedByCluster.get(c)!.push(n);
    } else {
      unconnectedByCluster.get(c)!.push(n);
      unconnectedNodeIds.add(n.id);
    }
  }

  const activeClusters = Array.from(
    new Set([...connectedByCluster.keys(), ...unconnectedByCluster.keys()])
  );

  // 2. Estimate footprints for each cluster to calculate non-overlapping anchors
  const clusterFootprints = new Map<
    MacroClusterId,
    { width: number; height: number; radius: number }
  >();

  for (const clusterId of activeClusters) {
    const connCount = (connectedByCluster.get(clusterId) || []).length;
    const unconnCount = (unconnectedByCluster.get(clusterId) || []).length;

    // Connected zone footprint
    const cCols = Math.max(2, Math.ceil(Math.sqrt(Math.max(1, connCount) * 1.6)));
    const cRows = Math.ceil(Math.max(1, connCount) / cCols);
    const cWidth = cCols * 290;
    const cHeight = cRows * 140;

    // Unconnected zone footprint
    const uCols = Math.max(2, Math.min(4, Math.ceil(Math.sqrt(Math.max(1, unconnCount) * 1.5))));
    const uRows = Math.ceil(Math.max(1, unconnCount) / uCols);
    const uWidth = unconnCount > 0 ? uCols * 280 : 0;
    const uHeight = unconnCount > 0 ? uRows * 130 + 80 : 0;

    const width = Math.max(650, Math.max(cWidth, uWidth) + 160);
    const height = Math.max(450, cHeight + (unconnCount > 0 ? uHeight + 100 : 0) + 160);
    const radius = Math.round(Math.max(width, height) / 2);

    clusterFootprints.set(clusterId, { width, height, radius });
  }

  const clusterAnchors = getClusterAnchors(clusterFootprints);

  // 3. Initialize ONLY connected nodes for organic force-directed physics
  const simNodes: SimNode[] = [];
  const nodeIndexMap = new Map<string, number>();

  for (const clusterId of activeClusters) {
    const connNodes = connectedByCluster.get(clusterId) || [];
    const anchor = clusterAnchors.get(clusterId) || { x: 0, y: 0 };
    const cols = Math.max(2, Math.ceil(Math.sqrt(Math.max(1, connNodes.length) * 1.6)));

    connNodes.forEach((n, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const startX = anchor.x + (col - cols / 2) * 280 + ((idx % 3) - 1) * 25;
      const startY = anchor.y + (row - Math.ceil(connNodes.length / cols) / 2) * 140 + ((idx % 2) - 0.5) * 20;

      const sn: SimNode = {
        id: n.id,
        x: startX,
        y: startY,
        vx: 0,
        vy: 0,
        cluster: clusterId,
        degree: (inDegree.get(n.id) || 0) + (outDegree.get(n.id) || 0),
      };
      nodeIndexMap.set(n.id, simNodes.length);
      simNodes.push(sn);
    });
  }

  // 4. Edges setup: Intra-cluster springs keep related code tight.
  // CRITICAL: Cross-cluster edges have very low stiffness so they NEVER pull islands together!
  const edgePairs: {
    s: number;
    t: number;
    isCrossCluster: boolean;
    weight: number;
  }[] = [];

  for (const e of edges) {
    const s = nodeIndexMap.get(e.source_node_id);
    const t = nodeIndexMap.get(e.target_node_id);
    if (s !== undefined && t !== undefined && s !== t) {
      const isCross = simNodes[s].cluster !== simNodes[t].cluster;
      // Very small weight for cross-cluster edges prevents cluster collapse
      const weight = isCross ? 0.005 : 1.2;
      edgePairs.push({ s, t, isCrossCluster: isCross, weight });
    }
  }

  // 5. Force Simulation Loop for Connected Nodes
  const iterations = Math.min(85, Math.max(40, Math.floor(simNodes.length * 0.45)));
  const cardMinDistX = 265;
  const cardMinDistY = 135;
  let temperature = 1.0;
  const coolingRate = 0.93;

  for (let iter = 0; iter < iterations; iter++) {
    // A. Inter-node collision repulsion
    for (let i = 0; i < simNodes.length; i++) {
      for (let j = i + 1; j < simNodes.length; j++) {
        const a = simNodes[i];
        const b = simNodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distSq = dx * dx + dy * dy || 0.01;
        const dist = Math.sqrt(distSq);

        const isSameCluster = a.cluster === b.cluster;

        if (isSameCluster) {
          const overlapX = cardMinDistX - Math.abs(dx);
          const overlapY = cardMinDistY - Math.abs(dy);

          if (overlapX > 0 && overlapY > 0) {
            const force = (Math.max(overlapX, overlapY) / 100) * 36 * temperature;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            a.vx -= fx;
            a.vy -= fy;
            b.vx += fx;
            b.vy += fy;
          } else if (dist < 420) {
            const force = (3200 / distSq) * temperature;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            a.vx -= fx;
            a.vy -= fy;
            b.vx += fx;
            b.vy += fy;
          }
        } else {
          // Strong inter-cluster buffer repulsion: keeps islands apart
          if (dist < 800) {
            const force = ((800 - dist) / 800) * 55 * temperature;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            a.vx -= fx;
            a.vy -= fy;
            b.vx += fx;
            b.vy += fy;
          }
        }
      }
    }

    // B. Edge Springs
    for (const ep of edgePairs) {
      const a = simNodes[ep.s];
      const b = simNodes[ep.t];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 0.01;

      if (!ep.isCrossCluster) {
        const displacement = dist - 240;
        const springForce = displacement * 0.045 * ep.weight * temperature;
        const fx = (dx / dist) * springForce;
        const fy = (dy / dist) * springForce;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }
    }

    // C. Cluster Anchor Centroid Gravitation
    for (const sn of simNodes) {
      const anchor = clusterAnchors.get(sn.cluster) || { x: 0, y: 0 };
      const cdx = anchor.x - sn.x;
      const cdy = anchor.y - sn.y;

      sn.vx += cdx * 0.042 * temperature;
      sn.vy += cdy * 0.042 * temperature;

      const maxSpeed = 32 * temperature;
      const speed = Math.sqrt(sn.vx * sn.vx + sn.vy * sn.vy);
      if (speed > maxSpeed) {
        sn.vx = (sn.vx / speed) * maxSpeed;
        sn.vy = (sn.vy / speed) * maxSpeed;
      }

      sn.x += sn.vx;
      sn.y += sn.vy;
      sn.vx *= 0.72;
      sn.vy *= 0.72;
    }

    temperature *= coolingRate;
  }

  // 6. Build initial positions map from connected simulation
  const positions = new Map<string, NodePosition>();
  for (const sn of simNodes) {
    positions.set(sn.id, {
      x: Math.round(sn.x),
      y: Math.round(sn.y),
    });
  }

  // 7. Place UNCONNECTED nodes in their dedicated compartment inside each cluster
  // Placed neatly below the connected network in an orderly, stable grid shelf
  const clusterUnconnectedSections = new Map<MacroClusterId, UnconnectedSection>();

  for (const clusterId of activeClusters) {
    const connNodes = connectedByCluster.get(clusterId) || [];
    const unconnNodes = unconnectedByCluster.get(clusterId) || [];
    const anchor = clusterAnchors.get(clusterId) || { x: 0, y: 0 };

    if (unconnNodes.length === 0) continue;

    // Determine bottom Y and center X of connected nodes in this cluster
    let connMinX = anchor.x - 200;
    let connMaxX = anchor.x + 200;
    let connMaxY = anchor.y - 50;

    if (connNodes.length > 0) {
      connMinX = Infinity;
      connMaxX = -Infinity;
      connMaxY = -Infinity;
      for (const n of connNodes) {
        const p = positions.get(n.id);
        if (p) {
          connMinX = Math.min(connMinX, p.x);
          connMaxX = Math.max(connMaxX, p.x + 250);
          connMaxY = Math.max(connMaxY, p.y + 110);
        }
      }
    }

    const centerX = Math.round((connMinX + connMaxX) / 2);
    const shelfStartY = connMaxY + 90; // Clean 90px separation gap

    // Grid columns: 2 to 4 columns depending on count
    const uCols = Math.max(2, Math.min(4, Math.ceil(Math.sqrt(unconnNodes.length * 1.5))));
    const cardStepX = 275;
    const cardStepY = 125;
    const totalGridWidth = (uCols - 1) * cardStepX + 250;
    const startX = Math.round(centerX - totalGridWidth / 2);

    let uMinX = Infinity;
    let uMaxX = -Infinity;
    let uMinY = Infinity;
    let uMaxY = -Infinity;

    unconnNodes.forEach((n, idx) => {
      const col = idx % uCols;
      const row = Math.floor(idx / uCols);
      const nx = startX + col * cardStepX;
      const ny = shelfStartY + 50 + row * cardStepY; // 50px top header gap for shelf badge

      positions.set(n.id, { x: nx, y: ny });

      uMinX = Math.min(uMinX, nx);
      uMaxX = Math.max(uMaxX, nx + 250);
      uMinY = Math.min(uMinY, ny);
      uMaxY = Math.max(uMaxY, ny + 110);
    });

    // Store raw absolute bounds of the unconnected compartment
    clusterUnconnectedSections.set(clusterId, {
      x: uMinX - 30,
      y: uMinY - 45,
      width: uMaxX - uMinX + 60,
      height: uMaxY - uMinY + 45 + 30,
    });
  }

  // 8. Compute Cluster Bounding Hulls (including connected web + dedicated unconnected shelf)
  const clusters: ClusterBounds[] = [];
  const paddingX = 75;
  const paddingTop = 95; // Room for cluster banner
  const paddingBottom = 60;

  for (const clusterId of activeClusters) {
    const connNodes = connectedByCluster.get(clusterId) || [];
    const unconnNodes = unconnectedByCluster.get(clusterId) || [];
    const allNodeIds = [...connNodes.map((n) => n.id), ...unconnNodes.map((n) => n.id)];

    if (allNodeIds.length === 0) continue;

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;

    for (const nid of allNodeIds) {
      const p = positions.get(nid);
      if (p) {
        minX = Math.min(minX, p.x);
        maxX = Math.max(maxX, p.x + 250);
        minY = Math.min(minY, p.y);
        maxY = Math.max(maxY, p.y + 110);
      }
    }

    const clusterX = Math.round(minX - paddingX);
    const clusterY = Math.round(minY - paddingTop);
    const width = Math.max(520, Math.round(maxX - minX + paddingX * 2));
    const height = Math.max(300, Math.round(maxY - minY + paddingTop + paddingBottom));

    // Convert raw unconnected shelf coordinates to relative coordinates inside cluster container
    let relUnconnSection: UnconnectedSection | undefined = undefined;
    const rawShelf = clusterUnconnectedSections.get(clusterId);
    if (rawShelf) {
      relUnconnSection = {
        x: Math.round(rawShelf.x - clusterX),
        y: Math.round(rawShelf.y - clusterY),
        width: Math.round(rawShelf.width),
        height: Math.round(rawShelf.height),
      };
    }

    clusters.push({
      clusterId,
      cluster: CLUSTER_CONFIGS[clusterId],
      x: clusterX,
      y: clusterY,
      width,
      height,
      nodeCount: allNodeIds.length,
      connectedCount: connNodes.length,
      unconnectedCount: unconnNodes.length,
      unconnectedSection: relUnconnSection,
      nodeIds: allNodeIds,
    });
  }

  // 9. STRICT AABB ANTI-OVERLAP RESOLUTION ACROSS CLUSTERS
  // Iteratively checks for any overlap between cluster bounding boxes and pushes them apart
  const MIN_CLUSTER_GUTTER = 450; // Minimum 450px clear space between cluster boxes
  const maxOverlapPasses = 15;

  for (let pass = 0; pass < maxOverlapPasses; pass++) {
    let hadOverlap = false;

    for (let i = 0; i < clusters.length; i++) {
      for (let j = i + 1; j < clusters.length; j++) {
        const a = clusters[i];
        const b = clusters[j];

        // Compute AABB intersection with gutter
        const aLeft = a.x - MIN_CLUSTER_GUTTER / 2;
        const aRight = a.x + a.width + MIN_CLUSTER_GUTTER / 2;
        const aTop = a.y - MIN_CLUSTER_GUTTER / 2;
        const aBottom = a.y + a.height + MIN_CLUSTER_GUTTER / 2;

        const bLeft = b.x - MIN_CLUSTER_GUTTER / 2;
        const bRight = b.x + b.width + MIN_CLUSTER_GUTTER / 2;
        const bTop = b.y - MIN_CLUSTER_GUTTER / 2;
        const bBottom = b.y + b.height + MIN_CLUSTER_GUTTER / 2;

        const overlapX = Math.min(aRight, bRight) - Math.max(aLeft, bLeft);
        const overlapY = Math.min(aBottom, bBottom) - Math.max(aTop, bTop);

        if (overlapX > 0 && overlapY > 0) {
          hadOverlap = true;
          // Determine push direction along the axis of least overlap
          if (overlapX < overlapY) {
            const pushX = Math.round(overlapX / 2) + 20;
            const dirX = a.x + a.width / 2 < b.x + b.width / 2 ? -1 : 1;

            // Shift cluster A and all its nodes
            a.x += dirX * pushX;
            for (const nid of a.nodeIds) {
              const p = positions.get(nid);
              if (p) p.x += dirX * pushX;
            }

            // Shift cluster B and all its nodes
            b.x -= dirX * pushX;
            for (const nid of b.nodeIds) {
              const p = positions.get(nid);
              if (p) p.x -= dirX * pushX;
            }
          } else {
            const pushY = Math.round(overlapY / 2) + 20;
            const dirY = a.y + a.height / 2 < b.y + b.height / 2 ? -1 : 1;

            a.y += dirY * pushY;
            for (const nid of a.nodeIds) {
              const p = positions.get(nid);
              if (p) p.y += dirY * pushY;
            }

            b.y -= dirY * pushY;
            for (const nid of b.nodeIds) {
              const p = positions.get(nid);
              if (p) p.y -= dirY * pushY;
            }
          }
        }
      }
    }

    if (!hadOverlap) break;
  }

  return { positions, clusters, nodeClusterMap, unconnectedNodeIds };
}

/**
 * Hierarchical Clustered Layout: Organizes nodes top-to-bottom in distinct cluster columns
 * with connected nodes on top and a dedicated standalone shelf at the bottom.
 */
export function computeHierarchicalLayout(
  nodes: GraphNode[],
  edges: GraphEdge[]
): LayoutResult {
  const positions = new Map<string, NodePosition>();
  const { inDegree, outDegree } = computeConnectivity(nodes, edges);

  const nodeClusterMap = new Map<string, MacroClusterId>();
  const connectedByCluster = new Map<MacroClusterId, GraphNode[]>();
  const unconnectedByCluster = new Map<MacroClusterId, GraphNode[]>();
  const unconnectedNodeIds = new Set<string>();

  for (const n of nodes) {
    const c = determineMacroCluster(n);
    nodeClusterMap.set(n.id, c);
    if (!connectedByCluster.has(c)) connectedByCluster.set(c, []);
    if (!unconnectedByCluster.has(c)) unconnectedByCluster.set(c, []);

    const deg = (inDegree.get(n.id) || 0) + (outDegree.get(n.id) || 0);
    if (deg > 0) {
      connectedByCluster.get(c)!.push(n);
    } else {
      unconnectedByCluster.get(c)!.push(n);
      unconnectedNodeIds.add(n.id);
    }
  }

  const activeClusters = Array.from(
    new Set([...connectedByCluster.keys(), ...unconnectedByCluster.keys()])
  );
  const columnWidth = 660;
  const columnGutter = 350; // Proper distance between columns
  const clusters: ClusterBounds[] = [];

  activeClusters.forEach((clusterId, colIdx) => {
    const connNodes = connectedByCluster.get(clusterId) || [];
    const unconnNodes = unconnectedByCluster.get(clusterId) || [];
    const allNodeIds = [...connNodes.map((n) => n.id), ...unconnNodes.map((n) => n.id)];

    connNodes.sort((a, b) => (inDegree.get(a.id) || 0) - (inDegree.get(b.id) || 0));

    const totalWidth = activeClusters.length * (columnWidth + columnGutter) - columnGutter;
    const baseX = colIdx * (columnWidth + columnGutter) - totalWidth / 2;
    const baseY = 0;

    // 1. Layout connected nodes in top half
    let maxConnY = baseY + 80;
    connNodes.forEach((n, idx) => {
      const col = idx % 2;
      const row = Math.floor(idx / 2);
      const nx = baseX + col * 280 + 50;
      const ny = baseY + 100 + row * 125;
      maxConnY = Math.max(maxConnY, ny + 95);
      positions.set(n.id, { x: nx, y: ny });
    });

    // 2. Layout unconnected nodes in dedicated shelf below
    let relUnconnSection: UnconnectedSection | undefined = undefined;
    let maxTotalY = maxConnY;

    if (unconnNodes.length > 0) {
      const shelfY = maxConnY + 80;
      let uMinX = Infinity;
      let uMaxX = -Infinity;
      let uMinY = Infinity;
      let uMaxY = -Infinity;

      unconnNodes.forEach((n, idx) => {
        const col = idx % 2;
        const row = Math.floor(idx / 2);
        const nx = baseX + col * 280 + 50;
        const ny = shelfY + 50 + row * 125;

        positions.set(n.id, { x: nx, y: ny });

        uMinX = Math.min(uMinX, nx);
        uMaxX = Math.max(uMaxX, nx + 250);
        uMinY = Math.min(uMinY, ny);
        uMaxY = Math.max(uMaxY, ny + 95);
      });

      maxTotalY = uMaxY + 30;

      relUnconnSection = {
        x: Math.round(uMinX - 25 - baseX),
        y: Math.round(uMinY - 45 - baseY),
        width: Math.round(uMaxX - uMinX + 50),
        height: Math.round(uMaxY - uMinY + 45 + 25),
      };
    }

    clusters.push({
      clusterId,
      cluster: CLUSTER_CONFIGS[clusterId],
      x: baseX,
      y: baseY,
      width: columnWidth,
      height: Math.max(300, maxTotalY - baseY + 50),
      nodeCount: allNodeIds.length,
      connectedCount: connNodes.length,
      unconnectedCount: unconnNodes.length,
      unconnectedSection: relUnconnSection,
      nodeIds: allNodeIds,
    });
  });

  return { positions, clusters, nodeClusterMap, unconnectedNodeIds };
}
