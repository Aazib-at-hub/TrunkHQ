/**
 * TrunkHQ — Base API Client
 *
 * Centralized HTTP client wrapping fetch. All API communication
 * goes through this module. Handles auth headers, error parsing,
 * and base URL configuration.
 */

import type { APIError } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Custom error class that carries the parsed API error response. */
export class ApiError extends Error {
  public code: string;
  public status: number;
  public details: unknown;

  constructor(status: number, error: APIError["error"]) {
    super(error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = error.code;
    this.details = error.details;
  }
}

/** Get the stored auth token from localStorage. */
function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("cortex_token");
}

/** Set the auth token in localStorage. */
export function setToken(token: string): void {
  localStorage.setItem("cortex_token", token);
}

/** Remove the auth token from localStorage. */
export function clearToken(): void {
  localStorage.removeItem("cortex_token");
}

/**
 * Core fetch wrapper with auth, error handling, and JSON parsing.
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (typeof window !== "undefined") {
    const activeOrgId = localStorage.getItem("cortex_org_id");
    if (activeOrgId) {
      headers["X-Organization-Id"] = activeOrgId;
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    const errorMsg =
      err instanceof Error
        ? err.message
        : "Failed to connect to backend server. Make sure FastAPI is running on http://localhost:8000.";
    throw new ApiError(503, {
      code: "NETWORK_ERROR",
      message: errorMsg,
      details: null,
    });
  }

  // Handle no-content responses
  if (response.status === 204) {
    return undefined as T;
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(response.status, {
      code: "PARSE_ERROR",
      message: `Server returned status ${response.status} with non-JSON response.`,
      details: null,
    });
  }

  if (!response.ok) {
    const apiError = data as APIError & {
      detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
    };
    if (apiError?.error) {
      throw new ApiError(response.status, apiError.error);
    }
    let detailMessage = "An unexpected error occurred";
    if (typeof apiError?.detail === "string") {
      detailMessage = apiError.detail;
    } else if (Array.isArray(apiError?.detail) && apiError.detail.length > 0) {
      detailMessage = apiError.detail
        .map((item) => {
          const field = item.loc?.slice(-1)[0];
          return field ? `${String(field)}: ${item.msg ?? "Invalid value"}` : item.msg ?? "Invalid value";
        })
        .join("; ");
    }
    throw new ApiError(response.status, {
      code: "VALIDATION_ERROR",
      message: detailMessage,
      details: apiError?.detail ?? null,
    });
  }

  return data as T;
}

/** HTTP GET */
export function get<T>(endpoint: string): Promise<T> {
  return request<T>(endpoint, { method: "GET" });
}

/** HTTP POST */
export function post<T>(endpoint: string, body?: unknown): Promise<T> {
  return request<T>(endpoint, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
}

/** HTTP PUT */
export function put<T>(endpoint: string, body?: unknown): Promise<T> {
  return request<T>(endpoint, {
    method: "PUT",
    body: body ? JSON.stringify(body) : undefined,
  });
}

/** HTTP PATCH */
export function patch<T>(endpoint: string, body?: unknown): Promise<T> {
  return request<T>(endpoint, {
    method: "PATCH",
    body: body ? JSON.stringify(body) : undefined,
  });
}

/** HTTP DELETE */
export function del<T>(endpoint: string): Promise<T> {
  return request<T>(endpoint, { method: "DELETE" });
}

// ── Typed API Helpers ────────────────────────────────────────────────────────

import type {
  ChatResponse,
  Conversation,
  ConversationDetail,
  FileDetail,
  HealthResponse,
  AuditLogItem,
  Organization,
  OrganizationMember,
  PlanItem,
  Project,
  ProjectDetail,
  ProjectDocument,
  ProjectDocumentDetail,
  Repository,
  RepositoryFile,
  SubscriptionDetail,
  TokenResponse,
  UpdateRepositoryPayload,
  User,
} from "./types";

export const authApi = {
  register: (body: { email: string; username: string; password: string }) =>
    post<User>("/api/v1/auth/register", body),
  login: (body: { email: string; password: string }) =>
    post<TokenResponse>("/api/v1/auth/login", body),
  logout: () => post<{ message: string }>("/api/v1/auth/logout"),
  getMe: () => get<User>("/api/v1/auth/me"),
  completeOnboarding: (body: { account_type: string; workspace_name?: string }) =>
    patch<User>("/api/v1/auth/onboarding", body),
};

export const orgApi = {
  listOrgs: () => get<Organization[]>("/api/v1/organizations"),
  createOrg: (body: { name: string; account_type: string }) =>
    post<Organization>("/api/v1/organizations", body),
  listMembers: (orgId: string) =>
    get<OrganizationMember[]>(`/api/v1/organizations/${orgId}/members`),
  addMember: (orgId: string, body: { email: string; role: string }) =>
    post<OrganizationMember>(`/api/v1/organizations/${orgId}/members`, body),
  updateMemberRole: (orgId: string, userId: string, role: string) =>
    patch<OrganizationMember>(`/api/v1/organizations/${orgId}/members/${userId}`, { role }),
  removeMember: (orgId: string, userId: string) =>
    del<{ message: string }>(`/api/v1/organizations/${orgId}/members/${userId}`),
  listAuditLogs: (orgId: string) =>
    get<AuditLogItem[]>(`/api/v1/organizations/${orgId}/audit-logs`),
};

export const billingApi = {
  listPlans: () => get<PlanItem[]>("/api/v1/billing/plans"),
  getSubscription: () => get<SubscriptionDetail>("/api/v1/billing/subscription"),
};

export const projectApi = {
  listProjects: () => get<Project[]>("/api/v1/projects"),
  createProject: (body: {
    name: string;
    description?: string;
    category?: string;
    tech_stack?: string[];
  }) => post<Project>("/api/v1/projects", body),
  getProject: (projectId: string) => get<ProjectDetail>(`/api/v1/projects/${projectId}`),
  updateProject: (
    projectId: string,
    body: { name?: string; description?: string; category?: string; tech_stack?: string[] }
  ) => patch<Project>(`/api/v1/projects/${projectId}`, body),
  attachRepo: (projectId: string, repoId: string) =>
    post<Repository>(`/api/v1/projects/${projectId}/repositories/${repoId}`),
  detachRepo: (projectId: string, repoId: string) =>
    del<void>(`/api/v1/projects/${projectId}/repositories/${repoId}`),
  deleteProject: (projectId: string) => del<void>(`/api/v1/projects/${projectId}`),
};

export const documentApi = {
  listDocuments: (projectId: string) =>
    get<ProjectDocument[]>(`/api/v1/projects/${projectId}/documents`),
  getDocument: (projectId: string, docId: string) =>
    get<ProjectDocumentDetail>(`/api/v1/projects/${projectId}/documents/${docId}`),
  deleteDocument: (projectId: string, docId: string) =>
    del<void>(`/api/v1/projects/${projectId}/documents/${docId}`),
  uploadDocument: async (projectId: string, file: File, title?: string): Promise<ProjectDocument> => {
    const formData = new FormData();
    formData.append("file", file);
    if (title?.trim()) formData.append("title", title.trim());

    const headers: Record<string, string> = {};
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (typeof window !== "undefined") {
      const orgId = localStorage.getItem("cortex_org_id");
      if (orgId) headers["X-Organization-Id"] = orgId;
    }

    const response = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/documents`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => null);
      if (errData?.error) throw new ApiError(response.status, errData.error);
      throw new ApiError(response.status, {
        code: "UPLOAD_ERROR",
        message: response.statusText || "Document upload failed",
        details: null,
      });
    }
    return (await response.json()) as ProjectDocument;
  },
};

export const repoApi = {
  importRepo: (body: {
    github_url: string;
    branch?: string;
    description?: string;
    tags?: string[];
    links?: Record<string, string>;
    notes?: string;
  }) => post<Repository>("/api/v1/repositories/import", body),
  listRepos: (params?: { search?: string; tag?: string; language?: string }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.tag) qs.set("tag", params.tag);
    if (params?.language) qs.set("language", params.language);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return get<Repository[]>(`/api/v1/repositories${suffix}`);
  },
  getRepo: (id: string) => get<Repository>(`/api/v1/repositories/${id}`),
  updateRepo: (id: string, body: UpdateRepositoryPayload) =>
    patch<Repository>(`/api/v1/repositories/${id}`, body),
  getStatus: (id: string) =>
    get<{
      id: string;
      status: Repository["status"];
      file_count: number;
      chunk_count: number;
      error_message: string | null;
      updated_at: string;
    }>(`/api/v1/repositories/${id}/status`),
  listFiles: (id: string) => get<RepositoryFile[]>(`/api/v1/repositories/${id}/files`),
  getFileDetail: (repoId: string, fileId: string) =>
    get<FileDetail>(`/api/v1/repositories/${repoId}/files/${fileId}`),
  reindex: (id: string) => post<Repository>(`/api/v1/repositories/${id}/reindex`),
  deleteRepo: (id: string) => del<void>(`/api/v1/repositories/${id}`),
};

export const chatApi = {
  askQuestion: (
    repoId: string,
    body: { question: string; conversation_id?: string | null; context_mode?: string }
  ) => post<ChatResponse>(`/api/v1/repositories/${repoId}/chat`, body),
  listConversations: (repoId: string) =>
    get<Conversation[]>(`/api/v1/repositories/${repoId}/conversations`),
  getConversation: (convId: string) =>
    get<ConversationDetail>(`/api/v1/conversations/${convId}`),
  deleteConversation: (convId: string) =>
    del<void>(`/api/v1/conversations/${convId}`),
};

export const healthApi = {
  checkHealth: () => get<HealthResponse>("/api/v1/health"),
};

