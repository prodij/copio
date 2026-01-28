"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch, type StockMovement } from "@/lib/api";
import { useProducts } from "./use-products";
import { useLocations } from "./use-locations";
import { useStockItems, type StockItem } from "./use-stock-items";

export function useRecentMovements(limit: number = 10) {
  return useQuery({
    queryKey: ["stock-movements", "recent", limit],
    queryFn: () => apiFetch<StockMovement[]>(`/stock-movements`),
    select: (data) => data.slice(0, limit),
  });
}

export function useDashboardStats() {
  const products = useProducts();
  const locations = useLocations();
  const stockItems = useStockItems();
  const movements = useRecentMovements(10);

  const isLoading = products.isLoading || locations.isLoading || stockItems.isLoading || movements.isLoading;
  const isError = products.isError || locations.isError || stockItems.isError || movements.isError;

  const totalProducts = products.data?.length ?? 0;
  const totalLocations = locations.data?.length ?? 0;
  const totalStockItems = stockItems.data?.length ?? 0;
  const totalUnits = stockItems.data?.reduce((sum, item) => sum + item.quantityAvailable, 0) ?? 0;

  const LOW_STOCK_THRESHOLD = 10;
  const lowStockItems: StockItem[] = stockItems.data?.filter((item) => item.quantityAvailable < LOW_STOCK_THRESHOLD) ?? [];

  return {
    isLoading,
    isError,
    stats: {
      totalProducts,
      totalLocations,
      totalStockItems,
      totalUnits,
      lowStockCount: lowStockItems.length,
    },
    lowStockItems,
    recentMovements: movements.data ?? [],
  };
}
