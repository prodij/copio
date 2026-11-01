import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { createWorkspace } from "@/api/queries";
import { ApiError } from "@/api/errors";
import { userManager } from "@/auth/userManager";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function CreateWorkspace() {
  const [name, setName] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: async (n: string) => {
      const ws = await createWorkspace(n);
      // The current token has no role for the new org yet; renew it so /me shows the workspace.
      try {
        await userManager.signinSilent();
      } catch {
        throw new ApiError(0, "Workspace created, but refreshing your sign-in failed. Sign out and in again.");
      }
      return ws;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      void navigate("/plans");
    },
  });
  return (
    <form className="max-w-sm space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate(name.trim()); }}>
      <Label htmlFor="ws-name">Workspace name</Label>
      <Input id="ws-name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
      {create.error && <ErrorState error={create.error as ApiError} />}
      <Button type="submit" disabled={!name.trim() || create.isPending}>Create workspace</Button>
    </form>
  );
}
