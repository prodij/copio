"use client";

import { useState, useMemo } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowUpDown, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

const LOW_STOCK_THRESHOLD = 10;

interface Product {
  id: string;
  sku: string;
  name: string;
}

interface Location {
  id: string;
  name: string;
}

interface StockItem {
  id: string;
  productId: string;
  locationId: string;
  quantityAvailable: number;
  quantityReserved: number;
  quantityInbound: number;
  costBasis: string | null;
  product: Product;
  location: Location;
}

type SortField = "productName" | "sku" | "locationName" | "quantityAvailable" | "quantityReserved" | "quantityInbound" | "totalValue";
type SortDirection = "asc" | "desc";

interface Props {
  stockItems: StockItem[];
  products: Product[];
  locations: Location[];
}

export function InventoryTable({ stockItems, products, locations }: Props) {
  const [locationFilter, setLocationFilter] = useState<string>("all");
  const [productFilter, setProductFilter] = useState<string>("all");
  const [sortField, setSortField] = useState<SortField>("productName");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const calculateTotalValue = (item: StockItem): number => {
    if (!item.costBasis) return 0;
    return item.quantityAvailable * parseFloat(item.costBasis);
  };

  const filteredAndSortedItems = useMemo(() => {
    let filtered = stockItems;

    if (locationFilter !== "all") {
      filtered = filtered.filter((item) => item.locationId === locationFilter);
    }
    if (productFilter !== "all") {
      filtered = filtered.filter((item) => item.productId === productFilter);
    }

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

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
  };

  const SortableHeader = ({ field, children, className }: { field: SortField; children: React.ReactNode; className?: string }) => (
    <TableHead
      className={cn("cursor-pointer select-none hover:bg-muted/50", className)}
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center gap-1">
        {children}
        <ArrowUpDown className={cn("h-4 w-4", sortField === field ? "opacity-100" : "opacity-30")} />
      </div>
    </TableHead>
  );

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-4">
        <div className="w-[200px]">
          <Select value={locationFilter} onValueChange={setLocationFilter}>
            <SelectTrigger>
              <SelectValue placeholder="Filter by location" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Locations</SelectItem>
              {locations.map((location) => (
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
              {products.map((product) => (
                <SelectItem key={product.id} value={product.id}>
                  {product.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <SortableHeader field="productName">Product</SortableHeader>
            <SortableHeader field="sku">SKU</SortableHeader>
            <SortableHeader field="locationName">Location</SortableHeader>
            <SortableHeader field="quantityAvailable" className="text-right">Available</SortableHeader>
            <SortableHeader field="quantityReserved" className="text-right">Reserved</SortableHeader>
            <SortableHeader field="quantityInbound" className="text-right">Inbound</SortableHeader>
            <SortableHeader field="totalValue" className="text-right">Total Value</SortableHeader>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filteredAndSortedItems.length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-muted-foreground">
                No inventory data yet. Add products and locations first.
              </TableCell>
            </TableRow>
          ) : (
            filteredAndSortedItems.map((item) => {
              const isLowStock = item.quantityAvailable < LOW_STOCK_THRESHOLD;
              return (
                <TableRow key={item.id} className={cn(isLowStock && "bg-red-50 dark:bg-red-950/20")}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {item.product.name}
                      {isLowStock && <AlertTriangle className="h-4 w-4 text-red-500" />}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{item.product.sku}</TableCell>
                  <TableCell>{item.location.name}</TableCell>
                  <TableCell className={cn("text-right", isLowStock && "text-red-600 font-semibold")}>
                    {item.quantityAvailable}
                  </TableCell>
                  <TableCell className="text-right">{item.quantityReserved}</TableCell>
                  <TableCell className="text-right">{item.quantityInbound}</TableCell>
                  <TableCell className="text-right">{formatCurrency(calculateTotalValue(item))}</TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}
