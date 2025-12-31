"use client";

import * as React from "react";
import { useRef, useEffect, useState, useCallback, memo } from "react";
import { Send, Loader2, Bot, User, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import {
  useSessionPersistence,
  type PersistedMessage,
} from "@/lib/hooks/useSessionPersistence";

interface PersistedChatInterfaceProps {
  /** Initial session ID to load */
  sessionId?: string;
  /** Agent type to use */
  agentType?: string;
  /** Engagement ID to associate with session */
  engagementId?: string;
  /** Chat title */
  title?: string;
  /** Input placeholder */
  placeholder?: string;
  /** Additional CSS classes */
  className?: string;
  /** Callback when session ID changes (new session created) */
  onSessionChange?: (sessionId: string) => void;
  /** Callback when a message is sent */
  onMessageSent?: () => void;
}

interface MessageBubbleProps {
  message: PersistedMessage;
}

/**
 * Format a timestamp for display
 */
function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Memoized message bubble component
 */
const MessageBubble = memo(function MessageBubble({
  message,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const isError = message.metadata?.error === true;

  if (isSystem) {
    return (
      <div className="flex justify-center my-2">
        <div
          className={cn(
            "text-xs px-3 py-1.5 rounded-full",
            isError
              ? "bg-destructive/10 text-destructive"
              : "bg-muted text-muted-foreground"
          )}
        >
          {isError && <AlertCircle className="h-3 w-3 inline mr-1" />}
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex gap-3 mb-4",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Bot className="h-4 w-4 text-muted-foreground" />
        )}
      </div>

      {/* Message content */}
      <div
        className={cn(
          "flex flex-col max-w-[80%]",
          isUser ? "items-end" : "items-start"
        )}
      >
        <div
          className={cn(
            "rounded-2xl px-4 py-2 break-words",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-sm"
              : "bg-muted text-foreground rounded-bl-sm"
          )}
          data-testid={isUser ? "user-message" : "assistant-message"}
        >
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
        <span className="text-xs text-muted-foreground mt-1 px-1">
          {formatTime(message.created_at)}
        </span>
      </div>
    </div>
  );
});

/**
 * Empty state component shown when there are no messages
 */
const EmptyState = memo(function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-6">
      <div className="rounded-full bg-muted p-4 mb-4">
        <Bot className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="font-medium text-foreground mb-1">
        Start a new conversation
      </h3>
      <p className="text-sm text-muted-foreground max-w-[250px]">
        Ask questions about actuarial topics, data analysis, or any other
        inquiries you have.
      </p>
    </div>
  );
});

/**
 * Typing indicator shown when agent is processing
 */
const TypingIndicator = memo(function TypingIndicator() {
  return (
    <div className="flex gap-3 mb-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-muted flex items-center justify-center">
        <Bot className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-2">
        <div className="flex gap-1">
          <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:-0.3s]" />
          <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce [animation-delay:-0.15s]" />
          <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" />
        </div>
      </div>
    </div>
  );
});

/**
 * Persisted chat interface that stores messages in the backend
 */
export function PersistedChatInterface({
  sessionId: initialSessionId,
  agentType = "general",
  engagementId,
  title = "AI Actuary",
  placeholder = "Ask me anything about actuarial topics...",
  className,
  onSessionChange,
  onMessageSent,
}: PersistedChatInterfaceProps) {
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const prevSessionIdRef = useRef<string | null>(null);

  const {
    sessionId,
    messages,
    isLoading,
    isSending,
    error,
    sessionTitle,
    sendMessage,
    loadSession,
    startNewSession,
  } = useSessionPersistence({
    initialSessionId,
    agentType,
    engagementId,
    onError: (err) => {
      console.error("Session error:", err);
    },
    onMessageSent: () => {
      onMessageSent?.();
    },
  });

  // Notify parent when session ID changes
  useEffect(() => {
    if (sessionId && sessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = sessionId;
      onSessionChange?.(sessionId);
    }
  }, [sessionId, onSessionChange]);

  // Load session when initialSessionId prop changes
  useEffect(() => {
    if (initialSessionId && initialSessionId !== sessionId) {
      loadSession(initialSessionId);
    } else if (!initialSessionId && sessionId) {
      // Clear session if initialSessionId is removed
      startNewSession();
    }
  }, [initialSessionId, sessionId, loadSession, startNewSession]);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSending, scrollToBottom]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!inputValue.trim() || isSending) return;

      const message = inputValue.trim();
      setInputValue("");
      await sendMessage(message);
      inputRef.current?.focus();
    },
    [inputValue, isSending, sendMessage]
  );

  const displayTitle = sessionTitle || title;

  return (
    <Card
      className={cn("flex flex-col h-[600px] w-full", className)}
      data-testid="persisted-chat-interface"
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3 border-b">
        <CardTitle className="text-lg font-semibold truncate">
          {displayTitle}
        </CardTitle>
        {isLoading && (
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span className="text-xs">Loading...</span>
          </div>
        )}
      </CardHeader>

      <CardContent
        className="flex-1 overflow-y-auto p-4"
        data-testid="message-list"
      >
        {error && (
          <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md mb-4">
            <AlertCircle className="h-4 w-4 inline mr-2" />
            {error.message}
          </div>
        )}

        {messages.length === 0 && !isLoading ? (
          <EmptyState />
        ) : (
          <div className="flex flex-col">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {isSending && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </CardContent>

      <CardFooter className="border-t p-4">
        <form
          onSubmit={handleSubmit}
          className="flex w-full gap-2"
          data-testid="chat-form"
        >
          <Input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={placeholder}
            disabled={isLoading || isSending}
            className="flex-1"
            data-testid="chat-input"
            aria-label="Message input"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!inputValue.trim() || isLoading || isSending}
            data-testid="send-button"
            aria-label="Send message"
          >
            {isSending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>
      </CardFooter>
    </Card>
  );
}
