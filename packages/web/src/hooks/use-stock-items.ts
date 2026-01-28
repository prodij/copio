"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

// Types matching the API response
export interface Product {
  id: string;
  sku: string;
  name: string;
  brand: string | null;
  category: string | null;
}

export interface Location {
  id: string;
  name: string;
  type: "WAREHOUSE" | "FBA" | "THREEPEL";
}

export interface StockItem {
  id: string;
  productId: string;
  locationId: string;
  quantityAvailable: number;
  quantityReserved: number;
  quantityInbound: number;
  costBasis: string | null; // Decimal comes as string from API
  createdAt: string;
  updatedAt: string;
  product: Product;
  location: Location;
}

export interface CreateStockItemInput {
  productId: string;
  locationId: string;
  quantityAvailable?: number;
  quantityReserved?: number;
  quantityInbound?: number;
  costBasis?: number;
}

// Query keys
const stockItemKeys = {
  all: ["stockItems"] as const,
  lists: () => [...stockItemKeys.all, "list"] as const,
  list: (filters?: { locationId?: string; productId?: string }) =>
    [...stockItemKeys.lists(), filters] as const,
  details: () => [...stockItemKeys.all, "detail"] as const,
  detail: (id: string) => [...stockItemKeys.details(), id] as const,
  byLocation: (locationId: string) =>
    [...stockItemKeys.all, "byLocation", locationId] as const,
  byProduct: (productId: string) =>
    [...stockItemKeys.all, "byProduct", productId] as const,
};

// Fetch all stock items with product/location relations
export function useStockItems() {
  return useQuery({
    queryKey: stockItemKeys.lists(),
    queryFn: () => apiFetch<StockItem[]>("/stock-items"),
  });
}

// Fetch a single stock item by ID
export function useStockItem(id: string) {
  return useQuery({
    queryKey: stockItemKeys.detail(id),
    queryFn: () => apiFetch<StockItem>(`/stock-items/${id}`),
    enabled: !!id,
  });
}

// Fetch stock items by location
export function useStockItemsByLocation(locationId: string) {
  return useQuery({
    queryKey: stockItemKeys.byLocation(locationId),
    queryFn: () =>
      apiFetch<StockItem[]>(`/stock-items/by-location/${locationId}`),
    enabled: !!locationId,
  });
}

// Fetch stock items by product
export function useStockItemsByProduct(productId: string) {
  return useQuery({
    queryKey: stockItemKeys.byProduct(productId),
    queryFn: () =>
      apiFetch<StockItem[]>(`/stock-items/by-product/${productId}`),
    enabled: !!productId,
  });
}

// Create a new stock item
export function useCreateStockItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateStockItemInput) =>
      apiFetch<StockItem>("/stock-items", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      // Invalidate all stock item queries to refetch
      queryClient.invalidateQueries({ queryKey: stockItemKeys.all });
    },
  });
}
