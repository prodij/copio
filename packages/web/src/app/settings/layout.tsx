"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Users, Shield, ScrollText, Settings as SettingsIcon, User } from "lucide-react";

const settingsNav = [
  { title: "Profile", href: "/settings/profile", icon: User },
  { title: "General", href: "/settings", icon: SettingsIcon },
  { title: "Users", href: "/settings/users", icon: Users },
  { title: "Roles", href: "/settings/roles", icon: Shield },
  { title: "Audit Log", href: "/settings/audit-log", icon: ScrollText },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full">
      <aside className="w-48 border-r bg-muted/30 p-4">
        <h2 className="mb-4 text-lg font-semibold">Settings</h2>
        <nav className="space-y-1">
          {settingsNav.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-muted font-medium"
                    : "hover:bg-muted"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.title}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
