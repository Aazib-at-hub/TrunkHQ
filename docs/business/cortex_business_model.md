# TrunkHQ — Business Model & Commercialization Strategy

**Product:** TrunkHQ  
**Positioning:** Engineering Intelligence as a Service (EIaaS) — *One platform. Multiple repositories. Connected engineering knowledge.*  
**Model:** B2B SaaS + Usage-Based AI/Indexing + Enterprise Licensing  

---

## 1. Strategic Positioning

TrunkHQ is positioned as a **Cloud SaaS Project Knowledge & Onboarding Hub (Engineering Intelligence Platform)** — a centralized storage center for a team's projects so engineering teams stop wasting hours walking freshers and new hires through codebases and documentation.

**Core Value Proposition (Outcome-Driven):**
> TrunkHQ is the central project storage center for your engineering team: import your repositories once, and let new hires and developers get instant, citation-backed answers, architecture visibility, and dependency traces without spending hours reading raw code and scattered docs.

---

## 2. Target Customer Segments & Beachhead

| Segment | Core Problem | Cortex Offering | Priority |
| :--- | :--- | :--- | :--- |
| **Startups** | Tribal knowledge scattered across repos; slow developer onboarding | Shared engineering workspace, cited Q&A, architecture graph | **Primary Beachhead** |
| **Software Agencies** | Repeatedly inheriting and maintaining unfamiliar client codebases | Multi-project workspace, fast codebase discovery, impact analysis | **Primary Beachhead** |
| **Individual Developers** | Understanding open-source or unfamiliar repositories | Free/Pro personal code intelligence (acquisition funnel) | **PLG Funnel** |
| **Mid-Market & Enterprises** | Complex multi-repo architecture, security, compliance, and silos | Private/hybrid deployment, RBAC, SSO, audit logs, custom SLA | **Expansion Market** |

**Why Startups & Agencies First:**
- Short sales cycles with direct founder/CTO/engineering-lead decision-makers.
- High pain from developer onboarding and context-switching across client or service repositories.
- Matches Cortex's current **CONDITIONAL GO** readiness for dedicated single-org/team deployments.

---

## 3. Packaging & Launch Pricing (Indicative INR)

> *Note: Launch pricing below is indicative and requires willingness-to-pay validation with pilot customers.*

| Tier | Target | Indicative Price | Included Capabilities |
| :--- | :--- | :--- | :--- |
| **Free — Individual** | Developer acquisition | **₹0 / mo** | 1 repository, limited monthly AI queries, basic hybrid RAG search, line-level source citations, community support |
| **Pro — Individual** | Power / freelance devs | **₹499–999 / mo** | Multiple repositories, higher indexing limits, advanced Q&A, conversation history, relationship graph access |
| **Team** *(Core Revenue)* | Startups & Agencies | **₹2,999–7,999 / mo** | Shared engineering workspace, multiple repositories, team knowledge base, relationship & blast-radius graph, RBAC, usage dashboard, BYOK option |
| **Enterprise** | Mid-market & Enterprise | **₹2L–15L+ / yr** | Dedicated/private cloud or self-hosted deployment, SSO & audit logs, advanced RBAC, custom integrations, SLA & onboarding support |

**Pricing Guardrails:**
- **No per-question nickel-and-diming:** Include generous monthly AI query allowances per tier.
- **Usage-based expansion:** Meter overages on heavy indexing volume, vector storage, and excess AI inference.
- **Bring Your Own Key (BYOK):** Allow Team/Enterprise customers to supply their own Gemini/OpenAI keys to control inference spend while paying Cortex for the platform, indexing, and graph intelligence.

---

## 4. Revenue Architecture

1. **Recurring SaaS Subscriptions (Primary):** Monthly/annual Pro, Team, and Enterprise plans.
2. **Usage-Based Credits:** Additional indexing volume, storage, and AI inference beyond tier allowances.
3. **Enterprise Licensing:** Annual contracts for private-cloud or self-hosted deployments.
4. **Professional Services (Acquisition Enabler):** Paid pilots, custom repository/workflow setup, and integrations (kept secondary to recurring software revenue).

---

## 5. Commercial Rollout Aligned to Actual Codebase Readiness

Based on the [Executive Readiness Report](file:///c:/Users/SAQIB/Desktop/Cortex%20Engineering/docs/production-readiness/01_executive_readiness_report.md), Cortex's commercial rollout must align strictly with verified technical capabilities:

| Commercial Stage | Product Capabilities (Verified vs. Required) | Monetization |
| :--- | :--- | :--- |
| **Now — Controlled Pilots** | **Verified in V2:** GitHub ingestion, hybrid RAG (`pgvector` + `tsvector`), line-level citations, AST/TS relationship graph, shortest path & blast-radius impact, Day/Night UI, admin `/system` diagnostics. **Deployment constraint:** Provision 1 isolated instance per org (Project Storage House shares repos across users in an instance). | Paid Agency/Startup Pilots (`Team` tier) & Dedicated Single-Tenant Deployments |
| **Next — Self-Serve Cloud SaaS** | **Engineering Prerequisites:** Multi-tenant workspace/org isolation (`workspace_id` enforcement), per-tenant usage metering & quota enforcement, API rate limiting, BYOK runtime config, persistent background job queue. | `Free` PLG funnel -> `Pro` -> `Team` self-serve subscriptions |
| **Scale — Enterprise GA** | **Engineering Prerequisites:** SAML/OIDC SSO, immutable audit logs, cross-repository unified graph, CI/CD & issue-tracker integrations, non-root hardened containers & HA DB setup. | `Enterprise` annual licenses (₹2L–15L+ ACV) |

---

## 6. Go-To-Market (PLG + Founder-Led Sales)

1. **Product-Led Developer Funnel:** Free single-repo access drives bottom-up adoption among engineers.
2. **Agency Pilot Program:** Offer 30–60 day paid pilots for 1–2 client codebases demonstrating faster onboarding and safer refactoring via blast-radius analysis.
3. **Startup Founder/CTO Outreach:** Position around cutting engineer ramp-up time and preserving architecture context as teams scale.
4. **Enterprise Security-First Motion:** Controlled single-tenant pilots, private deployment option, and annual licensing.

---

## 7. Illustrative Revenue Projection (Not a Forecast)

| Segment | Customers | Avg. Monthly Price | Monthly Revenue |
| :--- | :---: | :---: | :---: |
| Pro Individual | 100 | ₹799 | ₹79,900 |
| Team (Startups & Agencies) | 15 | ₹4,999 | ₹74,985 |
| Enterprise | 2 | ₹25,000 | ₹50,000 |
| **Total Illustrative MRR** | **117** | — | **₹2,04,885** |

- **Illustrative ARR:** ~₹24.6 lakh/year (gross revenue before LLM inference, hosting, infrastructure, taxes, and operating expenses).

---

## 8. Competitive Positioning

| Competitor | Primary Focus | Cortex Differentiation |
| :--- | :--- | :--- |
| **Sourcegraph** | Code search & navigation at scale | Cortex pairs semantic + graph intelligence with accessible team onboarding & architecture Q&A for startups/agencies |
| **Glean** | Enterprise workplace/document search | Cortex is code- and architecture-native (AST graph, blast radius, line citations) |
| **LinearB / Swarmia** | Delivery metrics & DORA productivity | Cortex focuses on *system comprehension and architectural knowledge*, not developer surveillance/metrics |

---

## 9. Locked Strategic Decisions & Architectural Implications

1. **Delivery Model — Cloud SaaS (Hosted by Cortex):**
   - *Implication:* Multi-tenant organization/workspace isolation (`workspace_id` enforcement on repositories, files, chunks, and graph queries), rate limiting, usage metering, and durable background job queues are **mandatory P0/P1 engineering gates** before opening self-serve multi-tenant Cloud SaaS. Until then, onboard pilot teams on dedicated isolated cloud instances.
2. **Primary Paying Customer — Startups & Engineering Teams:**
   - *Implication:* Optimize UX, pricing (`Team` tier ₹2,999–7,999/mo), and sales around team workspaces, shared project libraries, and onboarding speed rather than individual-only tooling or heavy enterprise procurement.
3. **Product Category — Project Knowledge & Onboarding Storage Center:**
   - *Implication:* Keep the product focused on **fast repository storage, instant fresher/new-hire onboarding, cited Q&A, and visual dependency/architecture maps** — eliminating hours of manual codebase walkthroughs.
