"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, Shield, Users } from "lucide-react";
import { CreateRoleDialog } from "@/components/create-role-dialog";
import Link from "next/link";

interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
}

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    fetch("/api/v1/roles")
      .then((res) => res.json())
      .then((data) => {
        setRoles(data);
        setLoading(false);
      });
  }, []);

  const handleRoleCreated = (role: Role) => {
    setRoles([...roles, role]);
    setDialogOpen(false);
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Roles</h1>
          <p className="text-muted-foreground">Manage user roles and permissions</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Role
        </Button>
      </div>

      <div className="grid gap-4">
        {roles.map((role) => (
          <Link key={role.id} href={`/settings/roles/${role.id}`}>
            <Card className="hover:bg-muted/50 cursor-pointer transition-colors">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5" />
                    {role.name}
                  </CardTitle>
                  {role.is_system && <Badge variant="secondary">System</Badge>}
                </div>
                <CardDescription>{role.description || "No description"}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-muted-foreground">
                  {role.permissions.length} permissions
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <CreateRoleDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onRoleCreated={handleRoleCreated}
      />
    </div>
  );
}
