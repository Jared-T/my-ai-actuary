"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { User, Bell, Settings, LucideIcon } from "lucide-react";

interface SidebarItem {
  title: string;
  href: string;
  icon: LucideIcon;
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  {
    title: "Account",
    href: "/settings/account",
    icon: User,
  },
  {
    title: "Notifications",
    href: "/settings/notifications",
    icon: Bell,
  },
  {
    title: "Preferences",
    href: "/settings/preferences",
    icon: Settings,
  },
];

export function SettingsSidebar() {
  const pathname = usePathname();

  return (
    <nav
      className="flex flex-col gap-1 w-full md:w-48"
      aria-label="Settings navigation"
    >
      {SIDEBAR_ITEMS.map((item) => {
        const isActive = pathname === item.href;
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {item.title}
          </Link>
        );
      })}
    </nav>
  );
}
