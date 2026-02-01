"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
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

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [roles, setRoles] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch("/api/v1/users").then((r) => r.json()),
      fetch("/api/v1/roles").then((r) => r.json()),
    ]).then(([usersData, rolesData]) => {
      setUsers(usersData);
      setRoles(rolesData);
      setLoading(false);
    });
  }, []);

  const handleDeactivate = async (userId: string) => {
    if (!confirm("Deactivate this user?")) return;
    await fetch(`/api/v1/users/${userId}`, { method: "DELETE" });
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

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Users</h1>
          <p className="text-muted-foreground">Manage team members and invitations</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Invite User
        </Button>
      </div>

      <div className="space-y-4">
        {users.map((user) => (
          <Card key={user.id}>
            <CardContent className="flex items-center justify-between p-4">
              <div className="flex items-center gap-4">
                <Avatar>
                  <AvatarFallback>{getInitials(user)}</AvatarFallback>
                </Avatar>
                <div>
                  <div className="font-medium">
                    {user.first_name} {user.last_name}
                    {!user.is_active && (
                      <Badge variant="secondary" className="ml-2">Inactive</Badge>
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
            </CardContent>
          </Card>
        ))}

        {invites.length > 0 && (
          <>
            <h2 className="text-lg font-semibold mt-8 mb-4">Pending Invitations</h2>
            {invites.map((invite) => (
              <Card key={invite.id}>
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-4">
                    <Avatar>
                      <AvatarFallback>
                        <Mail className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <div className="font-medium">{invite.email}</div>
                      <div className="text-sm text-muted-foreground">
                        Expires {new Date(invite.expires_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                  <Badge variant="outline">{invite.role.name}</Badge>
                </CardContent>
              </Card>
            ))}
          </>
        )}
      </div>

      <InviteUserDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        roles={roles}
        onInviteSent={handleInviteSent}
      />
    </div>
  );
}
