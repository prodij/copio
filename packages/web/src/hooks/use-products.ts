import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// Types based on Prisma schema
export interface ChannelListing {
  id: string;
  productId: string;
  channel: "AMAZON" | "SHOPIFY" | "WALMART";
  channelSku: string;
  channelData: Record<string, unknown>;
  status: "ACTIVE" | "INACTIVE" | "SUPPRESSED";
  syncedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  brand: string | null;
  category: string | null;
  attributes: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  listings: ChannelListing[];
}

export interface CreateProductInput {
  name: string;
  sku: string;
  brand?: string;
  category?: string;
  attributes?: Record<string, unknown>;
  channelListings?: Array<{
    channel: "AMAZON" | "SHOPIFY" | "WALMART";
    channelSku: string;
    channelData?: Record<string, unknown>;
    status?: "ACTIVE" | "INACTIVE" | "SUPPRESSED";
  }>;
}

export interface UpdateProductInput {
  name?: string;
  brand?: string;
  category?: string;
  attributes?: Record<string, unknown>;
}

// Fetch all products
export function useProducts() {
  return useQuery<Product[]>({
    queryKey: ["products"],
    queryFn: async () => {
      const { data } = await api.get("/products");
      return data;
    },
  });
}

// Fetch single product
export function useProduct(id: string | undefined) {
  return useQuery<Product>({
    queryKey: ["products", id],
    queryFn: async () => {
      const { data } = await api.get(`/products/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

// Create product mutation
export function useCreateProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreateProductInput) => {
      const { data } = await api.post("/products", input);
      return data as Product;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
}

// Update product mutation
export function useUpdateProduct() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      ...input
    }: UpdateProductInput & { id: string }) => {
      const { data } = await api.patch(`/products/${id}`, input);
      return data as Product;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["products", data.id] });
    },
  });
}
