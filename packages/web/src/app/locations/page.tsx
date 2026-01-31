import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { MapPin } from "lucide-react";
import { CreateLocationDialog } from "./create-dialog";

const API_URL = process.env.API_URL || 'http://localhost:8001/api/v1';

interface Location {
  id: string;
  name: string;
  type: string;
  channel: string | null;
  address: Record<string, unknown> | null;
  createdAt: string;
}

async function getLocations(): Promise<Location[]> {
  const res = await fetch(`${API_URL}/locations`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch locations');
  return res.json();
}

function getTypeBadgeVariant(type: string): "warehouse" | "fba" | "threepel" | "secondary" {
  const typeMap: Record<string, "warehouse" | "fba" | "threepel"> = {
    WAREHOUSE: "warehouse",
    FBA: "fba",
    THREEPEL: "threepel",
  };
  return typeMap[type] || "secondary";
}

function getChannelBadgeVariant(channel: string): "shopify" | "amazon" | "faire" | "internal" | "outline" {
  const channelMap: Record<string, "shopify" | "amazon" | "faire" | "internal"> = {
    SHOPIFY: "shopify",
    AMAZON: "amazon",
    WALMART: "amazon",
    FAIRE: "faire",
    INTERNAL: "internal",
  };
  return channelMap[channel] || "outline";
}

function formatDate(date: string) {
  return new Date(date).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatAddress(address: unknown): string {
  if (!address || typeof address !== "object") return "—";
  const addr = address as Record<string, unknown>;
  const parts = [addr.street, addr.city, addr.state, addr.zip].filter(Boolean);
  return parts.length > 0 ? parts.join(", ") : "—";
}

export default async function LocationsPage() {
  const locations = await getLocations();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Locations</h1>
          <p className="text-muted-foreground">Manage your warehouses and storage locations.</p>
        </div>
        <CreateLocationDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Storage Locations</CardTitle>
          <CardDescription>Warehouses and facilities where inventory is stored.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead>Address</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {locations.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-24 text-center">
                    <div className="flex flex-col items-center gap-2 text-muted-foreground">
                      <MapPin className="h-8 w-8" />
                      <p>No locations yet. Add your first warehouse or storage location.</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                locations.map((location) => (
                  <TableRow key={location.id}>
                    <TableCell className="font-medium">{location.name}</TableCell>
                    <TableCell>
                      <Badge variant={getTypeBadgeVariant(location.type)}>
                        {location.type === "THREEPEL" ? "3PL" : location.type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {location.channel ? (
                        <Badge variant={getChannelBadgeVariant(location.channel)}>
                          {location.channel}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>{formatAddress(location.address)}</TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(location.createdAt)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
