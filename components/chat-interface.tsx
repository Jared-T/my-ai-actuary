"use client";

import * as React from "react";
import { useRef, useEffect, useState, useCallback, memo } from "react";
import { Send, Loader2, WifiOff, Wifi } from "lucide-react";
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
  useRealtimeMessages,
  Message,
} from "@/lib/hooks/useRealtimeMessages";

interface ChatInterfaceProps {
  channelName?: string;
  userName?: string;
  className?: string;
  title?: string;
  placeholder?: string;
}

interface MessageBubbleProps {
  message: Message;
  isOwn: boolean;
}

/**
 * Memoized message bubble component to prevent unnecessary re-renders
 * when the message list grows. Only re-renders if the message or isOwn changes.
 */
const MessageBubble = memo(function MessageBubble({
  message,
  isOwn,
}: MessageBubbleProps) {
  const formattedTime = new Date(message.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      className={cn(
        "flex flex-col max-w-[80%] mb-3",
        isOwn ? "ml-auto items-end" : "mr-auto items-start"
      )}
    >
      {!isOwn && (
        <span className="text-xs text-muted-foreground mb-1 px-1">
          {message.sender_name}
        </span>
      )}
      <div
        className={cn(
          "rounded-2xl px-4 py-2 break-words",
          isOwn
            ? "bg-primary text-primary-foreground rounded-br-sm"
            : "bg-muted text-foreground rounded-bl-sm"
        )}
        data-testid={isOwn ? "own-message" : "other-message"}
      >
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
      </div>
      <span className="text-xs text-muted-foreground mt-1 px-1">
        {formattedTime}
      </span>
    </div>
  );
});

interface ConnectionStatusProps {
  isConnected: boolean;
  isLoading: boolean;
}

/**
 * Memoized connection status indicator
 */
const ConnectionStatus = memo(function ConnectionStatus({
  isConnected,
  isLoading,
}: ConnectionStatusProps) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span className="text-xs">Connecting...</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-1.5",
        isConnected ? "text-green-600 dark:text-green-500" : "text-destructive"
      )}
      data-testid="connection-status"
    >
      {isConnected ? (
        <>
          <Wifi className="h-3.5 w-3.5" />
          <span className="text-xs">Connected</span>
        </>
      ) : (
        <>
          <WifiOff className="h-3.5 w-3.5" />
          <span className="text-xs">Disconnected</span>
        </>
      )}
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
        <Send className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="font-medium text-foreground mb-1">No messages yet</h3>
      <p className="text-sm text-muted-foreground max-w-[200px]">
        Start the conversation by sending a message below
      </p>
    </div>
  );
});

export function ChatInterface({
  channelName = "chat-room",
  userName = "User",
  className,
  title = "Chat",
  placeholder = "Type a message...",
}: ChatInterfaceProps) {
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { messages, sendMessage, isConnected, isLoading, error } =
    useRealtimeMessages({
      channelName,
      // Error is already exposed via the error state; additional handling can be added here if needed
    });

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!inputValue.trim() || !isConnected) return;

      sendMessage(inputValue, userName);
      setInputValue("");
      inputRef.current?.focus();
    },
    [inputValue, isConnected, sendMessage, userName]
  );

  return (
    <Card
      className={cn("flex flex-col h-[600px] w-full max-w-2xl", className)}
      data-testid="chat-interface"
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3 border-b">
        <CardTitle className="text-lg font-semibold">{title}</CardTitle>
        <ConnectionStatus isConnected={isConnected} isLoading={isLoading} />
      </CardHeader>

      <CardContent className="flex-1 overflow-y-auto p-4" data-testid="message-list">
        {error && (
          <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-md mb-4">
            {error.message}
          </div>
        )}

        {messages.length === 0 && !isLoading ? (
          <EmptyState />
        ) : (
          <div className="flex flex-col">
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                isOwn={message.is_own_message ?? false}
              />
            ))}
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
            disabled={!isConnected || isLoading}
            className="flex-1"
            data-testid="chat-input"
            aria-label="Message input"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!inputValue.trim() || !isConnected || isLoading}
            data-testid="send-button"
            aria-label="Send message"
          >
            {isLoading ? (
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
