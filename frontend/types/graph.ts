/**
 * Cortex Engineering — Relationship Graph Type Definitions
 */

export type NodeDomain = "all" | "code" | "architecture" | "knowledge";

export type NodeType =
  | "repository"
  | "directory"
  | "file"
  | "module"
  | "class"
  | "function"
  | "method"
  | "symbol"
  | "test"
  | "service"
  | "api_endpoint"
  | "database"
  | "table"
  | "queue"
  | "external_system"
  | "deployment"
  | "config"
  | "document"
  | "requirement"
  | "decision"
  | "issue"
  | "commit"
  | "pull_request"
  | "incident";

export type EdgeType =
  | "CONTAINS"
  | "DEFINES"
  | "IMPORTS"
  | "CALLS"
  | "INHERITS"
  | "IMPLEMENTS"
  | "TESTS"
  | "DEPENDS_ON"
  | "EXPOSES"
  | "READS_FROM"
  | "WRITES_TO"
  | "IMPLEMENTS_REQUIREMENT"
  | "DOCUMENTS"
  | "INTRODUCED_BY"
  | "TRACKED_BY"
  | "SUPERSEDES";

export interface GraphNode {
  id: string;
  node_type: NodeType | string;
  stable_key: string;
  name: string;
  qualified_name?: string | null;
  description?: string | null;
  properties: Record<string, unknown>;
  source_kind: "code" | "architecture" | "knowledge" | string;
  source_uri?: string | null;
  created_at?: string | null;
}

export interface GraphEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: EdgeType | string;
  confidence: number;
  evidence_kind: string;
  source_uri?: string | null;
  properties: Record<string, unknown>;
}

export interface GraphSliceResponse {
  repository_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface NodeNeighborsResponse {
  node: GraphNode | null;
  outgoing_edges: GraphEdge[];
  incoming_edges: GraphEdge[];
  neighbors: GraphNode[];
}

export interface PathStep {
  node?: GraphNode | null;
  edge?: GraphEdge | null;
}

export interface FindPathResponse {
  found: boolean;
  length: number;
  steps: PathStep[];
}

export interface ImpactResponse {
  root: GraphNode | null;
  impacted_nodes: GraphNode[];
  edges: GraphEdge[];
  depth_levels: Record<string, number>;
  total_impacted: number;
}

export interface GraphStatusResponse {
  repository_id: string;
  status: string;
  nodes_count: number;
  edges_count: number;
  nodes_deleted: number;
  edges_deleted: number;
  error_summary?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface HubNodeInsight {
  node: GraphNode;
  in_degree: number;
  out_degree: number;
  total_degree: number;
  role: string;
}

export interface KeyModuleInsight {
  module: string;
  entity_count: number;
}

export interface GraphInsightsResponse {
  repository_id: string;
  total_nodes: number;
  total_edges: number;
  domains: Record<string, number>;
  hub_nodes: HubNodeInsight[];
  entrypoints: HubNodeInsight[];
  key_modules: KeyModuleInsight[];
}

