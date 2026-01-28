"use client";

import { useState, useMemo } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useStockItems,
  useCreateStockItem,
  type StockItem,
} from "@/hooks/use-stock-items";
import { useProducts } from "@/hooks/use-products";
import { useLocations } from "@/hooks/use-locations";
import { ArrowUpDown, AlertTriangle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

// Low stock threshold
const LOW_STOCK_THRESHOLD = 10;

type SortField =
  | "productName"
  | "sku"
  | "locationName"
  | "quantityAvailable"
  | "quantityReserved"
  | "quantityInbound"
  | "totalValue";
type SortDirection = "asc" | "desc";

export default function InventoryPage() {
  const { data: stockItems, isLoading, error } = useStockItems();
  const { data: products } = useProducts();
  const { data: locations } = useLocations();
  const createStockItem = useCreateStockItem();

  // Filter state
  const [locationFilter, setLocationFilter] = useState<string>("all");
  const [productFilter, setProductFilter] = useState<string>("all");

  // Sort state
  const [sortField, setSortField] = useState<SortField>("productName");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newStockItem, setNewStockItem] = useState({
    productId: "",
    locationId: "",
    quantityAvailable: 0,
    costBasis: 0,
  });

  // Helper to calculate total value
  const calculateTotalValue = (item: StockItem): number => {
    if (!item.costBasis) return 0;
    return item.quantityAvailable * parseFloat(item.costBasis);
  };

  // Filter and sort items
  const filteredAndSortedItems = useMemo(() => {
    if (!stockItems) return [];

    let filtered = stockItems;

    // Apply filters
    if (locationFilter !== "all") {
      filtered = filtered.filter((item) => item.locationId === locationFilter);
    }
    if (productFilter !== "all") {
      filtered = filtered.filter((item) => item.productId === productFilter);
    }

    // Apply sorting
    return [...filtered].sort((a, b) => {
      let aValue: string | number;
      let bValue: string | number;

      switch (sortField) {
        case "productName":
          aValue = a.product.name.toLowerCase();
          bValue = b.product.name.toLowerCase();
          break;
        case "sku":
          aValue = a.product.sku.toLowerCase();
          bValue = b.product.sku.toLowerCase();
          break;
        case "locationName":
          aValue = a.location.name.toLowerCase();
          bValue = b.location.name.toLowerCase();
          break;
        case "quantityAvailable":
          aValue = a.quantityAvailable;
          bValue = b.quantityAvailable;
          break;
        case "quantityReserved":
          aValue = a.quantityReserved;
          bValue = b.quantityReserved;
          break;
        case "quantityInbound":
          aValue = a.quantityInbound;
          bValue = b.quantityInbound;
          break;
        case "totalValue":
          aValue = calculateTotalValue(a);
          bValue = calculateTotalValue(b);
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortDirection === "asc" ? -1 : 1;
      if (aValue > bValue) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }, [stockItems, locationFilter, productFilter, sortField, sortDirection]);

  // Toggle sort
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  // Handle create stock item
  const handleCreateStockItem = async () => {
    try {
      await createStockItem.mutateAsync({
        productId: newStockItem.productId,
        locationId: newStockItem.locationId,
        quantityAvailable: newStockItem.quantityAvailable,
        costBasis: newStockItem.costBasis || undefined,
      });
      setDialogOpen(false);
      setNewStockItem({
        productId: "",
        locationId: "",
        quantityAvailable: 0,
        costBasis: 0,
      });
    } catch {
      // Error is handled by the mutation
    }
  };

  // Format currency
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(value);
  };

  // Sortable header component
  const SortableHeader = ({
    field,
    children,
    className,
  }: {
    field: SortField;
    children: React.ReactNode;
    className?: string;
  }) => (
    <TableHead
      className={cn("cursor-pointer select-none hover:bg-muted/50", className)}
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center gap-1">
        {children}
        <ArrowUpDown
          className={cn(
            "h-4 w-4",
            sortField === field ? "opacity-100" : "opacity-30"
          )}
        />
      </div>
    </TableHead>
  );

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Inventory</h1>
          <p className="text-muted-foreground">
            Manage stock levels across all locations.
          </p>
        </div>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              <p>Failed to load inventory data. Please try again later.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Inventory</h1>
          <p className="text-muted-foreground">
            Manage stock levels across all locations.
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button>Add Stock</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Stock Item</DialogTitle>
              <DialogDescription>
                Create a new stock item to track inventory for a product at a
                specific location.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="product">Product</Label>
                <Select
                  value={newStockItem.productId}
                  onValueChange={(value) =>
                    setNewStockItem({ ...newStockItem, productId: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a product" />
                  </SelectTrigger>
                  <SelectContent>
                    {products?.map((product) => (
                      <SelectItem key={product.id} value={product.id}>
                        {product.name} ({product.sku})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="location">Location</Label>
                <Select
                  value={newStockItem.locationId}
                  onValueChange={(value) =>
                    setNewStockItem({ ...newStockItem, locationId: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a location" />
                  </SelectTrigger>
                  <SelectContent>
                    {locations?.map((location) => (
                      <SelectItem key={location.id} value={location.id}>
                        {location.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="quantity">Initial Quantity</Label>
                <Input
                  id="quantity"
                  type="number"
                  min="0"
                  value={newStockItem.quantityAvailable}
                  onChange={(e) =>
                    setNewStockItem({
                      ...newStockItem,
                      quantityAvailable: parseInt(e.target.value) || 0,
                    })
                  }
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="costBasis">Cost Per Unit ($)</Label>
                <Input
                  id="costBasis"
                  type="number"
                  min="0"
                  step="0.01"
                  value={newStockItem.costBasis || ""}
                  onChange={(e) =>
                    setNewStockItem({
                      ...newStockItem,
                      costBasis: parseFloat(e.target.value) || 0,
                    })
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateStockItem}
                disabled={
                  !newStockItem.productId ||
                  !newStockItem.locationId ||
                  createStockItem.isPending
                }
              >
                {createStockItem.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Create
              </Button>
            </DialogFooter>
            {createStockItem.isError && (
              <p className="text-sm text-destructive mt-2">
                {createStockItem.error?.message || "Failed to create stock item"}
              </p>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="w-[200px]">
          <Select value={locationFilter} onValueChange={setLocationFilter}>
            <SelectTrigger>
              <SelectValue placeholder="Filter by location" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Locations</SelectItem>
              {locations?.map((location) => (
                <SelectItem key={location.id} value={location.id}>
                  {location.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-[200px]">
          <Select value={productFilter} onValueChange={setProductFilter}>
            <SelectTrigger>
              <SelectValue placeholder="Filter by product" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Products</SelectItem>
              {products?.map((product) => (
                <SelectItem key={product.id} value={product.id}>
                  {product.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Stock Levels</CardTitle>
          <CardDescription>
            Current inventory quantities by product and location. Click column
            headers to sort.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableHeader field="productName">Product</SortableHeader>
                  <SortableHeader field="sku">SKU</SortableHeader>
                  <SortableHeader field="locationName">Location</SortableHeader>
                  <SortableHeader field="quantityAvailable" className="text-right">
                    Available
                  </SortableHeader>
                  <SortableHeader field="quantityReserved" className="text-right">
                    Reserved
                  </SortableHeader>
                  <SortableHeader field="quantityInbound" className="text-right">
                    Inbound
                  </SortableHeader>
                  <SortableHeader field="totalValue" className="text-right">
                    Total Value
                  </SortableHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAndSortedItems.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={7}
                      className="text-center text-muted-foreground"
                    >
                      No inventory data yet. Add products and locations first.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredAndSortedItems.map((item) => {
                    const isLowStock =
                      item.quantityAvailable < LOW_STOCK_THRESHOLD;
                    return (
                      <TableRow
                        key={item.id}
                        className={cn(isLowStock && "bg-red-50 dark:bg-red-950/20")}
                      >
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {item.product.name}
                            {isLowStock && (
                              <AlertTriangle className="h-4 w-4 text-red-500" />
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {item.product.sku}
                        </TableCell>
                        <TableCell>{item.location.name}</TableCell>
                        <TableCell
                          className={cn(
                            "text-right",
                            isLowStock && "text-red-600 font-semibold"
                          )}
                        >
                          {item.quantityAvailable}
                        </TableCell>
                        <TableCell className="text-right">
                          {item.quantityReserved}
                        </TableCell>
                        <TableCell className="text-right">
                          {item.quantityInbound}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatCurrency(calculateTotalValue(item))}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
