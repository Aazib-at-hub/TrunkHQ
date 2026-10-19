# Cortex Engineering — Customer Pilot Readiness Checklist

## 1. Startup & Pilot Customer Onboarding Checklist

- [x] **Verified Git Authentication:** Safe public GitHub URL cloning with injection protection.
- [x] **Deterministic Line-Level Citations:** All RAG responses cite exact line ranges in indexed files.
- [x] **Zero Duplication on Reindex:** Reindexing safely updates codebase without polluting search results.
- [x] **Live Ingestion Progress:** Frontend shows step-by-step progress while repository is processing.
- [x] **Clean Frontend User Experience:** 0 linting errors, 0 runtime exceptions on main navigation and chat.
- [x] **AST Relationship Graph:** Interactive exploration of classes, functions, and architecture manifests.

---

## 2. Customer Demonstration Script

1. **Step 1: Sign in / Register**
   - Create or log into account. Observe system health badge: "System Online".
2. **Step 2: Import Repository**
   - Click **Import Repo**.
   - Input repository URL: `https://github.com/pallets/flask` (Branch: `main`).
   - Observe live status indicator transition: `PENDING` $\rightarrow$ `CLONING` $\rightarrow$ `INDEXING` $\rightarrow$ `READY`.
3. **Step 3: Grounded Architecture Q&A**
   - Ask: *"How does Flask handle request dispatching and error handling?"*
   - Observe the response citing exact line numbers in `src/flask/app.py`.
   - Click any source citation card to view the exact code snippet.
4. **Step 4: Explore the Relationship Graph**
   - Switch tab to **Relationship Graph**.
   - Toggle **Hierarchy** mode to view top-down module dependencies.
   - Click on an architectural endpoint or core class (e.g. `Flask`) to inspect 1-hop callers and blast radius.

---

## 3. Disclosed Limitations for Pilot Customers

1. **Repository Limits:** Currently recommended for repositories under 5,000 files / 250 MB.
2. **Private Repositories:** Requires supplying a GitHub Personal Access Token (`GITHUB_TOKEN`) with read permissions.
3. **Organization Management:** Pilots are provisioned as dedicated team workspaces. Multi-organization SAML SSO is slated for the Enterprise GA release.
