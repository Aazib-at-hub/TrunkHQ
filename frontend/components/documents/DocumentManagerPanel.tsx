"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FileText, Upload, Trash2, Eye, RefreshCw, AlertCircle } from "lucide-react";
import { documentApi } from "../../lib/api/client";
import type { ProjectDocument, ProjectDocumentDetail } from "../../lib/api/types";
import { Button } from "../ui/button";
import { Modal } from "../ui/modal";

interface DocumentManagerPanelProps {
  projectId: string;
}

export function DocumentManagerPanel({ projectId }: DocumentManagerPanelProps) {
  const [docs, setDocs] = useState<ProjectDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<ProjectDocumentDetail | null>(null);

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const list = await documentApi.listDocuments(projectId);
      setDocs(list);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load project documents.");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchDocs();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchDocs]);

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setErrorMsg(null);
    try {
      for (const file of Array.from(files)) {
        const uploaded = await documentApi.uploadDocument(projectId, file);
        setDocs((prev) => [uploaded, ...prev]);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to upload document.");
    } finally {
      setUploading(false);
    }
  };

  const handlePreview = async (docId: string) => {
    try {
      const detail = await documentApi.getDocument(projectId, docId);
      setPreviewDoc(detail);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load document preview.");
    }
  };

  const handleDelete = async (docId: string) => {
    try {
      await documentApi.deleteDocument(projectId, docId);
      setDocs((prev) => prev.filter((d) => d.id !== docId));
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to delete document.");
    }
  };

  return (
    <div className="mx-auto w-full max-w-5xl p-6 space-y-6 overflow-y-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border-default pb-4">
        <div>
          <h3 className="text-base font-bold text-text-primary">Project Documentation</h3>
          <p className="text-xs text-text-secondary mt-0.5">
            Upload SRS, PRDs, architecture docs, OpenAPI specs, or SQL schemas (.pdf, .docx, .md,
            .txt, .json, .yaml, .sql, .csv).
          </p>
        </div>

        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-medium text-white hover:bg-emerald-500 transition shrink-0">
          <Upload className="h-3.5 w-3.5" />
          <span>{uploading ? "Indexing..." : "Upload Document"}</span>
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.md,.txt,.csv,.json,.yaml,.yml,.sql"
            disabled={uploading}
            onChange={(e) => void handleFileUpload(e.target.files)}
            className="hidden"
          />
        </label>
      </div>

      {errorMsg && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-14 text-xs text-text-secondary gap-2">
          <RefreshCw className="h-4 w-4 animate-spin text-emerald-400" />
          <span>Loading documents...</span>
        </div>
      ) : docs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-default bg-bg-secondary/40 p-10 text-center space-y-2">
          <FileText className="h-8 w-8 text-text-tertiary mx-auto" />
          <p className="text-sm font-medium text-text-primary">No documents uploaded yet</p>
          <p className="text-xs text-text-secondary">
            Attach engineering specifications or architecture guides to index alongside your code.
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {docs.map((doc) => (
            <div
              key={doc.id}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-border-default bg-bg-secondary/70 p-4"
            >
              <div className="flex items-start gap-3 min-w-0">
                <FileText className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-text-primary truncate">{doc.title}</p>
                  <p className="text-[11px] font-mono text-text-tertiary truncate">
                    {doc.file_name} · {(doc.size_bytes / 1024).toFixed(1)} KB · {doc.chunk_count} chunks ·{" "}
                    <span className="text-emerald-400">{doc.status}</span>
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button variant="outline" size="sm" onClick={() => void handlePreview(doc.id)}>
                  <Eye className="h-3.5 w-3.5 mr-1" />
                  Preview
                </Button>
                <Button variant="ghost" size="sm" onClick={() => void handleDelete(doc.id)}>
                  <Trash2 className="h-3.5 w-3.5 text-rose-400" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        isOpen={Boolean(previewDoc)}
        onClose={() => setPreviewDoc(null)}
        title={previewDoc?.title ?? "Document Preview"}
        description={previewDoc?.file_name}
        maxWidth="lg"
      >
        <div className="max-h-96 overflow-y-auto space-y-3 pt-2">
          {previewDoc?.chunks.map((c) => (
            <div
              key={c.id}
              className="rounded-lg border border-border-default bg-bg-primary p-3 text-xs space-y-1"
            >
              <p className="font-mono text-[10px] text-emerald-400">
                Chunk #{c.chunk_index + 1}
                {c.page_number ? ` · Page ${c.page_number}` : ""}
              </p>
              <pre className="whitespace-pre-wrap font-sans text-text-secondary leading-relaxed">
                {c.content}
              </pre>
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
