/**
 * TrunkHQ — Graph API Client
 */

import { get, post } from "./client";
import type {
  FindPathResponse,
  GraphInsightsResponse,
  GraphNode,
  GraphSliceResponse,
  GraphStatusResponse,
  ImpactResponse,
  NodeNeighborsResponse,
} from "../../types/graph";

export const graphApi = {
  getGraph: (repoId: string, nodeTypes?: string[], limit: number = 300) => {
    const params = new URLSearchParams();
    if (nodeTypes && nodeTypes.length > 0) {
      nodeTypes.forEach((t) => params.append("node_types", t));
    }
    params.set("limit", limit.toString());
    return get<GraphSliceResponse>(`/api/v1/repositories/${repoId}/graph?${params.toString()}`);
  },

  getNode: (repoId: string, nodeId: string) =>
    get<GraphNode>(`/api/v1/repositories/${repoId}/graph/nodes/${nodeId}`),

  getNeighbors: (repoId: string, nodeId: string, direction: string = "both", limit: number = 100) =>
    get<NodeNeighborsResponse>(
      `/api/v1/repositories/${repoId}/graph/nodes/${nodeId}/neighbors?direction=${direction}&limit=${limit}`
    ),

  findPath: (repoId: string, sourceId: string, targetId: string, maxDepth: number = 5) =>
    post<FindPathResponse>(`/api/v1/repositories/${repoId}/graph/paths`, {
      source_id: sourceId,
      target_id: targetId,
      max_depth: maxDepth,
    }),

  getImpact: (
    repoId: string,
    nodeId: string,
    maxDepth: number = 3,
    edgeTypes?: string[],
    includeTests: boolean = true
  ) =>
    post<ImpactResponse>(`/api/v1/repositories/${repoId}/graph/impact`, {
      node_id: nodeId,
      max_depth: maxDepth,
      edge_types: edgeTypes,
      include_tests: includeTests,
    }),

  searchNodes: (repoId: string, query: string, nodeType?: string, limit: number = 20) => {
    const params = new URLSearchParams({ q: query, limit: limit.toString() });
    if (nodeType) params.set("node_type", nodeType);
    return get<GraphNode[]>(`/api/v1/repositories/${repoId}/graph/search?${params.toString()}`);
  },

  getStatus: (repoId: string) =>
    get<GraphStatusResponse>(`/api/v1/repositories/${repoId}/graph/status`),

  reindex: (repoId: string) =>
    post<GraphStatusResponse>(`/api/v1/repositories/${repoId}/graph/reindex`),

  getInsights: (repoId: string, topK: number = 10) =>
    get<GraphInsightsResponse>(`/api/v1/repositories/${repoId}/graph/insights?top_k=${topK}`),
};
