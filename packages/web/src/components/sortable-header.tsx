"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TableHead } from "@/components/ui/table";

interface SortableHeaderProps {
  field: string;
  children: React.ReactNode;
  className?: string;
}

export function SortableHeader({ field, children, className }: SortableHeaderProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const currentSort = searchParams.get("sortBy");
  const currentDir = searchParams.get("sortDir") || "asc";
  const isActive = currentSort === field;

  const handleSort = () => {
    const params = new URLSearchParams(searchParams.toString());
    
    if (isActive) {
      // Toggle direction
      params.set("sortDir", currentDir === "asc" ? "desc" : "asc");
    } else {
      // Set new sort field with default desc for dates, asc for text
      params.set("sortBy", field);
      params.set("sortDir", ["createdAt", "leadTimeDays", "minOrderValue"].includes(field) ? "desc" : "asc");
    }
    
    router.push(`?${params.toString()}`);
  };

  return (
    <TableHead className={className}>
      <Button
        variant="ghost"
        size="sm"
        className="-ml-3 h-8 hover:bg-transparent"
        onClick={handleSort}
      >
        {children}
        {isActive ? (
          currentDir === "asc" ? (
            <ArrowUp className="ml-1 h-3 w-3" />
          ) : (
            <ArrowDown className="ml-1 h-3 w-3" />
          )
        ) : (
          <ArrowUpDown className="ml-1 h-3 w-3 opacity-50" />
        )}
      </Button>
    </TableHead>
  );
}
