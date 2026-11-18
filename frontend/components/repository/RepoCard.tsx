"use client";

import React from "react";
import { Badge } from "../ui/badge";
import { GitBranch, Clock, FileText, Layers, Trash2, ArrowUpRight, AlertCircle, User as UserIcon } from "lucide-react";
import type { Repository } from "../../lib/api/types";

interface RepoCardProps {
  repository: Repository;
  currentUserId?: string;
  onSelect: (repo: Repository) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
}

export function RepoCard({ repository, currentUserId, onSelect, onDelete }: RepoCardProps) {
  const getStatusBadge = (status: Repository["status"]) => {
    switch (status) {
      case "READY":
        return <Badge variant="success">READY</Badge>;
      case "FAILED":
        return <Badge variant="error">FAILED</Badge>;
      case "PENDING":
        return <Badge variant="default">PENDING</Badge>;
      default:
        return (
          <Badge variant="info" className="animate-pulse">
            {status}
          </Badge>
        );
    }
  };

  return (
    <div
      onClick={() => onSelect(repository)}
      className="group relative flex flex-col justify-between rounded-xl border border-border-default bg-bg-secondary p-5 hover:border-emerald-500/50 hover:bg-bg-tertiary/40 transition-all duration-200 cursor-pointer shadow-sm hover:shadow-md"
    >
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h4 className="text-base font-semibold text-text-primary truncate group-hover:text-emerald-400 transition-colors">
              {repository.name}
            </h4>
            <p className="text-xs text-text-tertiary truncate mt-0.5">
              {repository.github_url}
            </p>
          </div>
          <div>{getStatusBadge(repository.status)}</div>
        </div>

        {repository.description && (
          <p className="mt-2.5 text-xs text-text-secondary line-clamp-2">
            {repository.description}
          </p>
        )}

        {repository.tags && repository.tags.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {repository.tags.slice(0, 4).map((tag) => (
              <span
                key={tag}
                className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300"
              >
                {tag}
              </span>
            ))}
            {repository.tags.length > 4 && (
              <span className="text-[10px] text-text-tertiary self-center">
                +{repository.tags.length - 4}
              </span>
            )}
          </div>
        )}

        {repository.error_message && (
          <div className="mt-3 flex items-start gap-1.5 rounded-lg border border-rose-500/20 bg-rose-500/10 p-2 text-xs text-rose-300">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span className="line-clamp-2">{repository.error_message}</span>
          </div>
        )}

        <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-text-secondary">
          <div className="flex items-center gap-1.5">
            <GitBranch className="h-3.5 w-3.5 text-text-tertiary" />
            <span className="truncate">{repository.branch}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-text-tertiary" />
            <span>{repository.file_count} files</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-text-tertiary" />
            <span>{repository.chunk_count} chunks</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-text-tertiary" />
            <span>{new Date(repository.created_at).toLocaleDateString()}</span>
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-border-default/60 pt-3">
        <span className="inline-flex items-center text-xs font-medium text-emerald-400 group-hover:translate-x-0.5 transition-transform gap-1">
          Open Project <ArrowUpRight className="h-3.5 w-3.5" />
        </span>
        <div className="flex items-center gap-2">
          {repository.owner_username && (
            <span className="inline-flex items-center gap-1 text-[11px] text-text-tertiary">
              <UserIcon className="h-3 w-3" />
              {repository.owner_username}
            </span>
          )}
          {currentUserId && repository.user_id === currentUserId && (
            <button
              onClick={(e) => onDelete(repository.id, e)}
              className="rounded p-1 text-text-tertiary hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
              title="Delete project"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
