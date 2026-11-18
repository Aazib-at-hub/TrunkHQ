# TrunkHQ — Database Schema & Migration Strategy

**Date:** November 17, 2026  

---

## 1. Existing Implemented Schema (`001`–`004`)

- `users`: `id`, `email`, `username`, `hashed_password`, timestamps.
- `repositories`: `id`, `user_id`, `name`, `github_url`, `branch`, `description`, `tags`, `links`, `notes`, `status`, `file_count`, `chunk_count`.
- `files`: `id`, `repository_id`, `path`, `language`, `content_hash`, `line_count`.
- `code_chunks`: `id`, `file_id`, `repository_id`, `content`, `start_line`, `end_line`, `embedding` (`Vector(384)`, HNSW cosine + `tsvector` GIN).
- `conversations`, `messages`, `message_sources`: per-user chat history and chunk citations.
- `graph_nodes`, `graph_edges`, `graph_index_runs`: `workspace_id`, `repository_id`, `node_type`/`edge_type`, `stable_key`, `properties`, `source_kind`.

---

## 2. Planned Backward-Compatible Migrations

### Migration `005_multi_tenancy_orgs` (Phase 3)
- **New tables:**
  - `organizations` (`id`, `name`, `slug`, `account_type`, `owner_id`, `byok_encrypted_key`, `byok_provider`, timestamps)
  - `organization_members` (`id`, `organization_id`, `user_id`, `role` [`owner`/`admin`/`developer`/`viewer`], timestamps, unique `(organization_id, user_id)`)
  - `organization_invitations` (`id`, `organization_id`, `email`, `role`, `token_hash`, `expires_at`, `accepted_at`)
- **Non-destructive column additions & backfill:**
  - Add nullable `organization_id` (indexed FK `organizations.id`) to `repositories`, `conversations`, `graph_nodes`, `graph_edges`.
  - Backfill: create 1 personal `Organization` per existing `User`, insert `owner` membership, and set `organization_id` on existing `repositories`, `conversations`, and `graph_*` rows (`workspace_id = organization_id`).
  - Once backfilled, enforce `NOT NULL` on `organization_id`.

### Migration `006_projects_and_documents` (Phase 4 & 5)
- **New tables:**
  - `projects` (`id`, `organization_id`, `name`, `slug`, `description`, `category`, `tech_stack` JSONB, `created_by`, timestamps)
  - `documents` (`id`, `organization_id`, `project_id`, `title`, `file_name`, `mime_type`, `size_bytes`, `storage_key`, `status`, `error_message`, `version`, timestamps)
  - `document_chunks` (`id`, `organization_id`, `project_id`, `document_id`, `content`, `section_title`, `page_number`, `embedding` `Vector(384)`)
- **Backward-compatible backfill:**
  - Add `project_id` to `repositories`, `conversations`, `graph_nodes`, `graph_edges`.
  - Create 1 `Project` per existing `Repository` (using `repo.id` or linking `repo.project_id`) so existing `/projects/{id}` links continue resolving cleanly.

### Migration `007_billing_and_jobs` (Phase 9 & 10)
- **New tables:**
  - `plans` (`id`, `code`, `name`, `limits` JSONB, `features` JSONB)
  - `subscriptions` (`id`, `organization_id`, `plan_id`, `status`, `provider`, `provider_sub_id`, `current_period_end`)
  - `usage_records` (`id`, `organization_id`, `metric` [`ai_queries`, `tokens`, `repos`, `docs_bytes`], `quantity`, `period_start`)
  - `ingestion_jobs` (`id`, `organization_id`, `project_id`, `target_type`, `target_id`, `status`, `attempts`, `error_message`)
  - `audit_logs` (`id`, `organization_id`, `actor_user_id`, `action`, `target_type`, `target_id`, `metadata` JSONB, `created_at`)
