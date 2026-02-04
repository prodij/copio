"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PermissionMatrix } from "@/components/permission-matrix";
import { ArrowLeft, Save, Trash2, Loader2 } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10 rounded" />
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

export default function RoleEditorPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [role, setRole] = useState<Role | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [allPermissions, setAllPermissions] = useState<Record<string, string[]>>({});

  useEffect(() => {
    if (!isAuthenticated) return;

    Promise.all([
      fetch(`/api/v1/roles/${params.id}`, { credentials: "include" }).then((r) => r.ok ? r.json() : null),
      fetch("/api/v1/permissions/by-resource", { credentials: "include" }).then((r) => r.ok ? r.json() : {}),
    ]).then(([roleData, perms]) => {
      setRole(roleData);
      setAllPermissions(perms && typeof perms === 'object' ? perms as Record<string, string[]> : {});
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, [params.id, isAuthenticated]);

  const handleSave = async () => {
    if (!role) return;
    setSaving(true);

    try {
      const res = await fetch(`/api/v1/roles/${role.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          name: role.name,
          description: role.description,
          permissions: role.permissions,
        }),
      });

      if (res.ok) {
        toast.success("Role saved");
      } else {
        toast.error("Failed to save role");
      }
    } catch {
      toast.error("Failed to save role");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!role || role.is_system) return;
    if (!confirm("Delete this role?")) return;

    await fetch(`/api/v1/roles/${role.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    router.push("/settings/roles");
  };

  const handlePermissionChange = (permission: string, enabled: boolean) => {
    if (!role) return;
    setRole({
      ...role,
      permissions: enabled
        ? [...role.permissions, permission]
        : role.permissions.filter((p) => p !== permission),
    });
  };

  if (loading) return <LoadingSkeleton />;
  
  if (!role) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/settings/roles">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Role not found</h1>
            <p className="text-muted-foreground">This role doesn't exist or you don't have access.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/settings/roles">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{role.name}</h1>
            {role.is_system && <Badge variant="secondary">System</Badge>}
          </div>
          <p className="text-muted-foreground">Edit role permissions</p>
        </div>
        <div className="flex gap-2">
          {!role.is_system && (
            <Button variant="destructive" onClick={handleDelete}>
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          )}
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Role Details</CardTitle>
          <CardDescription>Basic information about this role</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={role.name}
              onChange={(e) => setRole({ ...role, name: e.target.value })}
              disabled={role.is_system}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={role.description || ""}
              onChange={(e) => setRole({ ...role, description: e.target.value })}
              rows={3}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Permissions</CardTitle>
          <CardDescription>
            {role.permissions.length} permission{role.permissions.length !== 1 ? "s" : ""} granted
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PermissionMatrix
            allPermissions={allPermissions}
            selectedPermissions={role.permissions}
            onChange={handlePermissionChange}
            disabled={role.is_system}
          />
        </CardContent>
      </Card>
    </div>
  );
}
