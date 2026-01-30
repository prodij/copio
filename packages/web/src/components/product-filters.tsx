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

const STATUSES = [
  { value: "all", label: "All Status" },
  { value: "DRAFT", label: "Draft" },
  { value: "ACTIVE", label: "Active" },
  { value: "ARCHIVED", label: "Archived" },
];

const CHANNELS = [
  { value: "all", label: "All Channels" },
  { value: "AMAZON", label: "Amazon" },
  { value: "SHOPIFY", label: "Shopify" },
  { value: "WALMART", label: "Walmart" },
  { value: "EBAY", label: "eBay" },
];

interface ProductFiltersProps {
  brands: string[];
}

export function ProductFilters({ brands }: ProductFiltersProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const searchParam = searchParams.get("search") || "";
  const status = searchParams.get("status") || "all";
  const channel = searchParams.get("channel") || "all";
  const brand = searchParams.get("brand") || "all";

  // Local state for debounced search
  const [searchValue, setSearchValue] = useState(searchParam);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Sync local state when URL param changes (e.g., on clear)
  useEffect(() => {
    setSearchValue(searchParam);
  }, [searchParam]);

  const hasFilters = searchParam || status !== "all" || channel !== "all" || brand !== "all";

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
        router.push(`/products?${params.toString()}`);
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
      router.push("/products");
    });
  };

  const brandOptions = [
    { value: "all", label: "All Brands" },
    ...brands.map((b) => ({ value: b, label: b })),
  ];

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative flex-1 min-w-[200px] max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search products..."
          value={searchValue}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>

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

      <Select value={channel} onValueChange={(value) => updateParams({ channel: value })}>
        <SelectTrigger className="w-[140px]">
          <SelectValue placeholder="Channel" />
        </SelectTrigger>
        <SelectContent>
          {CHANNELS.map((c) => (
            <SelectItem key={c.value} value={c.value}>
              {c.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {brands.length > 0 && (
        <Select value={brand} onValueChange={(value) => updateParams({ brand: value })}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Brand" />
          </SelectTrigger>
          <SelectContent>
            {brandOptions.map((b) => (
              <SelectItem key={b.value} value={b.value}>
                {b.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

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
