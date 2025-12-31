import { redirect } from "next/navigation";
import { Suspense } from "react";
import { Bot, Loader2 } from "lucide-react";

import { createClient } from "@/lib/supabase/server";
import { SessionsContainer } from "@/components/sessions-container";

async function getUserInfo() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getUser();

  if (error || !data?.user) {
    return null;
  }

  return {
    id: data.user.id,
    email: data.user.email,
    name:
      data.user.user_metadata?.full_name ||
      data.user.email?.split("@")[0] ||
      "User",
  };
}

function SessionsLoading() {
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Loading sessions...</p>
      </div>
    </div>
  );
}

async function SessionsPageContent() {
  const user = await getUserInfo();

  // If no user is authenticated, redirect to login
  if (!user) {
    redirect("/auth/login");
  }

  return <SessionsContainer userName={user.name} />;
}

export default function SessionsPage() {
  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="flex items-center gap-3 px-4 py-3 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-2">
          <div className="rounded-full bg-primary/10 p-1.5">
            <Bot className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-lg font-semibold">AI Actuary</h1>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <Suspense fallback={<SessionsLoading />}>
          <SessionsPageContent />
        </Suspense>
      </main>
    </div>
  );
}
