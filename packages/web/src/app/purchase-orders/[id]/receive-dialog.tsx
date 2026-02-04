"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PackageCheck, Loader2, AlertCircle, Package } from "lucide-react";
import { toast } from "sonner";

interface POLine {
  id: string;
  productId: string;
  quantityOrdered: number;
  quantityReceived: number;
  unitCost: number;
  product: {
    id: string;
    sku: string;
    name: string;
    images?: Array<{ url: string }>;
  } | null;
}

interface PurchaseOrder {
  id: string;
  poNumber: string;
  lines: POLine[];
}

export function ReceiveDialog({ po }: { po: PurchaseOrder }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track quantities to receive for each line
  const [quantities, setQuantities] = useState<Record<string, number>>(() => {
    const initial: Record<string, number> = {};
    po.lines.forEach((line) => {
      // Default to remaining quantity
      initial[line.id] = Math.max(0, line.quantityOrdered - line.quantityReceived);
    });
    return initial;
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Filter to only lines with quantities > 0
      const linesToReceive = Object.entries(quantities)
        .filter(([, qty]) => qty > 0)
        .map(([lineId, quantityReceived]) => ({ lineId, quantityReceived }));

      if (linesToReceive.length === 0) {
        throw new Error("No quantities to receive");
      }

      const res = await fetch(`/api/purchase-orders/${po.id}/receive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lines: linesToReceive }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to receive items");
      }

      toast.success("Items received and inventory updated");
      setOpen(false);
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const receiveAll = () => {
    const allRemaining: Record<string, number> = {};
    po.lines.forEach((line) => {
      allRemaining[line.id] = Math.max(0, line.quantityOrdered - line.quantityReceived);
    });
    setQuantities(allRemaining);
  };

  const clearAll = () => {
    const empty: Record<string, number> = {};
    po.lines.forEach((line) => {
      empty[line.id] = 0;
    });
    setQuantities(empty);
  };

  const totalToReceive = Object.values(quantities).reduce((sum, qty) => sum + qty, 0);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <PackageCheck className="h-4 w-4 mr-2" /> Receive Items
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Receive Items</DialogTitle>
            <DialogDescription>
              Enter the quantities received for {po.poNumber}. This will update inventory.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4 space-y-4">
            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" size="sm" onClick={clearAll}>
                Clear All
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={receiveAll}>
                Receive All Remaining
              </Button>
            </div>

            <div className="space-y-3 max-h-[400px] overflow-y-auto">
              {po.lines.map((line) => {
                const remaining = line.quantityOrdered - line.quantityReceived;
                const isComplete = line.quantityReceived >= line.quantityOrdered;
                
                return (
                  <div
                    key={line.id}
                    className={`flex items-center gap-4 p-3 rounded-lg border ${isComplete ? "bg-green-50 border-green-200" : ""}`}
                  >
                    <div className="flex-shrink-0">
                      {line.product?.images?.[0] ? (
                        <img
                          src={line.product.images[0].url}
                          alt=""
                          className="h-12 w-12 rounded object-cover"
                        />
                      ) : (
                        <div className="h-12 w-12 rounded bg-muted flex items-center justify-center">
                          <Package className="h-5 w-5 text-muted-foreground" />
                        </div>
                      )}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{line.product?.name ?? "Unknown Product"}</div>
                      <div className="text-sm text-muted-foreground">
                        {line.product?.sku ?? "N/A"} • Ordered: {line.quantityOrdered} • Received: {line.quantityReceived}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {!isComplete ? (
                        <>
                          <Label htmlFor={`qty-${line.id}`} className="sr-only">
                            Quantity
                          </Label>
                          <Input
                            id={`qty-${line.id}`}
                            type="number"
                            min="0"
                            max={remaining}
                            value={quantities[line.id] || 0}
                            onChange={(e) =>
                              setQuantities({ ...quantities, [line.id]: parseInt(e.target.value) || 0 })
                            }
                            className="w-20 text-center"
                          />
                          <span className="text-sm text-muted-foreground">/ {remaining}</span>
                        </>
                      ) : (
                        <span className="text-green-600 font-medium">Complete ✓</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {totalToReceive > 0 && (
              <div className="text-sm font-medium text-right">
                Total to receive: {totalToReceive} items
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive mb-4">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || totalToReceive === 0}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Receive {totalToReceive} Items
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
