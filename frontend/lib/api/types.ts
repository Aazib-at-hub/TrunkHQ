/**
 * TrunkHQ — Shared TypeScript Types
 *
 * All API response types and domain models.
 * These mirror the backend Pydantic schemas.
 */

// ── User ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  username: string;
  is_admin?: boolean;
  account_type?: string;
  onboarding_completed?: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  account_type: string;
  owner_id: string;
  role: string;
  created_at: string;
}

export interface OrganizationMember {
  id: string;
  organization_id: string;
  user_id: string;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

export interface AuditLogItem {
  id: string;
  organization_id: string;
  actor_user_id: string;
  action: string;
  target_type: string;
  target_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface PlanItem {
  id: string;
  code: string;
  name: string;
  monthly_price_inr: number;
  annual_price_inr: number;
  limits: Record<string, number>;
  features: Record<string, boolean>;
  is_active: boolean;
}

export interface SubscriptionDetail {
  id: string;
  organization_id: string;
  status: string;
  billing_cycle: string;
  provider: string;
  current_period_end: string | null;
  plan: PlanItem;
  usage: Record<string, number>;
}

export interface Project {
  id: string;
  organization_id: string;
  created_by: string;
  name: string;
  slug: string;
  description: string | null;
  category: string;
  tech_stack: string[] | null;
  repository_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectDetail extends Project {
  repositories: Repository[];
}

export interface ProjectDocument {
  id: string;
  organization_id: string;
  project_id: string;
  uploaded_by: string;
  title: string;
  file_name: string;
  file_ext: string;
  mime_type: string;
  size_bytes: number;
  status: string;
  error_message: string | null;
  chunk_count: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunkItem {
  id: string;
  chunk_index: number;
  section_title: string | null;
  page_number: number | null;
  content: string;
}

export interface ProjectDocumentDetail extends ProjectDocument {
  chunks: DocumentChunkItem[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ── Repository ────────────────────────────────────────────────────────────────

export type RepositoryStatus =
  | "PENDING"
  | "CLONING"
  | "DISCOVERING"
  | "FILTERING"
  | "EXTRACTING"
  | "CHUNKING"
  | "EMBEDDING"
  | "INDEXING"
  | "READY"
  | "FAILED";

export interface Repository {
  id: string;
  user_id: string;
  organization_id?: string | null;
  project_id?: string | null;
  owner_username: string | null;
  name: string;
  github_url: string;
  branch: string;
  description: string | null;
  tags: string[] | null;
  links: Record<string, string> | null;
  notes: string | null;
  status: RepositoryStatus;
  file_count: number;
  chunk_count: number;
  languages: Record<string, number> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface UpdateRepositoryPayload {
  name?: string;
  description?: string | null;
  tags?: string[] | null;
  links?: Record<string, string> | null;
  notes?: string | null;
}

export interface RepositoryFile {
  id: string;
  path: string;
  filename: string;
  language: string;
  size_bytes: number;
}

export interface CodeChunk {
  id: string;
  chunk_index: number;
  start_line: number;
  end_line: number;
  language: string;
  content: string;
}

export interface FileDetail extends RepositoryFile {
  content: string | null;
  chunks: CodeChunk[];
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface Source {
  file_path: string;
  start_line: number;
  end_line: number;
  similarity_score: number | null;
  chunk_id: string | null;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  created_at: string;
}

export interface ChatResponse {
  conversation_id: string;
  message: Message;
}

export interface Conversation {
  id: string;
  repository_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail {
  id: string;
  repository_id: string;
  title: string | null;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

// ── Health ─────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
  database: string;
  embedding_provider: string;
  llm_provider: string;
}

// ── API Error ──────────────────────────────────────────────────────────────────

export interface APIError {
  error: {
    code: string;
    message: string;
    details: unknown;
  };
}
