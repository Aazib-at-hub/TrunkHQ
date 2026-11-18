"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/layout/AppShell";
import { Navbar } from "../../components/Navbar";
import { AuthModal } from "../../components/auth/AuthModal";
import { Button } from "../../components/ui/button";
import { orgApi } from "../../lib/api/client";
import type { AuditLogItem, OrganizationMember } from "../../lib/api/types";
import { useAuthStore } from "../../lib/store/auth";
import { useOrgStore } from "../../lib/store/org";
import { Users, UserPlus, Trash2, ShieldCheck, AlertCircle, RefreshCw } from "lucide-react";

export default function TeamPage() {
  const { user } = useAuthStore();
  const { organizations, activeOrgId } = useOrgStore();
  const [authModalOpen, setAuthModalOpen] = useState(false);

  const activeOrg = organizations.find((o) => o.id === activeOrgId) ?? organizations[0];
  const isOrgAdmin = activeOrg?.role === "owner" || activeOrg?.role === "admin";

  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "developer" | "viewer">("developer");
  const [adding, setAdding] = useState(false);

  const loadTeam = useCallback(async () => {
    if (!activeOrg?.id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const mList = await orgApi.listMembers(activeOrg.id);
      setMembers(mList);
      if (isOrgAdmin) {
        const aLogs = await orgApi.listAuditLogs(activeOrg.id);
        setLogs(aLogs);
      } else {
        setLogs([]);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load team members.");
    } finally {
      setLoading(false);
    }
  }, [activeOrg, isOrgAdmin]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadTeam();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadTeam]);

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeOrg?.id || !inviteEmail.trim()) return;
    setAdding(true);
    setErrorMsg(null);
    try {
      const added = await orgApi.addMember(activeOrg.id, {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      setMembers((prev) => [...prev, added]);
      setInviteEmail("");
      void loadTeam();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to add member.");
    } finally {
      setAdding(false);
    }
  };

  const handleRoleChange = async (userId: string, role: string) => {
    if (!activeOrg?.id) return;
    setErrorMsg(null);
    try {
      const updated = await orgApi.updateMemberRole(activeOrg.id, userId, role);
      setMembers((prev) => prev.map((m) => (m.user_id === userId ? updated : m)));
      void loadTeam();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to update role.");
    }
  };

  const handleRemove = async (userId: string) => {
    if (!activeOrg?.id) return;
    setErrorMsg(null);
    try {
      await orgApi.removeMember(activeOrg.id, userId);
      setMembers((prev) => prev.filter((m) => m.user_id !== userId));
      void loadTeam();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to remove member.");
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex flex-col bg-bg-primary text-text-primary">
        <Navbar onOpenAuth={() => setAuthModalOpen(true)} />
        <main className="flex-1 flex items-center justify-center p-6">
          <div className="max-w-md w-full rounded-2xl border border-border-default bg-bg-secondary p-8 text-center space-y-4">
            <Users className="h-9 w-9 text-emerald-400 mx-auto" />
            <h1 className="text-lg font-bold text-text-primary">Sign In Required</h1>
            <p className="text-xs text-text-secondary">
              Sign in to manage organization members, roles, and activity logs.
            </p>
            <Button variant="primary" size="md" onClick={() => setAuthModalOpen(true)}>
              Sign In
            </Button>
          </div>
        </main>
        <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      </div>
    );
  }

  return (
    <AppShell pageTitle="Team & Permissions">
      <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 space-y-6">
        <div className="flex items-center justify-between gap-4 border-b border-border-default pb-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-text-primary">
              {activeOrg?.name ?? "Organization"} · Team &amp; RBAC
            </h1>
            <p className="text-xs text-text-secondary mt-0.5">
              Manage workspace members, server-enforced roles, and organization audit history.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void loadTeam()} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {errorMsg && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Add Member (Owner/Admin only) */}
        {isOrgAdmin && (
          <form
            onSubmit={handleAddMember}
            className="rounded-xl border border-border-default bg-bg-secondary/70 p-4 flex flex-col sm:flex-row items-stretch sm:items-end gap-3"
          >
            <div className="flex-1">
              <label className="block text-[11px] font-medium text-text-secondary mb-1">
                Add Registered User by Email
              </label>
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="teammate@company.com"
                className="w-full rounded-lg border border-border-default bg-bg-primary px-3 py-2 text-xs text-text-primary placeholder:text-text-tertiary focus:border-emerald-500 focus:outline-none"
              />
            </div>
            <div className="sm:w-40">
              <label className="block text-[11px] font-medium text-text-secondary mb-1">
                Role
              </label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as "admin" | "developer" | "viewer")}
                className="w-full rounded-lg border border-border-default bg-bg-primary px-3 py-2 text-xs text-text-primary focus:border-emerald-500 focus:outline-none"
              >
                <option value="developer">Developer</option>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            <Button type="submit" variant="primary" size="sm" isLoading={adding} className="gap-1.5">
              <UserPlus className="h-3.5 w-3.5" />
              Add Member
            </Button>
          </form>
        )}

        {/* Members List */}
        <section className="rounded-xl border border-border-default bg-bg-secondary/60 overflow-hidden">
          <div className="border-b border-border-default px-4 py-3 text-xs font-semibold text-text-primary">
            Members ({members.length})
          </div>
          <div className="divide-y divide-border-default">
            {members.map((m) => (
              <div
                key={m.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 text-xs"
              >
                <div>
                  <p className="font-semibold text-text-primary">{m.username}</p>
                  <p className="text-text-tertiary">{m.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  {m.role === "owner" || !isOrgAdmin ? (
                    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase text-emerald-400">
                      {m.role}
                    </span>
                  ) : (
                    <>
                      <select
                        value={m.role}
                        onChange={(e) => void handleRoleChange(m.user_id, e.target.value)}
                        className="rounded-md border border-border-default bg-bg-primary px-2 py-1 text-xs text-text-primary"
                      >
                        <option value="admin">admin</option>
                        <option value="developer">developer</option>
                        <option value="viewer">viewer</option>
                      </select>
                      <button
                        type="button"
                        onClick={() => void handleRemove(m.user_id)}
                        title="Remove member"
                        className="rounded p-1.5 text-text-tertiary hover:bg-bg-tertiary hover:text-rose-400"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Audit Logs */}
        {isOrgAdmin && (
          <section className="rounded-xl border border-border-default bg-bg-secondary/60 overflow-hidden">
            <div className="border-b border-border-default px-4 py-3 text-xs font-semibold text-text-primary flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              Recent Organization Audit Logs
            </div>
            {logs.length === 0 ? (
              <p className="p-4 text-xs text-text-tertiary">No audit events recorded yet.</p>
            ) : (
              <div className="divide-y divide-border-default">
                {logs.map((log) => (
                  <div key={log.id} className="flex items-center justify-between px-4 py-2.5 text-xs">
                    <div>
                      <span className="font-mono font-semibold text-emerald-400">{log.action}</span>
                      {log.details && (
                        <span className="ml-2 text-text-secondary">
                          {JSON.stringify(log.details)}
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-[11px] text-text-tertiary">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </AppShell>
  );
}
