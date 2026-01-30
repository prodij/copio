"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

interface PaginationProps {
  total: number;
  pageSize?: number;
  pageSizeOptions?: number[];
}

export function Pagination({
  total,
  pageSize: defaultPageSize = 25,
  pageSizeOptions = [10, 25, 50, 100],
}: PaginationProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = Number(searchParams.get("page")) || 1;
  const pageSize = Number(searchParams.get("pageSize")) || defaultPageSize;
  const totalPages = Math.ceil(total / pageSize);

  const createQueryString = (params: Record<string, string | number>) => {
    const newParams = new URLSearchParams(searchParams.toString());
    Object.entries(params).forEach(([key, value]) => {
      newParams.set(key, String(value));
    });
    return newParams.toString();
  };

  const goToPage = (newPage: number) => {
    router.push(`${pathname}?${createQueryString({ page: newPage })}`);
  };

  const changePageSize = (newSize: string) => {
    router.push(`${pathname}?${createQueryString({ page: 1, pageSize: newSize })}`);
  };

  const startItem = (page - 1) * pageSize + 1;
  const endItem = Math.min(page * pageSize, total);

  if (total === 0) return null;

  return (
    <div className="flex items-center justify-between px-2 py-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>
          Showing {startItem}-{endItem} of {total}
        </span>
        <Select value={String(pageSize)} onValueChange={changePageSize}>
          <SelectTrigger className="h-8 w-[70px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {pageSizeOptions.map((size) => (
              <SelectItem key={size} value={String(size)}>
                {size}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span>per page</span>
      </div>

      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => goToPage(1)}
          disabled={page <= 1}
        >
          <ChevronsLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => goToPage(page - 1)}
          disabled={page <= 1}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="px-3 text-sm">
          Page {page} of {totalPages}
        </span>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => goToPage(page + 1)}
          disabled={page >= totalPages}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => goToPage(totalPages)}
          disabled={page >= totalPages}
        >
          <ChevronsRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
