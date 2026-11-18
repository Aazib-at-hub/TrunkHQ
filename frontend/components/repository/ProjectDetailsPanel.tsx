"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  ExternalLink,
  FileCode2,
  GitBranch,
  Link2,
  Pencil,
  Save,
  Search,
  Tag,
  User as UserIcon,
  X,
} from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { repoApi } from "../../lib/api/client";
import type { Repository, RepositoryFile } from "../../lib/api/types";

interface ProjectDetailsPanelProps {
  repository: Repository;
  isOwner: boolean;
  onUpdated: (updated: Repository) => void;
  onOpenFile: (file: RepositoryFile) => void;
}

export function ProjectDetailsPanel({
  repository,
  isOwner,
  onUpdated,
  onOpenFile,
}: ProjectDetailsPanelProps) {
  const [files, setFiles] = useState<RepositoryFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [fileQuery, setFileQuery] = useState("");

  const [editing, setEditing] = useState(false);
  const [description, setDescription] = useState(repository.description ?? "");
  const [tagsInput, setTagsInput] = useState((repository.tags ?? []).join(", "));
  const [notes, setNotes] = useState(repository.notes ?? "");
  const [linksInput, setLinksInput] = useState(() =>
    repository.links
      ? Object.entries(repository.links)
          .map(([k, v]) => `${k}: ${v}`)
          .join("\n")
      : ""
  );
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    let ignore = false;
    async function fetchFiles() {
      setLoadingFiles(true);
      try {
        const list = await repoApi.listFiles(repository.id);
        if (!ignore) setFiles(list);
      } catch {
        // Ignore if still indexing or unavailable
      } finally {
        if (!ignore) setLoadingFiles(false);
      }
    }
    fetchFiles();
    return () => {
      ignore = true;
    };
  }, [repository.id, repository.status]);

  const filteredFiles = useMemo(() => {
    const q = fileQuery.trim().toLowerCase();
    if (!q) return files;
    return files.filter((f) => f.path.toLowerCase().includes(q));
  }, [files, fileQuery]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError("");
    setSaving(true);

    const parsedTags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    const parsedLinks: Record<string, string> = {};
    for (const line of linksInput.split("\n")) {
      const idx = line.indexOf(":");
      if (idx > 0) {
        const label = line.slice(0, idx).trim();
        const url = line.slice(idx + 1).trim();
        if (label && url) parsedLinks[label] = url;
      }
    }

    try {
      const updated = await repoApi.updateRepo(repository.id, {
        description: description.trim() || null,
        tags: parsedTags,
        notes: notes.trim() || null,
        links: Object.keys(parsedLinks).length > 0 ? parsedLinks : null,
      });
      onUpdated(updated);
      setEditing(false);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Failed to save project details.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl space-y-6">
        {/* Overview Card */}
        <div className="rounded-xl border border-border-default bg-bg-secondary p-6 space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-1">
              <h2 className="text-xl font-bold text-text-primary">{repository.name}</h2>
              <div className="flex flex-wrap items-center gap-3 text-xs text-text-secondary">
                <a
                  href={repository.github_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-emerald-400 hover:underline"
                >
                  {repository.github_url}
                  <ExternalLink className="h-3 w-3" />
                </a>
                <span className="inline-flex items-center gap-1">
                  <GitBranch className="h-3.5 w-3.5 text-text-tertiary" />
                  {repository.branch}
                </span>
                {repository.owner_username && (
                  <span className="inline-flex items-center gap-1">
                    <UserIcon className="h-3.5 w-3.5 text-text-tertiary" />
                    Added by {repository.owner_username}
                  </span>
                )}
              </div>
            </div>

            {isOwner && !editing && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditing(true)}
                className="gap-1.5"
              >
                <Pencil className="h-3.5 w-3.5" />
                Edit Details
              </Button>
            )}
          </div>

          {editing ? (
            <form onSubmit={handleSave} className="space-y-4 border-t border-border-default/60 pt-4">
              {saveError && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-300">
                  {saveError}
                </div>
              )}
              <Input
                label="Description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Short summary of this project"
              />
              <Input
                label="Tags (comma-separated)"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="backend, fastapi, rag"
              />
              <div className="space-y-1">
                <label className="block text-xs font-medium text-text-secondary">
                  External Links (one per line: label: https://...)
                </label>
                <textarea
                  rows={2}
                  value={linksInput}
                  onChange={(e) => setLinksInput(e.target.value)}
                  placeholder={"docs: https://docs.example.com\ndemo: https://app.example.com"}
                  className="w-full rounded-lg border border-border-default bg-bg-primary px-3 py-2 text-xs text-text-primary placeholder:text-text-tertiary focus:border-emerald-500 focus:outline-none"
                />
              </div>
              <div className="space-y-1">
                <label className="block text-xs font-medium text-text-secondary">
                  Project Notes
                </label>
                <textarea
                  rows={4}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Architecture overview, setup commands, team contacts..."
                  className="w-full rounded-lg border border-border-default bg-bg-primary px-3 py-2 text-xs text-text-primary placeholder:text-text-tertiary focus:border-emerald-500 focus:outline-none"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setEditing(false)}
                  disabled={saving}
                >
                  <X className="h-3.5 w-3.5 mr-1" />
                  Cancel
                </Button>
                <Button type="submit" variant="primary" size="sm" isLoading={saving}>
                  <Save className="h-3.5 w-3.5 mr-1" />
                  Save
                </Button>
              </div>
            </form>
          ) : (
            <div className="space-y-4 border-t border-border-default/60 pt-4">
              <p className="text-sm text-text-secondary">
                {repository.description || "No description provided yet."}
              </p>

              {repository.tags && repository.tags.length > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  <Tag className="h-3.5 w-3.5 text-text-tertiary" />
                  {repository.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-300"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {repository.links && Object.keys(repository.links).length > 0 && (
                <div className="flex flex-wrap items-center gap-3">
                  <Link2 className="h-3.5 w-3.5 text-text-tertiary" />
                  {Object.entries(repository.links).map(([label, url]) => (
                    <a
                      key={label}
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 rounded-md border border-border-default bg-bg-primary px-2.5 py-1 text-xs text-emerald-400 hover:border-emerald-500/50"
                    >
                      <span>{label}</span>
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ))}
                </div>
              )}

              {repository.notes && (
                <div className="rounded-lg border border-border-default bg-bg-primary/60 p-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
                    Project Notes
                  </h4>
                  <p className="whitespace-pre-wrap text-sm text-text-secondary leading-relaxed">
                    {repository.notes}
                  </p>
                </div>
              )}

              {repository.languages && Object.keys(repository.languages).length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary mb-2">
                    Languages
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(repository.languages).map(([lang, count]) => (
                      <span
                        key={lang}
                        className="rounded-md border border-border-default bg-bg-primary px-2.5 py-1 text-xs text-text-secondary"
                      >
                        {lang}: <span className="text-text-primary font-medium">{count}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* File Browser Card */}
        <div className="rounded-xl border border-border-default bg-bg-secondary p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-text-primary">
              Indexed Files ({files.length})
            </h3>
            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-tertiary" />
              <input
                type="text"
                placeholder="Filter file paths..."
                value={fileQuery}
                onChange={(e) => setFileQuery(e.target.value)}
                className="w-full rounded-lg border border-border-default bg-bg-primary py-1.5 pl-8 pr-3 text-xs text-text-primary placeholder:text-text-tertiary focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </div>

          {loadingFiles ? (
            <p className="text-xs text-text-tertiary py-4">Loading files...</p>
          ) : filteredFiles.length === 0 ? (
            <p className="text-xs text-text-tertiary py-4">
              {files.length === 0 ? "No indexed files available yet." : "No files match your filter."}
            </p>
          ) : (
            <div className="max-h-96 overflow-y-auto divide-y divide-border-default/50 rounded-lg border border-border-default bg-bg-primary/40">
              {filteredFiles.map((file) => (
                <button
                  key={file.id}
                  onClick={() => onOpenFile(file)}
                  className="w-full flex items-center justify-between px-3 py-2 text-left text-xs hover:bg-bg-tertiary/60 transition-colors"
                >
                  <span className="flex items-center gap-2 truncate text-text-primary">
                    <FileCode2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                    <span className="truncate font-mono">{file.path}</span>
                  </span>
                  <span className="ml-3 shrink-0 text-[11px] text-text-tertiary">
                    {file.language} • {(file.size_bytes / 1024).toFixed(1)} KB
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

