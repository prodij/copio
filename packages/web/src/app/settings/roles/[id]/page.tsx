"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PermissionMatrix } from "@/components/permission-matrix";
import { ArrowLeft, Save, Trash2 } from "lucide-react";
import Link from "next/link";

interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
}

export default function RoleEditorPage() {
  const params = useParams();
  const router = useRouter();
  const [role, setRole] = useState<Role | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [allPermissions, setAllPermissions] = useState<Record<string, string[]>>({});

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/roles/${params.id}`).then((r) => r.json()),
      fetch("/api/v1/permissions/by-resource").then((r) => r.json()),
    ]).then(([roleData, perms]) => {
      setRole(roleData);
      setAllPermissions(perms);
      setLoading(false);
    });
  }, [params.id]);

  const handleSave = async () => {
    if (!role) return;
    setSaving(true);
    await fetch(`/api/v1/roles/${role.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: role.name,
        description: role.description,
        permissions: role.permissions,
      }),
    });
    setSaving(false);
  };

  const handleDelete = async () => {
    if (!role || role.is_system) return;
    if (!confirm("Delete this role?")) return;
    await fetch(`/api/v1/roles/${role.id}`, { method: "DELETE" });
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

  if (loading || !role) return <div>Loading...</div>;

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Link href="/settings/roles">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{role.name}</h1>
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
            <Save className="mr-2 h-4 w-4" />
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Role Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Name</Label>
              <Input
                value={role.name}
                onChange={(e) => setRole({ ...role, name: e.target.value })}
                disabled={role.is_system}
              />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea
                value={role.description || ""}
                onChange={(e) => setRole({ ...role, description: e.target.value })}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Permissions</CardTitle>
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
    </div>
  );
}
