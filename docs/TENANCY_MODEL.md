# TrunkHQ — Multi-Tenancy Model

**Date:** November 17, 2026  

---

## 1. Tenancy Hierarchy

```
User
 └── OrganizationMember (role: owner | admin | developer | viewer)
      └── Organization (tenant boundary: personal | freelancer | agency | startup | enterprise)
           ├── Project (client engagement, product, or service group)
           │    ├── Repository[] -> File[] -> CodeChunk[]
           │    ├── Document[]   -> DocumentChunk[]
           │    ├── GraphNode[] / GraphEdge[]
           │    └── Conversation[] -> Message[] -> MessageSource[]
           └── Subscription & UsageRecords
```

---

## 2. Segment Mapping

| Customer Segment | How Tenancy Maps |
| :--- | :--- |
| **Individual Developer** | Auto-provisioned personal `Organization` (`account_type=individual`); private projects & repos. |
| **Freelancer** | 1 `Organization` with separate `Project` workspaces per client (or 1 `Organization` per client), zero context mixing. |
| **Software Agency** | Agency `Organization` with `OrganizationMember` invites, `Project`-level permissions, and client-isolated projects. |
| **Startup** | Company `Organization` with shared multi-repo `Project`s, shared onboarding Q&A, and architecture graphs. |
| **Enterprise / MNC** | Multiple `Organization`s / departments, strict RBAC, audit logs, SSO-ready identity hooks, and configurable quotas. |

---

## 3. Server-Side Authorization Matrix

| Action | `owner` | `admin` | `developer` | `viewer` |
| :--- | :---: | :---: | :---: | :---: |
| Manage billing & delete organization | Yes | No | No | No |
| Invite/remove members & assign roles | Yes | Yes | No | No |
| Create/update/delete projects & repos | Yes | Yes | Yes | No |
| Upload/delete documents & trigger reindex | Yes | Yes | Yes | No |
| Query AI chat & explore graph/files | Yes | Yes | Yes | Yes |

**Invariant:** Every backend query for `Project`, `Repository`, `File`, `CodeChunk`, `Document`, `DocumentChunk`, `GraphNode`, `GraphEdge`, and `Conversation` MUST include `organization_id == current_org.id` (verified via `OrganizationMember`).
