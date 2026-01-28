"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { MoreHorizontal, Send, CheckCircle, XCircle, Trash2, Loader2 } from "lucide-react";

interface PurchaseOrder {
  id: string;
  poNumber: string;
  status: string;
}

export function POActions({ po }: { po: PurchaseOrder }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const updateStatus = async (status: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/purchase-orders/${po.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to update status");
      }
      router.refresh();
    } catch (error) {
      console.error("Failed to update status:", error);
    } finally {
      setLoading(false);
    }
  };

  const deletePO = async () => {
    const res = await fetch(`/api/purchase-orders/${po.id}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Failed to delete PO");
    }
    router.push("/purchase-orders");
  };

  const cancelPO = async () => {
    await updateStatus("CANCELLED");
  };

  return (
    <div className="flex items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <MoreHorizontal className="h-4 w-4" />}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {po.status === "DRAFT" && (
            <DropdownMenuItem onClick={() => updateStatus("SUBMITTED")}>
              <Send className="mr-2 h-4 w-4" />
              Submit Order
            </DropdownMenuItem>
          )}
          {po.status === "SUBMITTED" && (
            <DropdownMenuItem onClick={() => updateStatus("CONFIRMED")}>
              <CheckCircle className="mr-2 h-4 w-4" />
              Mark Confirmed
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {(po.status === "DRAFT" || po.status === "SUBMITTED") && (
        <ConfirmDialog
          trigger={
            <Button variant="outline" size="icon" className="text-destructive hover:text-destructive">
              <XCircle className="h-4 w-4" />
            </Button>
          }
          title="Cancel Purchase Order?"
          description={`Are you sure you want to cancel ${po.poNumber}? This will mark the order as cancelled.`}
          confirmText="Cancel Order"
          variant="destructive"
          onConfirm={cancelPO}
        />
      )}

      {(po.status === "DRAFT" || po.status === "CANCELLED") && (
        <ConfirmDialog
          trigger={
            <Button variant="outline" size="icon" className="text-destructive hover:text-destructive">
              <Trash2 className="h-4 w-4" />
            </Button>
          }
          title="Delete Purchase Order?"
          description={`Are you sure you want to delete ${po.poNumber}? This action cannot be undone.`}
          confirmText="Delete"
          variant="destructive"
          onConfirm={deletePO}
        />
      )}
    </div>
  );
}
