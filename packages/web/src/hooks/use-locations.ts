"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Location {
  id: string;
  name: string;
  type: "WAREHOUSE" | "FBA" | "THREEPEL";
  channel: string | null;
  address?: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface CreateLocationInput {
  name: string;
  type: string;
  channel?: string;
  address?: Record<string, unknown>;
}

const locationKeys = {
  all: ["locations"] as const,
  lists: () => [...locationKeys.all, "list"] as const,
  detail: (id: string) => [...locationKeys.all, "detail", id] as const,
};

export function useLocations() {
  return useQuery({
    queryKey: locationKeys.lists(),
    queryFn: () => apiFetch<Location[]>("/locations"),
  });
}

export function useLocation(id: string | undefined) {
  return useQuery({
    queryKey: locationKeys.detail(id!),
    queryFn: () => apiFetch<Location>(`/locations/${id}`),
    enabled: !!id,
  });
}

export function useCreateLocation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateLocationInput) =>
      apiFetch<Location>("/locations", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: locationKeys.all });
    },
  });
}

export function useUpdateLocation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, ...data }: CreateLocationInput & { id: string }) =>
      apiFetch<Location>(`/locations/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: locationKeys.all });
    },
  });
}
