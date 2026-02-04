"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Download, ChevronLeft, ChevronRight } from "lucide-react";

interface AuditEntry {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

interface AuditResponse {
  data: AuditEntry[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
}

const actionColors: Record<string, string> = {
  login: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  logout: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  permission_denied: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  resource_created: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  resource_updated: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  resource_deleted: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  role_assigned: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  role_removed: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
};

function LoadingSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center justify-between p-4 border rounded-lg">
          <div className="space-y-2">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-4 w-48" />
          </div>
          <Skeleton className="h-4 w-32" />
        </div>
      ))}
    </div>
  );
}

export default function AuditLogPage() {
  const { isAuthenticated } = useAuth();
  const [data, setData] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [page, setPage] = useState(1);

  const fetchData = async () => {
    if (!isAuthenticated) return;

    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", page.toString());
      if (actionFilter && actionFilter !== "all") params.set("action", actionFilter);

      const res = await fetch(`/api/v1/audit-log?${params}`, {
        credentials: "include",
      });

      if (res.ok) {
        const result = await res.json();
        setData(result);
      } else {
        setData({ data: [], pagination: { page: 1, pageSize: 20, total: 0, totalPages: 0 } });
      }
    } catch {
      setData({ data: [], pagination: { page: 1, pageSize: 20, total: 0, totalPages: 0 } });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, actionFilter, isAuthenticated]);

  const handleExport = () => {
    // Export uses cookies for auth, no token needed
    window.open("/api/v1/audit-log/export", "_blank");
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const totalPages = data?.pagination.totalPages ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Audit Log</h1>
          <p className="text-muted-foreground">Track all security-relevant events</p>
        </div>
        <Button variant="outline" onClick={handleExport}>
          <Download className="mr-2 h-4 w-4" />
          Export
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Events</CardTitle>
              <CardDescription>
                {data?.pagination.total || 0} total event{data?.pagination.total !== 1 ? "s" : ""}
              </CardDescription>
            </div>
            <Select value={actionFilter} onValueChange={setActionFilter}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Filter by action" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Actions</SelectItem>
                <SelectItem value="login">Login</SelectItem>
                <SelectItem value="logout">Logout</SelectItem>
                <SelectItem value="permission_denied">Permission Denied</SelectItem>
                <SelectItem value="resource_created">Resource Created</SelectItem>
                <SelectItem value="resource_updated">Resource Updated</SelectItem>
                <SelectItem value="resource_deleted">Resource Deleted</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <LoadingSkeleton />
          ) : (
            <div className="space-y-2">
              {data?.data.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">No events found</p>
              ) : (
                data?.data.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-start justify-between p-4 border rounded-lg"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge className={actionColors[entry.action] || "bg-gray-100"}>
                          {entry.action.replace(/_/g, " ")}
                        </Badge>
                        {entry.resource_type && (
                          <span className="text-sm text-muted-foreground">
                            on {entry.resource_type}
                          </span>
                        )}
                      </div>
                      {entry.details && (
                        <p className="text-sm text-muted-foreground font-mono">
                          {JSON.stringify(entry.details)}
                        </p>
                      )}
                    </div>
                    <div className="text-right text-sm text-muted-foreground">
                      <div>{formatDate(entry.created_at)}</div>
                      {entry.ip_address && <div className="font-mono">{entry.ip_address}</div>}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t">
              <p className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page - 1)}
                  disabled={page <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page + 1)}
                  disabled={page >= totalPages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
