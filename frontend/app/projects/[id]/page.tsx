"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertCircle, ArrowLeft, Lock, RefreshCw } from "lucide-react";
import { Navbar } from "../../../components/Navbar";
import { AppShell } from "../../../components/layout/AppShell";
import { AuthModal } from "../../../components/auth/AuthModal";
import { ChatInterface } from "../../../components/chat/ChatInterface";
import { Button } from "../../../components/ui/button";
import { useAuthStore } from "../../../lib/store/auth";
import { repoApi } from "../../../lib/api/client";
import type { Repository } from "../../../lib/api/types";

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuthStore();

  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [repo, setRepo] = useState<Repository | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadProject = async () => {
    if (!params?.id || !user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await repoApi.getRepo(params.id);
      setRepo(data);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load project.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadProject();
    }, 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params?.id, user?.id]);

  const projectBody = loading ? (
    <div className="flex-1 flex flex-col items-center justify-center gap-3">
      <RefreshCw className="h-6 w-6 animate-spin text-emerald-400" />
      <p className="text-xs text-text-secondary">Loading project workspace...</p>
    </div>
  ) : errorMsg || !repo ? (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="max-w-md w-full rounded-2xl border border-rose-500/20 bg-bg-secondary p-8 text-center space-y-4">
        <AlertCircle className="mx-auto h-8 w-8 text-rose-400" />
        <h2 className="text-base font-semibold text-text-primary">Unable to load project</h2>
        <p className="text-xs text-text-secondary">{errorMsg || "Project not found."}</p>
        <div className="flex justify-center gap-2">
          <Button variant="outline" size="sm" onClick={() => router.push("/")}>
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Projects
          </Button>
          <Button variant="primary" size="sm" onClick={loadProject}>
            Retry
          </Button>
        </div>
      </div>
    </div>
  ) : (
    <ChatInterface
      repository={repo}
      onBack={() => router.push("/")}
      onRepoUpdated={(updated) => setRepo(updated)}
    />
  );

  return (
    <>
      {user ? (
        <AppShell pageTitle={repo?.name ?? "Project Workspace"}>
          {projectBody}
        </AppShell>
      ) : (
        <div className="min-h-screen flex flex-col bg-bg-primary text-text-primary">
          <Navbar onOpenAuth={() => setAuthModalOpen(true)} />
          <main className="flex-1 flex flex-col">
            <div className="flex-1 flex items-center justify-center p-6">
              <div className="max-w-md w-full rounded-2xl border border-border-default bg-bg-secondary p-8 text-center space-y-4">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <Lock className="h-5 w-5" />
                </div>
                <h2 className="text-lg font-semibold text-text-primary">Sign in to view project</h2>
                <p className="text-xs text-text-secondary">
                  TrunkHQ projects are shared within the authenticated workspace.
                </p>
                <div className="flex justify-center gap-2 pt-2">
                  <Button variant="outline" size="sm" onClick={() => router.push("/")}>
                    <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
                    Home
                  </Button>
                  <Button variant="primary" size="sm" onClick={() => setAuthModalOpen(true)}>
                    Sign In
                  </Button>
                </div>
              </div>
            </div>
          </main>
        </div>
      )}

      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </>
  );
}

