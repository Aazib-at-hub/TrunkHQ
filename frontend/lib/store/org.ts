"use client";

import { create } from "zustand";
import { orgApi } from "../api/client";
import type { Organization } from "../api/types";

interface OrgState {
  organizations: Organization[];
  activeOrgId: string | null;
  loading: boolean;
  loadOrgs: () => Promise<void>;
  setActiveOrg: (orgId: string) => void;
  createOrg: (name: string, accountType: string) => Promise<Organization>;
  clearOrgs: () => void;
}

export const useOrgStore = create<OrgState>((set, get) => ({
  organizations: [],
  activeOrgId:
    typeof window !== "undefined" ? localStorage.getItem("cortex_org_id") : null,
  loading: false,

  loadOrgs: async () => {
    set({ loading: true });
    try {
      const orgs = await orgApi.listOrgs();
      const storedId =
        typeof window !== "undefined" ? localStorage.getItem("cortex_org_id") : null;
      const validStored = orgs.some((o) => o.id === storedId) ? storedId : null;
      const nextOrgId = validStored ?? orgs[0]?.id ?? null;
      if (typeof window !== "undefined") {
        if (nextOrgId) localStorage.setItem("cortex_org_id", nextOrgId);
        else localStorage.removeItem("cortex_org_id");
      }
      set({ organizations: orgs, activeOrgId: nextOrgId, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  setActiveOrg: (orgId: string) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("cortex_org_id", orgId);
    }
    set({ activeOrgId: orgId });
  },

  createOrg: async (name: string, accountType: string) => {
    const created = await orgApi.createOrg({ name, account_type: accountType });
    const updated = [...get().organizations, created];
    if (typeof window !== "undefined") {
      localStorage.setItem("cortex_org_id", created.id);
    }
    set({ organizations: updated, activeOrgId: created.id });
    return created;
  },

  clearOrgs: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("cortex_org_id");
    }
    set({ organizations: [], activeOrgId: null });
  },
}));
