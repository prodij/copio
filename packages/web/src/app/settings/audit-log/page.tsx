"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Download, Search, ChevronLeft, ChevronRight } from "lucide-react";

interface AuditEntry {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, any> | null;
  ip_address: string | null;
  created_at: string;
}

interface AuditResponse {
  items: AuditEntry[];
  total: number;
  page: number;
  page_size: number;
}

const actionColors: Record<string, string> = {
  login: "bg-green-100 text-green-800",
  logout: "bg-gray-100 text-gray-800",
  permission_denied: "bg-red-100 text-red-800",
  resource_created: "bg-blue-100 text-blue-800",
  resource_updated: "bg-yellow-100 text-yellow-800",
  resource_deleted: "bg-red-100 text-red-800",
  role_assigned: "bg-purple-100 text-purple-800",
  role_removed: "bg-orange-100 text-orange-800",
};

export default function AuditLogPage() {
  const [data, setData] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState<string>("");
  const [page, setPage] = useState(1);

  const fetchData = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set("page", page.toString());
    if (actionFilter) params.set("action", actionFilter);

    const res = await fetch(`/api/v1/audit-log?${params}`);
    const result = await res.json();
    setData(result);
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, [page, actionFilter]);

  const handleExport = () => {
    window.open("/api/v1/audit-log/export", "_blank");
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Audit Log</h1>
          <p className="text-muted-foreground">Track all security-relevant events</p>
        </div>
        <Button variant="outline" onClick={handleExport}>
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </div>

      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="flex gap-4">
            <Select value={actionFilter} onValueChange={setActionFilter}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Filter by action" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Actions</SelectItem>
                <SelectItem value="login">Login</SelectItem>
                <SelectItem value="logout">Logout</SelectItem>
                <SelectItem value="permission_denied">Permission Denied</SelectItem>
                <SelectItem value="resource_created">Resource Created</SelectItem>
                <SelectItem value="resource_updated">Resource Updated</SelectItem>
                <SelectItem value="resource_deleted">Resource Deleted</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div>Loading...</div>
      ) : (
        <>
          <div className="space-y-2">
            {data?.items.map((entry) => (
              <Card key={entry.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
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
                        <div className="text-sm text-muted-foreground">
                          {JSON.stringify(entry.details)}
                        </div>
                      )}
                    </div>
                    <div className="text-right text-sm text-muted-foreground">
                      <div>{formatDate(entry.created_at)}</div>
                      {entry.ip_address && <div>{entry.ip_address}</div>}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="flex items-center justify-between mt-6">
            <div className="text-sm text-muted-foreground">
              Showing {data?.items.length} of {data?.total} entries
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page - 1)}
                disabled={page <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">
                Page {page} of {totalPages}
              </span>
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
        </>
      )}
    </div>
  );
}
