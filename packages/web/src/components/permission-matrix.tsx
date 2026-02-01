"use client";

import { Checkbox } from "@/components/ui/checkbox";

interface PermissionMatrixProps {
  allPermissions: Record<string, string[]>; // resource -> actions
  selectedPermissions: string[];
  onChange: (permission: string, enabled: boolean) => void;
  disabled?: boolean;
}

const actionLabels: Record<string, string> = {
  view: "View",
  create: "Create",
  edit: "Edit",
  delete: "Delete",
  adjust: "Adjust",
  receive: "Receive",
  invite: "Invite",
  assign: "Assign",
  export: "Export",
};

export function PermissionMatrix({
  allPermissions,
  selectedPermissions,
  onChange,
  disabled,
}: PermissionMatrixProps) {
  const resources = Object.keys(allPermissions);
  const allActions = [...new Set(Object.values(allPermissions).flat())];

  const hasPermission = (resource: string, action: string) => {
    const perm = `${resource}:${action}`;
    return (
      selectedPermissions.includes(perm) ||
      selectedPermissions.includes("*:*") ||
      selectedPermissions.includes(`${resource}:*`) ||
      selectedPermissions.includes(`*:${action}`)
    );
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="text-left py-2 px-3 font-medium">Resource</th>
            {allActions.map((action) => (
              <th key={action} className="text-center py-2 px-3 font-medium capitalize">
                {actionLabels[action] || action}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {resources.map((resource) => (
            <tr key={resource} className="border-b hover:bg-muted/50">
              <td className="py-2 px-3 capitalize">{resource.replace(/_/g, " ")}</td>
              {allActions.map((action) => {
                const available = allPermissions[resource]?.includes(action);
                const checked = hasPermission(resource, action);
                return (
                  <td key={action} className="text-center py-2 px-3">
                    {available ? (
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(v) => onChange(`${resource}:${action}`, !!v)}
                        disabled={disabled}
                      />
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
