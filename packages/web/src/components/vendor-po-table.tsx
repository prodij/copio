"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface PurchaseOrder {
  id: string;
  poNumber: string;
  status: string;
  subtotal: number | null;
  total: number | null;
  createdAt: string;
  orderedAt: string | null;
  expectedAt: string | null;
  receivedAt: string | null;
  destination: { id: string; name: string; type: string } | null;
  _count: { lines: number };
}

interface VendorPOTableProps {
  purchaseOrders: PurchaseOrder[];
}

const PO_STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300",
  SUBMITTED: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  CONFIRMED: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300",
  SHIPPED: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  PARTIAL: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  RECEIVED: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  CANCELLED: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  CLOSED: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

type SortField = "poNumber" | "status" | "total" | "createdAt" | "orderedAt" | "expectedAt" | "receivedAt" | "lines";
type SortDir = "asc" | "desc";

export function VendorPOTable({ purchaseOrders }: VendorPOTableProps) {
  const [sortField, setSortField] = useState<SortField>("createdAt");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const sortedPOs = useMemo(() => {
    return [...purchaseOrders].sort((a, b) => {
      let aVal: string | number | null;
      let bVal: string | number | null;

      switch (sortField) {
        case "poNumber":
          aVal = a.poNumber;
          bVal = b.poNumber;
          break;
        case "status":
          aVal = a.status;
          bVal = b.status;
          break;
        case "total":
          aVal = a.total;
          bVal = b.total;
          break;
        case "createdAt":
          aVal = a.createdAt;
          bVal = b.createdAt;
          break;
        case "orderedAt":
          aVal = a.orderedAt;
          bVal = b.orderedAt;
          break;
        case "expectedAt":
          aVal = a.expectedAt;
          bVal = b.expectedAt;
          break;
        case "receivedAt":
          aVal = a.receivedAt;
          bVal = b.receivedAt;
          break;
        case "lines":
          aVal = a._count?.lines || 0;
          bVal = b._count?.lines || 0;
          break;
        default:
          return 0;
      }

      // Handle nulls
      if (aVal === null && bVal === null) return 0;
      if (aVal === null) return sortDir === "asc" ? 1 : -1;
      if (bVal === null) return sortDir === "asc" ? -1 : 1;

      // Compare
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc" 
          ? aVal.localeCompare(bVal) 
          : bVal.localeCompare(aVal);
      }

      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }

      return 0;
    });
  }, [purchaseOrders, sortField, sortDir]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return <ArrowUpDown className="ml-1 h-3 w-3 opacity-50" />;
    }
    return sortDir === "asc" 
      ? <ArrowUp className="ml-1 h-3 w-3" />
      : <ArrowDown className="ml-1 h-3 w-3" />;
  };

  const SortableHeader = ({ field, children, className }: { field: SortField; children: React.ReactNode; className?: string }) => (
    <TableHead className={className}>
      <Button
        variant="ghost"
        size="sm"
        className="-ml-3 h-8 hover:bg-transparent"
        onClick={() => handleSort(field)}
      >
        {children}
        <SortIcon field={field} />
      </Button>
    </TableHead>
  );

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <SortableHeader field="poNumber">PO Number</SortableHeader>
          <SortableHeader field="status">Status</SortableHeader>
          <TableHead>Destination</TableHead>
          <SortableHeader field="lines" className="text-center">Lines</SortableHeader>
          <SortableHeader field="total" className="text-right">Total</SortableHeader>
          <SortableHeader field="createdAt">Created</SortableHeader>
          <SortableHeader field="orderedAt">Ordered</SortableHeader>
          <SortableHeader field="expectedAt">Expected</SortableHeader>
          <SortableHeader field="receivedAt">Received</SortableHeader>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedPOs.map((po) => (
          <TableRow key={po.id}>
            <TableCell>
              <Link href={`/purchase-orders/${po.id}`} className="font-medium hover:underline">
                {po.poNumber}
              </Link>
            </TableCell>
            <TableCell>
              <Badge variant="outline" className={PO_STATUS_COLORS[po.status] || PO_STATUS_COLORS.DRAFT}>
                {po.status}
              </Badge>
            </TableCell>
            <TableCell>
              <span className="text-sm">{po.destination?.name || "—"}</span>
            </TableCell>
            <TableCell className="text-center">{po._count?.lines || 0}</TableCell>
            <TableCell className="text-right font-medium">
              {po.total ? `$${Number(po.total).toLocaleString(undefined, { minimumFractionDigits: 2 })}` : "—"}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {new Date(po.createdAt).toLocaleDateString()}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {po.orderedAt ? new Date(po.orderedAt).toLocaleDateString() : "—"}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {po.expectedAt ? new Date(po.expectedAt).toLocaleDateString() : "—"}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {po.receivedAt ? new Date(po.receivedAt).toLocaleDateString() : "—"}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
