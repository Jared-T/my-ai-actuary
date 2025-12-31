"use client";

import * as React from "react";
import { useState, useCallback, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { SessionList } from "@/components/session-list";
import { PersistedChatInterface } from "@/components/persisted-chat-interface";
import { useSessionList } from "@/lib/hooks/useSessionList";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Delay in ms before refreshing session list after a message is sent */
const SESSION_REFRESH_DELAY_MS = 1000;

/** Mobile breakpoint width in pixels */
const MOBILE_BREAKPOINT_PX = 768;

interface SessionsContainerProps {
  /** User's display name */
  userName?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Container component that combines session list sidebar with chat interface.
 * Provides multi-turn conversation support with session persistence.
 */
export function SessionsContainer({
  userName = "User",
  className,
}: SessionsContainerProps) {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null
  );
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const refreshTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const {
    sessions,
    isLoading,
    error,
    fetchSessions,
    deleteSession,
    updateSessionTitle,
  } = useSessionList({
    autoLoad: true,
    onError: (err) => {
      console.error("Failed to load sessions:", err);
    },
  });

  // Handle session selection
  const handleSelectSession = useCallback((sessionId: string) => {
    setSelectedSessionId(sessionId);
    // Close sidebar on mobile after selection
    if (window.innerWidth < MOBILE_BREAKPOINT_PX) {
      setIsSidebarOpen(false);
    }
  }, []);

  // Handle new session creation
  const handleNewSession = useCallback(() => {
    setSelectedSessionId(null);
    // Close sidebar on mobile after creating new session
    if (window.innerWidth < MOBILE_BREAKPOINT_PX) {
      setIsSidebarOpen(false);
    }
  }, []);

  // Handle session ID change from chat interface (when new session is created)
  const handleSessionChange = useCallback(
    (newSessionId: string) => {
      setSelectedSessionId(newSessionId);
      // Refresh session list to include the new session
      fetchSessions();
    },
    [fetchSessions]
  );

  // Handle session deletion
  const handleDeleteSession = useCallback(
    async (sessionId: string): Promise<boolean> => {
      const success = await deleteSession(sessionId);
      if (success && sessionId === selectedSessionId) {
        // If the deleted session was selected, clear selection
        setSelectedSessionId(null);
      }
      return success;
    },
    [deleteSession, selectedSessionId]
  );

  // Handle message sent - refresh session list to update activity time
  const handleMessageSent = useCallback(() => {
    // Clear any existing timeout to debounce
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current);
    }
    // Debounced refresh to avoid too many API calls
    refreshTimeoutRef.current = setTimeout(() => {
      fetchSessions();
      refreshTimeoutRef.current = null;
    }, SESSION_REFRESH_DELAY_MS);
  }, [fetchSessions]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current);
      }
    };
  }, []);

  // Toggle sidebar
  const toggleSidebar = useCallback(() => {
    setIsSidebarOpen((prev) => !prev);
  }, []);

  // Close sidebar on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isSidebarOpen && window.innerWidth < MOBILE_BREAKPOINT_PX) {
        setIsSidebarOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSidebarOpen]);

  return (
    <div className={cn("flex h-full", className)} data-testid="sessions-container">
      {/* Mobile sidebar toggle */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed left-4 top-16 z-50 md:hidden"
        onClick={toggleSidebar}
        aria-label={isSidebarOpen ? "Close sidebar" : "Open sidebar"}
      >
        {isSidebarOpen ? (
          <X className="h-5 w-5" />
        ) : (
          <Menu className="h-5 w-5" />
        )}
      </Button>

      {/* Sidebar overlay for mobile */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-72 border-r bg-background transform transition-transform duration-200 ease-in-out md:relative md:transform-none",
          "pt-14 md:pt-0", // Account for header on mobile
          isSidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
        data-testid="session-sidebar"
      >
        <SessionList
          sessions={sessions}
          selectedSessionId={selectedSessionId}
          isLoading={isLoading}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onDeleteSession={handleDeleteSession}
          onUpdateTitle={updateSessionTitle}
          className="h-full"
        />
      </aside>

      {/* Main chat area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 flex items-center justify-center p-4 md:p-6">
          <PersistedChatInterface
            sessionId={selectedSessionId ?? undefined}
            agentType="general"
            title={
              selectedSessionId
                ? sessions.find((s) => s.id === selectedSessionId)?.title ||
                  "Conversation"
                : "New Conversation"
            }
            onSessionChange={handleSessionChange}
            onMessageSent={handleMessageSent}
            className="w-full max-w-3xl h-full max-h-[calc(100vh-8rem)]"
          />
        </div>
      </main>
    </div>
  );
}
