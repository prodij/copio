"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  useLocations,
  useCreateLocation,
  type Location,
} from "@/hooks/use-locations";
import { Plus, Loader2, AlertCircle, MapPin } from "lucide-react";

const LOCATION_TYPES = ["WAREHOUSE", "FBA", "THREEPEL"] as const;
const CHANNELS = ["SHOPIFY", "AMAZON", "FAIRE", "INTERNAL"] as const;

type LocationType = (typeof LOCATION_TYPES)[number];
type Channel = (typeof CHANNELS)[number];

function getTypeBadgeVariant(
  type: string
): "warehouse" | "fba" | "threepel" | "secondary" {
  const typeMap: Record<string, "warehouse" | "fba" | "threepel"> = {
    WAREHOUSE: "warehouse",
    FBA: "fba",
    THREEPEL: "threepel",
  };
  return typeMap[type] || "secondary";
}

function getChannelBadgeVariant(
  channel: string
): "shopify" | "amazon" | "faire" | "internal" | "outline" {
  const channelMap: Record<string, "shopify" | "amazon" | "faire" | "internal"> = {
    SHOPIFY: "shopify",
    AMAZON: "amazon",
    FAIRE: "faire",
    INTERNAL: "internal",
  };
  return channelMap[channel] || "outline";
}

function formatDate(date: Date | string) {
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

function CreateLocationDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<LocationType>("WAREHOUSE");
  const [channel, setChannel] = useState<Channel | "">("");
  const [address, setAddress] = useState("");

  const createLocation = useCreateLocation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    await createLocation.mutateAsync({
      name: name.trim(),
      type,
      channel: channel || undefined,
      address: address ? { street: address } : undefined,
    });

    setName("");
    setType("WAREHOUSE");
    setChannel("");
    setAddress("");
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Location
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Location</DialogTitle>
            <DialogDescription>
              Add a new warehouse or storage location for your inventory.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="Main Warehouse"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="type">Type</Label>
              <Select
                value={type}
                onValueChange={(v) => setType(v as LocationType)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a type" />
                </SelectTrigger>
                <SelectContent>
                  {LOCATION_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t === "THREEPEL" ? "3PL" : t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="channel">Channel (optional)</Label>
              <Select
                value={channel}
                onValueChange={(v) => setChannel(v as Channel)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a channel" />
                </SelectTrigger>
                <SelectContent>
                  {CHANNELS.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="address">Address (optional)</Label>
              <Input
                id="address"
                placeholder="123 Main St, City, State"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createLocation.isPending}>
              {createLocation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create Location
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function LocationsTable({ locations }: { locations: Location[] }) {
  if (locations.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={5} className="h-24 text-center">
          <div className="flex flex-col items-center gap-2 text-muted-foreground">
            <MapPin className="h-8 w-8" />
            <p>No locations yet. Add your first warehouse or storage location.</p>
          </div>
        </TableCell>
      </TableRow>
    );
  }

  return (
    <>
      {locations.map((location) => (
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
          <TableCell className="text-muted-foreground">
            {formatDate(location.createdAt)}
          </TableCell>
        </TableRow>
      ))}
    </>
  );
}

export default function LocationsPage() {
  const { data: locations, isLoading, error } = useLocations();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Locations</h1>
          <p className="text-muted-foreground">
            Manage your warehouses and storage locations.
          </p>
        </div>
        <CreateLocationDialog />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Storage Locations</CardTitle>
          <CardDescription>
            Warehouses and facilities where inventory is stored.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center gap-2 py-8 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <span>Failed to load locations. Please try again.</span>
            </div>
          ) : (
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
                <LocationsTable locations={locations || []} />
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
