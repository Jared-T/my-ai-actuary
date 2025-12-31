"use client";

import { cn } from "@/lib/utils";

interface SettingsMessageProps {
  type: "success" | "error";
  message: string | null;
}

export function SettingsMessage({ type, message }: SettingsMessageProps) {
  if (!message) return null;

  return (
    <div
      role="alert"
      className={cn(
        "p-3 rounded-md text-sm",
        type === "error"
          ? "bg-destructive/10 text-destructive"
          : "bg-green-500/10 text-green-600 dark:text-green-400"
      )}
    >
      {message}
    </div>
  );
}
