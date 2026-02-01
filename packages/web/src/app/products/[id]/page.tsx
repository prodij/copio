import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProductEditor } from "./product-editor";

const API_URL = process.env.API_URL || "http://localhost:8000/api/v1";

interface Product {
  id: string;
  sku: string;
  name: string;
  productType: string;
  status: string;
  parentId: string | null;
  variationType: string | null;
  variationValue: string | null;
  brand: string | null;
  manufacturer: string | null;
  modelNumber: string | null;
  upc: string | null;
  ean: string | null;
  gtin: string | null;
  asin: string | null;
  mpn: string | null;
  shortDescription: string | null;
  longDescription: string | null;
  bulletPoints: string[];
  searchTerms: string[];
  seoTitle: string | null;
  seoDescription: string | null;
  weightValue: number | null;
  weightUnit: string | null;
  lengthValue: number | null;
  widthValue: number | null;
  heightValue: number | null;
  dimensionUnit: string | null;
  pkgWeightValue: number | null;
  pkgWeightUnit: string | null;
  pkgLengthValue: number | null;
  pkgWidthValue: number | null;
  pkgHeightValue: number | null;
  pkgDimensionUnit: string | null;
  countryOfOrigin: string | null;
  hazmat: boolean;
  hazmatInfo: Record<string, unknown> | null;
  ageRestriction: number | null;
  certifications: string[];
  warrantyInfo: string | null;
  costPrice: number | null;
  msrp: number | null;
  createdAt: string;
  updatedAt: string;
  images: Array<{
    id: string;
    url: string;
    altText: string | null;
    position: number;
  }>;
  attributes: Array<{
    id: string;
    name: string;
    value: string;
    group: string | null;
  }>;
  listings: Array<{
    id: string;
    channel: string;
    channelSku: string;
    channelProductId: string | null;
    title: string | null;
    description: string | null;
    bulletPoints: string[];
    price: number | null;
    compareAtPrice: number | null;
    fulfillmentChannel: string;
    bufferStock: number;
    maxQuantity: number | null;
    handlingDays: number | null;
    status: string;
    listingUrl: string | null;
  }>;
  vendors: Array<{
    id: string;
    vendorSku: string;
    vendorProductName: string | null;
    unitCost: number;
    currency: string;
    minOrderQty: number;
    orderMultiple: number;
    casePackQty: number | null;
    leadTimeDays: number | null;
    isPreferred: boolean;
    isActive: boolean;
    notes: string | null;
    vendor: { id: string; name: string; code: string | null; leadTimeDays: number };
  }>;
  parent: { id: string; sku: string; name: string } | null;
  variations: Array<{
    id: string;
    sku: string;
    name: string;
    variationType: string | null;
    variationValue: string | null;
  }>;
}

async function getProduct(id: string): Promise<Product | null> {
  const res = await fetch(`${API_URL}/products/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch product");
  return res.json();
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    DRAFT: "bg-gray-100 text-gray-800",
    ACTIVE: "bg-green-100 text-green-800",
    ARCHIVED: "bg-orange-100 text-orange-800",
  };
  return (
    <Badge className={colors[status] || "bg-gray-100"} variant="outline">
      {status}
    </Badge>
  );
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    SIMPLE: "bg-blue-100 text-blue-800",
    PARENT: "bg-purple-100 text-purple-800",
    VARIATION: "bg-indigo-100 text-indigo-800",
  };
  return (
    <Badge className={colors[type] || "bg-gray-100"} variant="outline">
      {type}
    </Badge>
  );
}

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const product = await getProduct(id);

  if (!product) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/products">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{product.name}</h1>
            <StatusBadge status={product.status} />
            <TypeBadge type={product.productType} />
          </div>
          <p className="text-muted-foreground">SKU: {product.sku}</p>
        </div>
      </div>

      <ProductEditor product={product} />
    </div>
  );
}
