"use client";

import React, { useState, useEffect, useRef } from "react";
import { Send, Bot, User, ArrowLeft, RefreshCw, Sparkles, BookOpen, Network, MessageSquare, Zap, Loader2, AlertCircle, FolderOpen, FileText, History, Plus, Trash2 } from "lucide-react";
import { Button } from "../ui/button";
import { SourceCard } from "./SourceCard";
import { SourceViewerModal } from "../source-viewer/SourceViewerModal";
import { RelationshipGraph } from "../graph/RelationshipGraph";
import { ProjectDetailsPanel } from "../repository/ProjectDetailsPanel";
import { DocumentManagerPanel } from "../documents/DocumentManagerPanel";
import { useAuthStore } from "../../lib/store/auth";
import { chatApi, repoApi } from "../../lib/api/client";
import type { Conversation, Repository, RepositoryFile, Message } from "../../lib/api/types";

interface ChatInterfaceProps {
  repository: Repository;
  onBack: () => void;
  onRepoUpdated?: (updated: Repository) => void;
}

export function ChatInterface({ repository, onBack, onRepoUpdated }: ChatInterfaceProps) {
  const { user } = useAuthStore();
  const greetingCounterRef = useRef(0);
  const [activeTab, setActiveTab] = useState<"details" | "documents" | "chat" | "graph">("details");
  const [contextMode, setContextMode] = useState<"rag" | "graph_enhanced">("graph_enhanced");

  const [currentRepo, setCurrentRepo] = useState<Repository>(repository);
  const [reindexing, setReindexing] = useState(false);
  const [reindexError, setReindexError] = useState<string | null>(null);
  const [repoFiles, setRepoFiles] = useState<RepositoryFile[]>([]);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const isReady = currentRepo.status === "READY";
  const isFailed = currentRepo.status === "FAILED";
  const isProcessing = !isReady && !isFailed;

  const [messages, setMessages] = useState<Message[]>(() => {
    if (repository.status === "READY") {
      return [
        {
          id: "initial-assistant-greeting",
          role: "assistant",
          content: `Hello! I have indexed **${repository.name}** (${repository.file_count} files, ${repository.chunk_count} chunks). Ask me anything about the architecture, key algorithms, auth flows, or file locations. All responses cite exact lines in the repository.`,
          sources: [],
          created_at: new Date().toISOString(),
        },
      ];
    }
    return [];
  });

  const [inputQuestion, setInputQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Status Polling Effect
  useEffect(() => {
    let timer: NodeJS.Timeout;
    let isCancelled = false;

    const pollStatus = async () => {
      try {
        const res = await repoApi.getStatus(currentRepo.id);
        if (isCancelled) return;

        const hasChanged =
          currentRepo.status !== res.status ||
          currentRepo.file_count !== res.file_count ||
          currentRepo.chunk_count !== res.chunk_count;

        const nextRepo = {
          ...currentRepo,
          status: res.status,
          file_count: res.file_count,
          chunk_count: res.chunk_count,
        };
        setCurrentRepo(nextRepo);
        if (hasChanged) {
          onRepoUpdated?.(nextRepo);
        }

        if (res.status === "READY") {
          // Greet user if messages are empty
          setMessages((prev) => {
            if (prev.length === 0) {
              return [
                {
                  id: "initial-assistant-greeting",
                  role: "assistant",
                  content: `Hello! I have indexed **${currentRepo.name}** (${res.file_count} files, ${res.chunk_count} chunks). Ask me anything about the architecture, key algorithms, auth flows, or file locations. All responses cite exact lines in the repository.`,
                  sources: [],
                  created_at: new Date().toISOString(),
                },
              ];
            }
            return prev;
          });
        } else if (res.status !== "FAILED") {
          timer = setTimeout(pollStatus, 2500);
        }
      } catch {
        if (!isCancelled) {
          timer = setTimeout(pollStatus, 4000);
        }
      }
    };

    if (currentRepo.status !== "READY" && currentRepo.status !== "FAILED") {
      pollStatus();
    }

    return () => {
      isCancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [currentRepo.id, currentRepo.status, currentRepo.name]);

  // Source viewer modal state
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerData, setViewerData] = useState<{
    filePath: string;
    startLine: number;
    endLine: number;
    content?: string;
  }>({ filePath: "", startLine: 1, endLine: 1 });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const query = inputQuestion.trim();
    if (!query || loading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      sources: [],
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputQuestion("");
    setLoading(true);

    try {
      const response = await chatApi.askQuestion(repository.id, {
        question: query,
        conversation_id: conversationId,
        context_mode: contextMode,
      });

      setConversationId(response.conversation_id);
      setMessages((prev) => [...prev, response.message]);
    } catch (err: unknown) {
      const errMsg =
        err instanceof Error
          ? err.message
          : "Failed to generate answer. Ensure the repository has finished indexing.";

      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: `⚠️ **Error querying repository:** ${errMsg}`,
          sources: [],
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenSource = async (
    filePath: string,
    startLine: number,
    endLine: number
  ) => {
    setViewerData({
      filePath,
      startLine,
      endLine,
      content: "Loading source...",
    });
    setViewerOpen(true);

    try {
      let files = repoFiles;
      if (files.length === 0) {
        files = await repoApi.listFiles(currentRepo.id);
        setRepoFiles(files);
      }
      const match = files.find((f) => f.path === filePath);
      if (!match) {
        setViewerData({
          filePath,
          startLine,
          endLine,
          content: `// Could not locate '${filePath}' in indexed files.`,
        });
        return;
      }
      const detail = await repoApi.getFileDetail(currentRepo.id, match.id);
      setViewerData({
        filePath: detail.path,
        startLine,
        endLine,
        content: detail.content ?? "// Empty file.",
      });
    } catch (err: unknown) {
      setViewerData({
        filePath,
        startLine,
        endLine,
        content: `// Failed to load source: ${err instanceof Error ? err.message : "Unknown error"}`,
      });
    }
  };

  const loadConversations = async () => {
    setLoadingHistory(true);
    try {
      const list = await chatApi.listConversations(currentRepo.id);
      setConversations(list);
    } catch {
      // Ignore history load error
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleSelectConversation = async (convId: string) => {
    setHistoryOpen(false);
    try {
      const detail = await chatApi.getConversation(convId);
      setConversationId(detail.id);
      setMessages(detail.messages);
    } catch {
      // Ignore load error
    }
  };

  const handleNewChat = () => {
    greetingCounterRef.current += 1;
    setConversationId(null);
    setHistoryOpen(false);
    setMessages([
      {
        id: `greeting-${greetingCounterRef.current}`,
        role: "assistant",
        content: `Started a new conversation on **${currentRepo.name}**. Ask anything about the codebase.`,
        sources: [],
        created_at: new Date().toISOString(),
      },
    ]);
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await chatApi.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (conversationId === convId) {
        handleNewChat();
      }
    } catch {
      // Ignore delete error
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col bg-bg-primary">
      {/* Minimal Top Header */}
      <div className="flex h-14 items-center justify-between gap-3 border-b border-border-default bg-bg-secondary px-4 sm:px-6">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="text-text-secondary hover:text-text-primary gap-1 pl-1 shrink-0"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Projects</span>
          </Button>
          <div className="h-4 w-px bg-border-default shrink-0" />
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-semibold text-text-primary text-sm truncate">
              {currentRepo.name}
            </span>
            <span className="hidden md:inline font-mono text-xs text-text-tertiary">
              ({currentRepo.branch})
            </span>
            {isProcessing && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20 animate-pulse shrink-0">
                <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
                <span>{currentRepo.status}...</span>
              </span>
            )}
            {isFailed && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/10 text-rose-300 border border-rose-500/20 shrink-0">
                <AlertCircle className="w-3 h-3 text-rose-400" />
                <span>Failed</span>
              </span>
            )}
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="flex items-center gap-1 bg-bg-tertiary p-1 rounded-lg border border-border-default shrink-0">
          <button
            onClick={() => setActiveTab("details")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
              activeTab === "details"
                ? "bg-accent text-white shadow-sm"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <FolderOpen className="w-3.5 h-3.5" />
            <span>Details</span>
          </button>
          <button
            onClick={() => setActiveTab("documents")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
              activeTab === "documents"
                ? "bg-accent text-white shadow-sm"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Docs</span>
          </button>
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
              activeTab === "chat"
                ? "bg-accent text-white shadow-sm"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Chat</span>
          </button>
          <button
            onClick={() => setActiveTab("graph")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
              activeTab === "graph"
                ? "bg-accent text-white shadow-sm"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            <Network className="w-3.5 h-3.5" />
            <span>Graph</span>
          </button>
        </div>
      </div>

      {/* Main View Area */}
      {activeTab === "details" ? (
        <ProjectDetailsPanel
          repository={currentRepo}
          isOwner={Boolean(user && user.id === currentRepo.user_id)}
          onUpdated={(updated) => {
            setCurrentRepo(updated);
            onRepoUpdated?.(updated);
          }}
          onOpenFile={async (file: RepositoryFile) => {
            try {
              const detail = await repoApi.getFileDetail(currentRepo.id, file.id);
              setViewerData({
                filePath: detail.path,
                startLine: 1,
                endLine: detail.content ? detail.content.split("\n").length : 1,
                content: detail.content ?? "",
              });
              setViewerOpen(true);
            } catch {
              // Ignore load errors
            }
          }}
        />
      ) : activeTab === "documents" ? (
        <DocumentManagerPanel projectId={currentRepo.project_id || currentRepo.id} />
      ) : activeTab === "graph" ? (
        <div className="flex-1 min-h-0 overflow-hidden">
          <RelationshipGraph
            repositoryId={currentRepo.id}
            onAskCortex={(prompt) => {
              setActiveTab("chat");
              setInputQuestion(prompt);
            }}
          />
        </div>
      ) : (
        <>
          {/* Message List */}
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Processing Banner */}
          {isProcessing && (
            <div className="mx-auto max-w-md rounded-2xl border border-emerald-500/20 bg-gradient-to-b from-emerald-500/10 via-bg-secondary to-bg-secondary p-6 text-center shadow-lg my-8 space-y-4">
              <div className="relative mx-auto flex h-14 w-14 items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20 border-t-emerald-500 animate-spin" />
                <Bot className="h-6 w-6 text-emerald-400" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-text-primary">
                  Processing & Indexing Repository
                </h3>
                <p className="text-xs text-text-secondary">
                  {currentRepo.status === "CLONING" && "Cloning repository source tree from GitHub..."}
                  {currentRepo.status === "INDEXING" && "Extracting AST symbols, chunking source files, and calculating embeddings..."}
                  {currentRepo.status !== "CLONING" && currentRepo.status !== "INDEXING" && "Preparing codebase and building knowledge graph..."}
                </p>
              </div>
              <div className="flex items-center justify-center gap-4 text-xs font-mono text-text-tertiary border-t border-border-default/60 pt-3">
                <span className="flex items-center gap-1.5">
                  <BookOpen className="h-3.5 w-3.5 text-emerald-400" />
                  {currentRepo.file_count} files
                </span>
                <span>•</span>
                <span className="flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                  {currentRepo.chunk_count} chunks
                </span>
              </div>
            </div>
          )}

          {/* Failed Banner */}
          {isFailed && (
            <div className="mx-auto max-w-md rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 text-center my-8 space-y-3">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-500/10 text-rose-400">
                <AlertCircle className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold text-text-primary">Indexing Failed</h3>
              <p className="text-xs text-rose-300">
                Could not complete codebase indexing. Please check your GitHub repository URL or retry.
              </p>
              <Button
                variant="secondary"
                size="sm"
                isLoading={reindexing}
                onClick={async () => {
                  setReindexing(true);
                  setReindexError(null);
                  try {
                    await repoApi.reindex(currentRepo.id);
                    setCurrentRepo((prev) => ({ ...prev, status: "PENDING" }));
                  } catch (e) {
                    setReindexError(e instanceof Error ? e.message : "Failed to retry indexing.");
                  } finally {
                    setReindexing(false);
                  }
                }}
                className="mt-2 text-xs"
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Retry Indexing
              </Button>
              {reindexError && (
                <p className="text-xs text-rose-300 mt-1">{reindexError}</p>
              )}
            </div>
          )}

          {messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
              >
                {!isUser && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-600/10 border border-emerald-500/20 text-emerald-400">
                    <Bot className="h-4 w-4" />
                  </div>
                )}

                <div
                  className={`flex flex-col space-y-2 max-w-[85%] ${
                    isUser ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      isUser
                        ? "bg-emerald-600 text-white rounded-br-sm"
                        : "bg-bg-secondary border border-border-default text-text-primary rounded-bl-sm"
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>

                  {/* Sources section */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="w-full space-y-1.5 pt-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
                        Referenced Sources ({msg.sources.length})
                      </span>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {msg.sources.map((src, i) => (
                          <SourceCard
                            key={i}
                            source={src}
                            onViewSource={handleOpenSource}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  <span className="text-[10px] text-text-tertiary px-1">
                    {new Date(msg.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>

                {isUser && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-bg-tertiary border border-border-default text-text-secondary">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            );
          })}

          {loading && (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600/10 border border-emerald-500/20 text-emerald-400">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-2 rounded-2xl border border-border-default bg-bg-secondary px-4 py-2.5 text-xs text-text-secondary">
                <RefreshCw className="h-3.5 w-3.5 animate-spin text-emerald-400" />
                <span>Searching codebase embeddings & formulating response...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Form with RAG Mode + History */}
      <div className="relative border-t border-border-default bg-bg-secondary p-4">
        {historyOpen && (
          <div className="mx-auto mb-3 max-w-4xl rounded-xl border border-border-default bg-bg-tertiary p-3 shadow-xl space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-text-primary">Conversation History</span>
              <button
                type="button"
                onClick={handleNewChat}
                className="inline-flex items-center gap-1 rounded-md bg-emerald-500/15 px-2 py-1 text-[11px] font-medium text-emerald-300 hover:bg-emerald-500/25"
              >
                <Plus className="h-3 w-3" /> New Chat
              </button>
            </div>
            {loadingHistory ? (
              <p className="text-xs text-text-tertiary py-2">Loading conversations...</p>
            ) : conversations.length === 0 ? (
              <p className="text-xs text-text-tertiary py-2">No past conversations for this project yet.</p>
            ) : (
              <div className="max-h-48 overflow-y-auto divide-y divide-border-default/50">
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => handleSelectConversation(conv.id)}
                    className={`flex items-center justify-between gap-2 py-2 px-2 rounded-lg cursor-pointer text-xs hover:bg-bg-elevated ${
                      conversationId === conv.id ? "bg-emerald-500/10 text-emerald-300" : "text-text-secondary"
                    }`}
                  >
                    <span className="truncate">{conv.title || "Untitled conversation"}</span>
                    <button
                      type="button"
                      onClick={(e) => handleDeleteConversation(conv.id, e)}
                      aria-label="Delete conversation"
                      className="rounded p-1 text-text-tertiary hover:text-rose-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <form
          onSubmit={handleSend}
          className="mx-auto flex max-w-4xl items-center gap-2"
        >
          <button
            type="button"
            onClick={() => {
              const next = !historyOpen;
              setHistoryOpen(next);
              if (next) loadConversations();
            }}
            title="Conversation history"
            className="flex h-10 items-center gap-1.5 rounded-xl border border-border-default bg-bg-primary px-3 text-xs text-text-secondary hover:text-text-primary transition-colors shrink-0"
          >
            <History className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">History</span>
          </button>

          <button
            type="button"
            onClick={() =>
              setContextMode((prev) => (prev === "rag" ? "graph_enhanced" : "rag"))
            }
            className={`flex h-10 items-center gap-1.5 rounded-xl border px-3 text-xs font-medium transition-all shrink-0 ${
              contextMode === "graph_enhanced"
                ? "bg-sky-500/10 text-sky-300 border-sky-500/30"
                : "bg-bg-primary text-text-tertiary border-border-default hover:text-text-primary"
            }`}
            title="Toggle between Vector RAG and Graph-Enhanced RAG"
          >
            {contextMode === "graph_enhanced" ? (
              <Network className="w-3.5 h-3.5 text-sky-400" />
            ) : (
              <Zap className="w-3.5 h-3.5 text-amber-400" />
            )}
            <span className="hidden md:inline">
              {contextMode === "graph_enhanced" ? "Graph RAG" : "Vector RAG"}
            </span>
          </button>

          <input
            type="text"
            placeholder={
              isProcessing
                ? `Project is currently indexing (${currentRepo.status})... Chat will be enabled shortly.`
                : isFailed
                ? "Indexing failed. Please retry indexing above."
                : `Ask a question about ${currentRepo.name}...`
            }
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            disabled={loading || isProcessing || isFailed}
            className="flex-1 rounded-xl border border-border-default bg-bg-primary px-4 py-2.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <Button
            type="submit"
            variant="primary"
            disabled={!inputQuestion.trim() || loading || isProcessing || isFailed}
            isLoading={loading}
            className="h-10 px-4 rounded-xl"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
        </>
      )}

      {/* Source Viewer Modal */}
      <SourceViewerModal
        isOpen={viewerOpen}
        onClose={() => setViewerOpen(false)}
        filePath={viewerData.filePath}
        startLine={viewerData.startLine}
        endLine={viewerData.endLine}
        codeContent={viewerData.content}
      />
    </div>
  );
}
