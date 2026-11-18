# TrunkHQ — UI/UX Review & Simplification Plan

> **Inspection Note:** Live Chrome DevTools inspection could not connect (`DevToolsActivePort` not enabled on this machine). Findings below are based on reviewing the implemented Next.js components and layout code across `frontend/app/` and `frontend/components/`.

---

## Goal

Make TrunkHQ feel **calm, obvious, and effortless** as a shared **Project Storage House**—so anyone can find a project, read its details, browse its files, or ask a question without visual noise or extra steps.

---

## What Works Well Today

- **Cohesive dark-first palette:** `frontend/app/globals.css` uses consistent slate surfaces (`--bg-primary`, `--bg-secondary`, `--bg-tertiary`) and restrained indigo accents.
- **Clear indexing feedback:** `RepoCard.tsx` and `ChatInterface.tsx` communicate background states (`PENDING`, `CLONING`, `INDEXING`, `READY`, `FAILED`) clearly.
- **Unified project workspace:** Keeping `Chat & RAG`, `Relationship Graph`, and `Project Details` inside one project view avoids scattering users across disconnected pages.

---

## Friction Points & How to Simplify

### 1. Duplicate CTAs & Mixed Terminology (`Navbar.tsx`, `page.tsx`)
- **Current state:** When signed in, both `Navbar.tsx` (`Import Repo`) and `page.tsx` (`Store Project`) render primary indigo buttons for the exact same action. Labels also mix *"Repository"*, *"Repo"*, and *"Project"*.
- **Why it feels hectic:** Two competing primary buttons draw attention to the same action, and mixed terms force users to guess if a "Repo" and a "Project" are different things.
- **Recommendation:**
  - Keep **one** primary `Store Project` button in the dashboard toolbar and remove the duplicate `Import Repo` button from `Navbar.tsx`.
  - Standardize on **Project** across UI copy, modals, and buttons.
  - Replace the always-visible `System Online` / `DB healthy` pill in the navbar with a subtle status dot inside the user menu or footer (only surface a banner when the backend is actually offline).

### 2. No Direct Project URLs (`app/page.tsx`)
- **Current state:** Clicking a project sets `selectedRepo` in React state on `app/page.tsx` instead of navigating to a route like `/projects/[id]`.
- **Why it feels hectic:** Browser Back/Forward does not work, refreshing the page kicks the user back to the dashboard, and teammates cannot share a direct link to a project's details or files.
- **Recommendation:** Add a Next.js route `frontend/app/projects/[id]/page.tsx` so every stored project has a shareable, bookmarkable URL.

### 3. Crowded Workspace Header (`ChatInterface.tsx`)
- **Current state:** The top bar inside a project packs 7 items into one row: `Back`, project title, status badge, 3-tab switcher, `Graph-Enhanced RAG` / `Vector RAG` toggle, file count, and chunk count.
- **Why it feels hectic:** On laptops or split-screen windows, the bar feels dense and mixes navigation with chat-specific settings.
- **Recommendation:**
  - Keep the workspace header minimal: **Back** | **Project Name + Status** | **Tabs (`Details`, `Chat`, `Graph`)**.
  - Move the `Vector RAG / Graph-Enhanced RAG` toggle next to the chat input box where it is actually used.
  - Keep file and chunk counts inside the `Project Details` tab rather than repeating them in the global header.

### 4. Project Details Should Be Effortless to Reach (`ChatInterface.tsx`, `ProjectDetailsPanel.tsx`)
- **Current state:** Opening any project lands on `Chat & RAG` first, with `Project Details` as the third tab.
- **Why it matters:** For a **Project Storage House**, many visitors open a project just to check its description, links, notes, owner, or browse a file.
- **Recommendation:**
  - Place `Details` as the first tab (`Details` | `Chat` | `Graph`) or remember the user's last-opened tab.
  - Add a **Copy GitHub URL** button and a quick **Ask AI about this file** action inside `SourceViewerModal.tsx` when viewing a file.

### 5. Past Conversations Are Not Surfaced (`ChatInterface.tsx`)
- **Current state:** `chatApi.listConversations` exists in `frontend/lib/api/client.ts`, but `ChatInterface.tsx` starts a fresh greeting every time a project is opened.
- **Recommendation:** Add a compact **History** dropdown button in the chat header/composer so users can resume previous Q&A threads without cluttering the screen with a permanent sidebar.

### 6. Graph Controls Overwhelm First-Time Viewers (`RelationshipGraph.tsx`)
- **Current state:** The graph view exposes domain filters, cluster filters, layout mode switches, neighborhood focus, insights drawer, impact panel, and node details around the canvas.
- **Recommendation:**
  - Start with a clean canvas showing only **Search** and **Node Type** pills.
  - Group layout mode, cluster filters, and insights behind a single **View Options** popover.

### 7. Native Browser `alert()` / `confirm()` Dialogs (`app/page.tsx`)
- **Current state:** Deleting a project triggers native `window.confirm()` and `window.alert()`, which clash with the app's custom `Modal` design.
- **Recommendation:** Use a small, consistent confirmation modal (or inline "Click again to confirm" button state) for destructive actions.

### 8. Unauthenticated Landing State (`app/page.tsx`)
- **Current state:** The "View Documentation" button links to `https://github.com` instead of real docs or a live preview.
- **Recommendation:** Link to the actual repository/docs or remove the dead-end button so the primary action is simply **Sign In to Browse Projects**.

---

## Prioritized Action Plan (Low Effort, High Impact)

| Priority | Change | Effort | Impact |
| :--- | :--- | :--- | :--- |
| 1 | Remove duplicate `Import Repo` button in `Navbar.tsx` and unify "Project" naming | Small | Cleaner header, less confusion |
| 2 | Simplify `ChatInterface.tsx` header (move RAG mode toggle to chat input, counts to Details) | Small | Much calmer workspace bar |
| 3 | Put `Details` as first tab in `ChatInterface.tsx` | Small | Immediate access to project info |
| 4 | Add `/projects/[id]` route for shareable links & browser Back support | Medium | Essential for team storage house |
| 5 | Add compact **History** dropdown in Chat using `chatApi.listConversations` | Medium | Preserves Q&A context |
| 6 | Replace `confirm()`/`alert()` with custom confirm UI | Small | Consistent polish |
| 7 | Tuck advanced Graph controls into a **View Options** menu | Medium | Less visual clutter on graph load |

