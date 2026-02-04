import Link from "next/link";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { User, Shield, ScrollText } from "lucide-react";

const settingsLinks = [
  {
    title: "Profile",
    description: "Manage your account settings",
    href: "/settings/profile",
    icon: User,
  },
  {
    title: "Users",
    description: "Invite and manage team members",
    href: "/settings/users",
    icon: User,
  },
  {
    title: "Roles",
    description: "Configure roles and permissions",
    href: "/settings/roles",
    icon: Shield,
  },
  {
    title: "Audit Log",
    description: "View security events",
    href: "/settings/audit-log",
    icon: ScrollText,
  },
];

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your organization settings, users, and roles.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {settingsLinks.map((item) => (
          <Link key={item.href} href={item.href}>
            <Card className="hover:bg-muted/50 transition-colors cursor-pointer h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <item.icon className="h-5 w-5" />
                  {item.title}
                </CardTitle>
                <CardDescription>{item.description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
