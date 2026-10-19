"use client";

import React, { useState, useEffect, useRef } from "react";
import { Send, Bot, User, ArrowLeft, RefreshCw, Sparkles, BookOpen, Network, MessageSquare, Zap, Loader2, AlertCircle } from "lucide-react";
import { Button } from "../ui/button";
import { SourceCard } from "./SourceCard";
import { SourceViewerModal } from "../source-viewer/SourceViewerModal";
import { RelationshipGraph } from "../graph/RelationshipGraph";
import { chatApi, repoApi } from "../../lib/api/client";
import type { Repository, Message } from "../../lib/api/types";

interface ChatInterfaceProps {
  repository: Repository;
  onBack: () => void;
}

export function ChatInterface({ repository, onBack }: ChatInterfaceProps) {
  const [activeTab, setActiveTab] = useState<"chat" | "graph">("chat");
  const [contextMode, setContextMode] = useState<"rag" | "graph_enhanced">("graph_enhanced");

  const [currentRepo, setCurrentRepo] = useState<Repository>(repository);
  const [reindexing, setReindexing] = useState(false);

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

        setCurrentRepo((prev) => ({
          ...prev,
          status: res.status,
          file_count: res.file_count,
          chunk_count: res.chunk_count,
        }));

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
      content: `// Source Citation: ${filePath} (lines ${startLine}-${endLine})\n// Loaded from semantic vector match in pgvector`,
    });
    setViewerOpen(true);
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col bg-bg-primary">
      {/* Top Header */}
      <div className="flex h-14 items-center justify-between border-b border-border-default bg-bg-secondary px-6">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="text-text-secondary hover:text-text-primary gap-1 pl-1"
          >
            <ArrowLeft className="h-4 w-4" /> Back to Repositories
          </Button>
          <div className="h-4 w-px bg-border-default" />
          <div className="flex items-center gap-2">
            <span className="font-semibold text-text-primary text-sm">
              {currentRepo.name}
            </span>
            <span className="font-mono text-xs text-text-tertiary">
              ({currentRepo.branch})
            </span>
            {isProcessing && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-300 border border-amber-500/20 animate-pulse ml-1">
                <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
                <span>{currentRepo.status}...</span>
              </span>
            )}
            {isFailed && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/10 text-rose-300 border border-rose-500/20 ml-1">
                <AlertCircle className="w-3 h-3 text-rose-400" />
                <span>Failed</span>
              </span>
            )}
          </div>

          {/* View Switcher Tabs */}
          <div className="flex items-center gap-1 bg-[#1a1b25] p-1 rounded-lg border border-border-default ml-4">
            <button
              onClick={() => setActiveTab("chat")}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                activeTab === "chat"
                  ? "bg-accent text-white shadow-sm"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Chat & RAG</span>
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
              <span>Relationship Graph</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-text-secondary">
          {activeTab === "chat" && (
            <button
              onClick={() =>
                setContextMode((prev) => (prev === "rag" ? "graph_enhanced" : "rag"))
              }
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-all ${
                contextMode === "graph_enhanced"
                  ? "bg-sky-500/10 text-sky-300 border-sky-500/30"
                  : "bg-white/5 text-text-tertiary border-border-default"
              }`}
              title="Toggle between standard vector RAG and graph-enhanced relationship retrieval"
            >
              {contextMode === "graph_enhanced" ? (
                <Network className="w-3.5 h-3.5 text-sky-400" />
              ) : (
                <Zap className="w-3.5 h-3.5 text-amber-400" />
              )}
              <span>{contextMode === "graph_enhanced" ? "Graph-Enhanced RAG" : "Vector RAG"}</span>
            </button>
          )}

          <div className="flex items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5 text-indigo-400" />
            <span>{currentRepo.file_count} files</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
            <span>{currentRepo.chunk_count} chunks</span>
          </div>
        </div>
      </div>

      {/* Main View Area */}
      {activeTab === "graph" ? (
        <RelationshipGraph
          repositoryId={currentRepo.id}
          onAskCortex={(prompt) => {
            setActiveTab("chat");
            setInputQuestion(prompt);
          }}
        />
      ) : (
        <>
          {/* Message List */}
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Processing Banner */}
          {isProcessing && (
            <div className="mx-auto max-w-md rounded-2xl border border-indigo-500/20 bg-gradient-to-b from-indigo-500/10 via-bg-secondary to-bg-secondary p-6 text-center shadow-lg my-8 space-y-4">
              <div className="relative mx-auto flex h-14 w-14 items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-indigo-500/20 border-t-indigo-500 animate-spin" />
                <Bot className="h-6 w-6 text-indigo-400" />
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
                  <BookOpen className="h-3.5 w-3.5 text-indigo-400" />
                  {currentRepo.file_count} files
                </span>
                <span>•</span>
                <span className="flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
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
                  try {
                    await repoApi.reindex(currentRepo.id);
                    setCurrentRepo((prev) => ({ ...prev, status: "PENDING" }));
                  } catch (e) {
                    alert("Reindex failed: " + (e instanceof Error ? e.message : "Unknown error"));
                  } finally {
                    setReindexing(false);
                  }
                }}
                className="mt-2 text-xs"
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Retry Indexing
              </Button>
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
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-600/10 border border-indigo-500/20 text-indigo-400">
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
                        ? "bg-indigo-600 text-white rounded-br-sm"
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
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/10 border border-indigo-500/20 text-indigo-400">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex items-center gap-2 rounded-2xl border border-border-default bg-bg-secondary px-4 py-2.5 text-xs text-text-secondary">
                <RefreshCw className="h-3.5 w-3.5 animate-spin text-indigo-400" />
                <span>Searching codebase embeddings & formulating response...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Form */}
      <div className="border-t border-border-default bg-bg-secondary p-4">
        <form
          onSubmit={handleSend}
          className="mx-auto flex max-w-4xl items-center gap-2"
        >
          <input
            type="text"
            placeholder={
              isProcessing
                ? `Repository is currently indexing (${currentRepo.status})... Chat will be enabled shortly.`
                : isFailed
                ? "Repository indexing failed. Please retry indexing above."
                : `Ask a question about ${currentRepo.name}... (e.g. How does error handling work?)`
            }
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            disabled={loading || isProcessing || isFailed}
            className="flex-1 rounded-xl border border-border-default bg-bg-primary px-4 py-2.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
