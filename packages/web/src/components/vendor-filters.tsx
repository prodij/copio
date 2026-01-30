"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useTransition, useState, useEffect, useRef } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const TIERS = [
  { value: "all", label: "All Tiers" },
  { value: "STRATEGIC", label: "Strategic" },
  { value: "PREFERRED", label: "Preferred" },
  { value: "STANDARD", label: "Standard" },
  { value: "PROBATIONARY", label: "Probationary" },
];

const STATUSES = [
  { value: "all", label: "All Status" },
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
];

export function VendorFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const searchParam = searchParams.get("search") || "";
  const tier = searchParams.get("tier") || "all";
  const status = searchParams.get("status") || "all";

  // Local state for debounced search
  const [searchValue, setSearchValue] = useState(searchParam);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Sync local state when URL param changes (e.g., on clear)
  useEffect(() => {
    setSearchValue(searchParam);
  }, [searchParam]);

  const hasFilters = searchParam || tier !== "all" || status !== "all";

  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      
      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === "" || value === "all") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      });

      startTransition(() => {
        router.push(`/vendors?${params.toString()}`);
      });
    },
    [router, searchParams]
  );

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchValue(value);
      
      // Clear existing timeout
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
      
      // Set new timeout for 500ms
      debounceRef.current = setTimeout(() => {
        updateParams({ search: value });
      }, 500);
    },
    [updateParams]
  );

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  const clearFilters = () => {
    startTransition(() => {
      router.push("/vendors");
    });
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative flex-1 min-w-[200px] max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search vendors..."
          value={searchValue}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>

      <Select value={tier} onValueChange={(value) => updateParams({ tier: value })}>
        <SelectTrigger className="w-[140px]">
          <SelectValue placeholder="Tier" />
        </SelectTrigger>
        <SelectContent>
          {TIERS.map((t) => (
            <SelectItem key={t.value} value={t.value}>
              {t.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={status} onValueChange={(value) => updateParams({ status: value })}>
        <SelectTrigger className="w-[130px]">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          {STATUSES.map((s) => (
            <SelectItem key={s.value} value={s.value}>
              {s.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9">
          <X className="h-4 w-4 mr-1" />
          Clear
        </Button>
      )}

      {isPending && (
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      )}
    </div>
  );
}
