# 01. TrunkHQ V2 — UI/UX Audit

> **Scope:** Complete screen-by-screen audit of `frontend/app/` and `frontend/components/` against V2 goals (Linear simplicity, Cursor developer ergonomics, GitHub exploration, Neo4j Bloom graph clarity, and system observability).

---

## 1. Current Screen & Component Inventory

| Surface | Implementation | Current Role |
| :--- | :--- | :--- |
| **Root Shell & Providers** | `frontend/app/layout.tsx`, `frontend/app/providers.tsx` | Mounts `Geist` fonts and `QueryClientProvider` (React Query is unused). |
| **Landing / Command Center** | `frontend/app/page.tsx` | Single-page SPA: unauthenticated hero OR authenticated Project Storage House grid OR active `<ChatInterface>`. |
| **Global Navigation** | `frontend/components/Navbar.tsx` | Brand header, subtle backend health dot, and user menu / Sign In. |
| **Auth Modal** | `frontend/components/auth/AuthModal.tsx` | Sign-in and registration dialog using `components/ui/modal.tsx`. |
| **Store Project Modal** | `frontend/components/repository/ImportRepoModal.tsx` | GitHub URL, branch, description, tags, and notes form. |
| **Project Card** | `frontend/components/repository/RepoCard.tsx` | Card with status badge, description, up to 4 tags, counts, owner, and owner-only delete. |
| **Project Workspace** | `frontend/components/chat/ChatInterface.tsx` | Header + 3 tabs (`chat`, `graph`, `details`), polling, and RAG prompt form. |
| **Project Details & Files** | `frontend/components/repository/ProjectDetailsPanel.tsx` | Metadata viewer/editor (`description`, `tags`, `links`, `notes`) + searchable file list. |
| **Source Viewer** | `frontend/components/source-viewer/SourceViewerModal.tsx` | Syntax-highlighted code modal (`react-syntax-highlighter` / `vscDarkPlus`) + copy button. |
| **Knowledge Graph** | `frontend/components/graph/RelationshipGraph.tsx` (+ `GraphToolbar`, `GraphNodeDetails`, `CustomNode`, `ClusterGroupNode`, `ImpactPanel`, `GraphInsightsPanel`) | `@xyflow/react` canvas with organic/hierarchical layouts, neighborhood focus, blast-radius modal, and insights modal. |

---

## 2. Critical UI/UX Bugs & Broken States

1. **Chat Source Citations Show Stub Text Instead of Real Code**
   - `frontend/components/chat/ChatInterface.tsx:170-182` (`handleOpenSource`) passes a 2-line placeholder comment (`// Source Citation: ... // Loaded from semantic vector match in pgvector`) to `SourceViewerModal` instead of fetching real source content.
   - Meanwhile, `ProjectDetailsPanel` (`ChatInterface.tsx:299-312`) fetches real code via `repoApi.getFileDetail`.
2. **Broken Light-Mode Contrast**
   - `frontend/app/globals.css:80-108` switches `--text-primary` to `#0f172a` under `@media (prefers-color-scheme: light)`, while `ChatInterface.tsx:220`, `RelationshipGraph.tsx`, `GraphToolbar.tsx`, `GraphNodeDetails.tsx`, `GraphInsightsPanel.tsx`, `ImpactPanel.tsx`, and `CustomNode.tsx` hardcode dark hex backgrounds (`#1a1b25`, `#101118`, `#171822`). Users on light OS themes see dark text on dark surfaces.
3. **Spinners That Never Display & Swallowed Errors**
   - `frontend/app/page.tsx:29,34-60`: `loadingRepos` initializes to `false` and is never set to `true`; API errors are swallowed, showing *"No repositories found"* on network/auth failure.
   - `frontend/components/graph/GraphNodeDetails.tsx:36-57`: `loading` initializes to `false` and is never set to `true` when `node` changes, hiding the neighbor spinner (`line 177`).
   - `frontend/components/graph/ImpactPanel.tsx:45-47`: `getImpact` errors only log to `console`, leaving the modal blank.
4. **No URL Routing or Browser History**
   - `selectedRepo`, `activeTab`, and `conversationId` live in component state on `frontend/app/page.tsx`. Refreshing loses context; browser Back/Forward does not work; teammates cannot share direct project URLs (`/projects/[id]`).
5. **Layout & Responsive Overflows**
   - `frontend/components/chat/ChatInterface.tsx:187-288`: Sub-header (`h-14`) packs Back button, title, status badge, 3 tabs, RAG mode toggle, and file/chunk counts into a single non-wrapping row.
   - `frontend/components/graph/RelationshipGraph.tsx:407`: Uses `h-[calc(100vh-64px)]` inside `ChatInterface` (`h-[calc(100vh-4rem)]`), ignoring the `56px` `ChatInterface` header and clipping the bottom of the canvas.
   - `frontend/components/graph/GraphNodeDetails.tsx:66`: Inline `w-84 md:w-96` drawer squeezes the graph canvas on narrow viewports.
6. **Stale State & Native Browser Dialogs**
   - `ChatInterface.tsx:52-102` updates `currentRepo` during polling without calling `onRepoUpdated`, leaving the dashboard list stale.
   - `page.tsx:88,98`, `ChatInterface.tsx:378`, and `RelationshipGraph.tsx:119` use native `confirm()` / `alert()`.
7. **Accessibility & Copy Inconsistencies**
   - Clickable `<div>` elements in `RepoCard.tsx:34`, `SourceCard.tsx:28`, `GraphInsightsPanel.tsx:169,229`, and `GraphNodeDetails.tsx:195,232` lack `role="button"` and keyboard handlers; icon-only buttons lack `aria-label`.
   - `ImpactPanel.tsx` and `GraphInsightsPanel.tsx` bypass `components/ui/modal.tsx` (missing `Escape` close and scroll lock).
   - `page.tsx:182-190` "View Documentation" links to `https://github.com`.

---

## 3. Unexposed Backend Capabilities in UI

- **Conversation History (`chatApi.listConversations`, `getConversation`, `deleteConversation`)**: Implemented in `frontend/lib/api/client.ts:208-213` but never surfaced in `ChatInterface.tsx`.
- **Shortest Path Tracing (`graphApi.findPath`)**: Implemented in `frontend/lib/api/graph.ts:34-39` with no UI trigger.
- **Global Graph Search (`graphApi.searchNodes`)**: `GraphToolbar.tsx` only filters the first 450 client-side nodes.

---

## 4. V2 Screen-by-Screen Target Design

1. **A. Command Center (`/`)**: Unified project grid with search, tag/language filters, indexing status summary, recent activity, and a single `Store Project` CTA.
2. **B. Project Workspace (`/projects/[id]`)**: Shareable URL with `Details` (first tab) | `Chat` | `Graph`, plus a clean header (`Back | Project Name + Status | Tabs`).
3. **C. Intelligence Workspace (`Chat` tab)**: Collapsible conversation history drawer, RAG mode selector (`Vector` vs `Graph-Enhanced`) inside the prompt composer, and **real** source code previews when clicking citations.
4. **D. Knowledge Graph Explorer (`Graph` tab)**: Clean canvas on load (Search + Domain filter + `View Options` popover), inline path-finder (`From -> To`), blast-radius highlighting directly on the canvas, and confidence/evidence badges on edges.
5. **E. System Intelligence (`/system` or drawer)**: Indexing diagnostics, graph extraction stats, and health/config status in one dedicated place rather than cluttering project views.

