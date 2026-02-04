"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, MoreVertical, Mail, Shield } from "lucide-react";
import { InviteUserDialog } from "@/components/invite-user-dialog";

interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  is_active: boolean;
  roles: { id: string; name: string }[];
}

interface Invite {
  id: string;
  email: string;
  expires_at: string;
  role: { name: string };
}

function UserAvatar({ initials }: { initials: string }) {
  return (
    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
      <span className="text-sm font-medium text-primary">{initials}</span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardContent className="flex items-center gap-4 p-4">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function UsersPage() {
  const { isAuthenticated } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [roles, setRoles] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;

    Promise.all([
      fetch("/api/v1/users", { credentials: "include" }).then((r) => r.ok ? r.json() : { data: [] }),
      fetch("/api/v1/roles", { credentials: "include" }).then((r) => r.ok ? r.json() : { data: [] }),
    ]).then(([usersResponse, rolesResponse]) => {
      // Handle paginated response - extract data array
      const usersData = usersResponse.data || usersResponse;
      const rolesData = rolesResponse.data || rolesResponse;
      setUsers(Array.isArray(usersData) ? usersData : []);
      setRoles(Array.isArray(rolesData) ? rolesData : []);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, [isAuthenticated]);

  const handleDeactivate = async (userId: string) => {
    if (!confirm("Deactivate this user?")) return;
    await fetch(`/api/v1/users/${userId}`, {
      method: "DELETE",
      credentials: "include",
    });
    setUsers(users.map((u) => (u.id === userId ? { ...u, is_active: false } : u)));
  };

  const handleInviteSent = (invite: Invite) => {
    setInvites([...invites, invite]);
    setDialogOpen(false);
  };

  const getInitials = (user: User) => {
    if (user.first_name && user.last_name) {
      return `${user.first_name[0]}${user.last_name[0]}`.toUpperCase();
    }
    return user.email[0].toUpperCase();
  };

  const getName = (user: User) => {
    if (user.first_name || user.last_name) {
      return `${user.first_name || ""} ${user.last_name || ""}`.trim();
    }
    return user.email;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground">Manage team members and invitations</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Invite User
        </Button>
      </div>

      {loading ? (
        <LoadingSkeleton />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Team Members</CardTitle>
            <CardDescription>{users.length} user{users.length !== 1 ? "s" : ""}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {users.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No users found</p>
            ) : (
              users.map((user) => (
                <div key={user.id} className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-4">
                    <UserAvatar initials={getInitials(user)} />
                    <div>
                      <div className="font-medium flex items-center gap-2">
                        {getName(user)}
                        {!user.is_active && (
                          <Badge variant="secondary">Inactive</Badge>
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground">{user.email}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex gap-1">
                      {user.roles?.map((role) => (
                        <Badge key={role.id} variant="outline">
                          <Shield className="mr-1 h-3 w-3" />
                          {role.name}
                        </Badge>
                      ))}
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem>Change Role</DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => handleDeactivate(user.id)}
                        >
                          Deactivate
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}

      {invites.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Pending Invitations</CardTitle>
            <CardDescription>{invites.length} pending</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {invites.map((invite) => (
              <div key={invite.id} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-4">
                  <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div>
                    <div className="font-medium">{invite.email}</div>
                    <div className="text-sm text-muted-foreground">
                      Expires {new Date(invite.expires_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>
                <Badge variant="outline">{invite.role.name}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <InviteUserDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        roles={roles}
        onInviteSent={handleInviteSent}
      />
    </div>
  );
}
