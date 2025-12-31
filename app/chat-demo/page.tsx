"use client";

import { ChatInterface } from "@/components/chat-interface";

/**
 * Demo page for testing the chat interface without authentication.
 * This page is intended for development and testing purposes only.
 */
export default function ChatDemoPage() {
  const isDevelopment = process.env.NODE_ENV === "development";

  return (
    <div className="flex-1 w-full flex flex-col gap-6 items-center py-8">
      <div className="w-full max-w-2xl">
        {/* Development warning banner */}
        {isDevelopment && (
          <div className="bg-yellow-100 dark:bg-yellow-900/30 border border-yellow-300 dark:border-yellow-700 text-yellow-800 dark:text-yellow-200 text-sm p-3 rounded-md mb-4">
            <strong>Development Mode:</strong> This is a demo page for testing.
            In production, use the authenticated <code>/chat</code> route.
          </div>
        )}

        <div className="mb-6">
          <h1 className="text-2xl font-bold">Chat Demo</h1>
          <p className="text-sm text-muted-foreground">
            Demo page for testing the chat interface (no auth required)
          </p>
        </div>

        <ChatInterface
          channelName="demo-chat"
          userName="Demo User"
          title="Demo Chat"
          placeholder="Type a message..."
        />
      </div>
    </div>
  );
}
