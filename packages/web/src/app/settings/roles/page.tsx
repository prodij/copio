"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Shield } from "lucide-react";
import { CreateRoleDialog } from "@/components/create-role-dialog";
import Link from "next/link";

interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
}

function LoadingSkeleton() {
  return (
    <div className="grid gap-4">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-4 w-24" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function RolesPage() {
  const { token } = useAuth();
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    if (!token) return;
    
    fetch("/api/v1/roles", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.ok ? res.json() : { data: [] })
      .then((response) => {
        // API returns { data: [...], total: N }
        const roles = response.data || response;
        setRoles(Array.isArray(roles) ? roles : []);
        setLoading(false);
      })
      .catch(() => {
        setRoles([]);
        setLoading(false);
      });
  }, [token]);

  const handleRoleCreated = (role: Role) => {
    setRoles([...roles, role]);
    setDialogOpen(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Roles</h1>
          <p className="text-muted-foreground">Manage user roles and permissions</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Role
        </Button>
      </div>

      {loading ? (
        <LoadingSkeleton />
      ) : roles.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No roles found. Create your first role to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {roles.map((role) => (
            <Link key={role.id} href={`/settings/roles/${role.id}`}>
              <Card className="hover:bg-muted/50 cursor-pointer transition-colors">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Shield className="h-5 w-5" />
                      {role.name}
                    </CardTitle>
                    {role.is_system && <Badge variant="secondary">System</Badge>}
                  </div>
                  <CardDescription>{role.description || "No description"}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {role.permissions.length} permission{role.permissions.length !== 1 ? "s" : ""}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <CreateRoleDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onRoleCreated={handleRoleCreated}
      />
    </div>
  );
}
