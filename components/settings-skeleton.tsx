"use client";

import { cn } from "@/lib/utils";

interface SettingsSkeletonProps {
  heights?: string[];
  className?: string;
}

export function SettingsSkeleton({
  heights = ["h-64", "h-48", "h-32"],
  className,
}: SettingsSkeletonProps) {
  return (
    <div className={cn("flex flex-col gap-6", className)}>
      {heights.map((height, index) => (
        <div
          key={index}
          className={cn(height, "rounded-xl border bg-card animate-pulse")}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}
