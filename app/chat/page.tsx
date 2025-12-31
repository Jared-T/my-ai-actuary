import { redirect } from "next/navigation";
import { Suspense } from "react";
import { MessageSquare, Loader2 } from "lucide-react";

import { createClient } from "@/lib/supabase/server";
import { ChatInterface } from "@/components/chat-interface";

async function getUserInfo() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getUser();

  if (error || !data?.user) {
    return null;
  }

  return {
    id: data.user.id,
    email: data.user.email,
    name: data.user.user_metadata?.full_name || data.user.email?.split("@")[0] || "User",
  };
}

function ChatLoading() {
  return (
    <div className="flex items-center justify-center h-[600px]">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Loading chat...</p>
      </div>
    </div>
  );
}

async function ChatContainer() {
  const user = await getUserInfo();

  // If no user is authenticated, redirect to login
  if (!user) {
    redirect("/auth/login");
  }

  return (
    <ChatInterface
      channelName="general-chat"
      userName={user.name}
      title="General Chat"
      placeholder="Type your message..."
    />
  );
}

export default function ChatPage() {
  return (
    <div className="flex-1 w-full flex flex-col gap-6 items-center py-8">
      <div className="w-full max-w-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="rounded-full bg-primary/10 p-2">
            <MessageSquare className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Chat Room</h1>
            <p className="text-sm text-muted-foreground">
              Real-time messaging with other users
            </p>
          </div>
        </div>

        <Suspense fallback={<ChatLoading />}>
          <ChatContainer />
        </Suspense>
      </div>
    </div>
  );
}
