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
import { Textarea } from "@/components/ui/textarea";
import { Phone, Loader2, AlertCircle, Clock } from "lucide-react";

interface PurchaseOrder {
  id: string;
  poNumber: string;
  lastContactedAt: string | null;
  nextFollowUpAt: string | null;
  followUpNotes: string | null;
}

export function FollowUpDialog({ po }: { po: PurchaseOrder }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    notes: po.followUpNotes || "",
    nextFollowUpDays: "",
  });

  const handleLogContact = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/purchase-orders/${po.id}/log-contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          notes: formData.notes || undefined,
          nextFollowUpDays: formData.nextFollowUpDays ? parseInt(formData.nextFollowUpDays) : undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to log contact");
      }

      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const quickFollowUp = async (days: number) => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/purchase-orders/${po.id}/log-contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nextFollowUpDays: days }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to set follow-up");
      }

      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Phone className="h-4 w-4 mr-2" />
          Follow Up
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[450px]">
        <form onSubmit={handleLogContact}>
          <DialogHeader>
            <DialogTitle>Vendor Follow-Up</DialogTitle>
            <DialogDescription>
              Log contact with vendor for {po.poNumber}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="flex items-center gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Last contacted:</span>{" "}
                <span className="font-medium">{formatDate(po.lastContactedAt)}</span>
              </div>
              {po.nextFollowUpAt && (
                <div>
                  <span className="text-muted-foreground">Next follow-up:</span>{" "}
                  <span className="font-medium">{formatDate(po.nextFollowUpAt)}</span>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Quick Actions</Label>
              <div className="flex gap-2 flex-wrap">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => quickFollowUp(1)}
                  disabled={loading}
                >
                  <Clock className="h-3 w-3 mr-1" />
                  +1 day
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => quickFollowUp(3)}
                  disabled={loading}
                >
                  <Clock className="h-3 w-3 mr-1" />
                  +3 days
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => quickFollowUp(7)}
                  disabled={loading}
                >
                  <Clock className="h-3 w-3 mr-1" />
                  +1 week
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="What was discussed? Any updates from vendor?"
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="nextFollowUpDays">Follow up in (days)</Label>
              <Input
                id="nextFollowUpDays"
                type="number"
                min="1"
                value={formData.nextFollowUpDays}
                onChange={(e) => setFormData({ ...formData, nextFollowUpDays: e.target.value })}
                placeholder="e.g., 3"
              />
            </div>
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
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Log Contact
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
