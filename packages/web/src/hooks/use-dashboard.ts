"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch, type Product, type Location, type StockItem, type StockMovement } from "@/lib/api";

export function useProducts() {
  return useQuery({
    queryKey: ["products"],
    queryFn: () => apiFetch<Product[]>("/products"),
  });
}

export function useLocations() {
  return useQuery({
    queryKey: ["locations"],
    queryFn: () => apiFetch<Location[]>("/locations"),
  });
}

export function useStockItems() {
  return useQuery({
    queryKey: ["stock-items"],
    queryFn: () => apiFetch<StockItem[]>("/stock-items"),
  });
}

export function useRecentMovements(limit: number = 10) {
  return useQuery({
    queryKey: ["stock-movements", "recent", limit],
    queryFn: () => apiFetch<StockMovement[]>(`/stock-movements?limit=${limit}`),
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
  const lowStockItems = stockItems.data?.filter((item) => item.quantityAvailable < LOW_STOCK_THRESHOLD) ?? [];

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
