"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Users, Shield, ScrollText, User, Building2 } from "lucide-react";

const settingsNav = [
  { title: "Company", href: "/settings/company", icon: Building2 },
  { title: "Profile", href: "/settings/profile", icon: User },
  { title: "Users", href: "/settings/users", icon: Users },
  { title: "Roles", href: "/settings/roles", icon: Shield },
  { title: "Audit Log", href: "/settings/audit-log", icon: ScrollText },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex gap-6">
      <aside className="w-48 flex-shrink-0">
        <nav className="space-y-1 sticky top-6">
          {settingsNav.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-muted font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.title}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="flex-1 min-w-0">{children}</main>
    </div>
  );
}
