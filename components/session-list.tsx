"use client";

import * as React from "react";
import { useState, useCallback, memo } from "react";
import {
  MessageSquare,
  Plus,
  Trash2,
  Pencil,
  Check,
  X,
  MoreVertical,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { SessionSummary } from "@/lib/hooks/useSessionPersistence";

/** Time constants in milliseconds */
const MS_PER_MINUTE = 60000;
const MS_PER_HOUR = 3600000;
const MS_PER_DAY = 86400000;
const DAYS_PER_WEEK = 7;

interface SessionListProps {
  /** List of sessions to display */
  sessions: SessionSummary[];
  /** Currently selected session ID */
  selectedSessionId: string | null;
  /** Whether sessions are being loaded */
  isLoading: boolean;
  /** Callback when a session is selected */
  onSelectSession: (sessionId: string) => void;
  /** Callback when new session button is clicked */
  onNewSession: () => void;
  /** Callback when a session is deleted */
  onDeleteSession?: (sessionId: string) => Promise<boolean>;
  /** Callback when a session title is updated */
  onUpdateTitle?: (sessionId: string, title: string) => Promise<boolean>;
  /** Additional CSS classes */
  className?: string;
}

interface SessionItemProps {
  session: SessionSummary;
  isSelected: boolean;
  onSelect: () => void;
  onDelete?: () => Promise<boolean>;
  onUpdateTitle?: (title: string) => Promise<boolean>;
}

/**
 * Format a date as relative time or date string
 */
function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / MS_PER_MINUTE);
  const diffHours = Math.floor(diffMs / MS_PER_HOUR);
  const diffDays = Math.floor(diffMs / MS_PER_DAY);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < DAYS_PER_WEEK) return `${diffDays}d ago`;

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

/**
 * Individual session item in the list
 */
const SessionItem = memo(function SessionItem({
  session,
  isSelected,
  onSelect,
  onDelete,
  onUpdateTitle,
}: SessionItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(session.title || "");
  const [isDeleting, setIsDeleting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const handleStartEdit = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setEditTitle(session.title || "New Conversation");
    setIsEditing(true);
  }, [session.title]);

  const handleCancelEdit = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditing(false);
    setEditTitle(session.title || "");
  }, [session.title]);

  const handleSaveEdit = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!onUpdateTitle || !editTitle.trim()) return;

      setIsSaving(true);
      try {
        const success = await onUpdateTitle(editTitle.trim());
        if (success) {
          setIsEditing(false);
        }
      } finally {
        setIsSaving(false);
      }
    },
    [editTitle, onUpdateTitle]
  );

  const handleDelete = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!onDelete) return;

      setIsDeleting(true);
      try {
        await onDelete();
      } finally {
        setIsDeleting(false);
      }
    },
    [onDelete]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      e.stopPropagation();
      if (e.key === "Enter") {
        handleSaveEdit(e as unknown as React.MouseEvent);
      } else if (e.key === "Escape") {
        handleCancelEdit(e as unknown as React.MouseEvent);
      }
    },
    [handleSaveEdit, handleCancelEdit]
  );

  return (
    <div
      onClick={onSelect}
      className={cn(
        "group flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors",
        "hover:bg-accent",
        isSelected && "bg-accent",
        isDeleting && "opacity-50 pointer-events-none"
      )}
      data-testid={`session-item-${session.id}`}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          onSelect();
        }
      }}
    >
      <div className="flex-shrink-0">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
      </div>

      <div className="flex-1 min-w-0">
        {isEditing ? (
          <div className="flex items-center gap-1">
            <Input
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              onClick={(e) => e.stopPropagation()}
              className="h-6 py-0 px-1 text-sm"
              autoFocus
              disabled={isSaving}
            />
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={handleSaveEdit}
              disabled={isSaving}
            >
              {isSaving ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Check className="h-3 w-3" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={handleCancelEdit}
              disabled={isSaving}
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        ) : (
          <>
            <p className="text-sm font-medium truncate">
              {session.title || "New Conversation"}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatRelativeTime(session.last_activity_at)}
              {session.message_count !== undefined && (
                <span className="ml-2">
                  {session.message_count} message{session.message_count !== 1 ? "s" : ""}
                </span>
              )}
            </p>
          </>
        )}
      </div>

      {!isEditing && (onDelete || onUpdateTitle) && (
        <div className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreVertical className="h-4 w-4" />
                <span className="sr-only">Session options</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {onUpdateTitle && (
                <DropdownMenuItem onClick={handleStartEdit}>
                  <Pencil className="h-4 w-4 mr-2" />
                  Rename
                </DropdownMenuItem>
              )}
              {onDelete && (
                <DropdownMenuItem
                  onClick={handleDelete}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </div>
  );
});

/**
 * Empty state when there are no sessions
 */
const EmptyState = memo(function EmptyState({
  onNewSession,
}: {
  onNewSession: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
      <div className="rounded-full bg-muted p-3 mb-3">
        <MessageSquare className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="font-medium text-sm mb-1">No conversations yet</h3>
      <p className="text-xs text-muted-foreground mb-4">
        Start a new conversation to get started
      </p>
      <Button size="sm" onClick={onNewSession}>
        <Plus className="h-4 w-4 mr-2" />
        New Chat
      </Button>
    </div>
  );
});

/**
 * Loading skeleton for sessions
 */
const LoadingSkeleton = memo(function LoadingSkeleton() {
  return (
    <div className="space-y-2 px-2">
      {[...Array(3)].map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg animate-pulse"
        >
          <div className="h-4 w-4 bg-muted rounded" />
          <div className="flex-1 space-y-1.5">
            <div className="h-4 bg-muted rounded w-3/4" />
            <div className="h-3 bg-muted rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
});

/**
 * Session list component displaying user's conversation sessions
 */
export function SessionList({
  sessions,
  selectedSessionId,
  isLoading,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onUpdateTitle,
  className,
}: SessionListProps) {
  return (
    <div
      className={cn("flex flex-col h-full", className)}
      data-testid="session-list"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <h2 className="font-semibold text-sm">Conversations</h2>
        <Button
          variant="ghost"
          size="icon"
          onClick={onNewSession}
          className="h-8 w-8"
          data-testid="new-session-button"
        >
          <Plus className="h-4 w-4" />
          <span className="sr-only">New conversation</span>
        </Button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading ? (
          <LoadingSkeleton />
        ) : sessions.length === 0 ? (
          <EmptyState onNewSession={onNewSession} />
        ) : (
          <div className="space-y-1 px-2">
            {sessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isSelected={session.id === selectedSessionId}
                onSelect={() => onSelectSession(session.id)}
                onDelete={
                  onDeleteSession
                    ? () => onDeleteSession(session.id)
                    : undefined
                }
                onUpdateTitle={
                  onUpdateTitle
                    ? (title) => onUpdateTitle(session.id, title)
                    : undefined
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
