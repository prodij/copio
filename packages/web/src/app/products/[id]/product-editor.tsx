"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Save, Loader2, Plus, X, ImageIcon, Star, Truck, Store } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { VendorProductDialog } from "@/components/vendor-product-dialog";
import { ChannelListingDialog } from "@/components/channel-listing-dialog";

interface VendorProduct {
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
}

interface ChannelListing {
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
}

interface Product {
  id: string;
  sku: string;
  name: string;
  productType: string;
  status: string;
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
  ageRestriction: number | null;
  certifications: string[];
  warrantyInfo: string | null;
  costPrice: number | null;
  msrp: number | null;
  images: Array<{ id: string; url: string; altText: string | null; position: number }>;
  attributes: Array<{ id: string; name: string; value: string; group: string | null }>;
  listings: ChannelListing[];
  vendors: VendorProduct[];
}

function ChannelBadge({ channel }: { channel: string }) {
  const colors: Record<string, string> = {
    AMAZON: "bg-orange-100 text-orange-800",
    SHOPIFY: "bg-green-100 text-green-800",
    WALMART: "bg-blue-100 text-blue-800",
    EBAY: "bg-yellow-100 text-yellow-800",
  };
  return <Badge className={`${colors[channel] || "bg-gray-100"}`}>{channel}</Badge>;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    DRAFT: "bg-gray-100 text-gray-800",
    PENDING: "bg-yellow-100 text-yellow-800",
    ACTIVE: "bg-green-100 text-green-800",
    INACTIVE: "bg-gray-100 text-gray-600",
    SUPPRESSED: "bg-red-100 text-red-800",
    ERROR: "bg-red-100 text-red-800",
  };
  return <Badge className={colors[status] || "bg-gray-100"} variant="outline">{status}</Badge>;
}

function FulfillmentBadge({ channel }: { channel: string }) {
  const labels: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    MERCHANT: { label: "Merchant", color: "bg-blue-100 text-blue-800", icon: <Store className="h-3 w-3" /> },
    MARKETPLACE: { label: "FBA/WFS", color: "bg-purple-100 text-purple-800", icon: <Truck className="h-3 w-3" /> },
    DROPSHIP: { label: "Dropship", color: "bg-orange-100 text-orange-800", icon: <Truck className="h-3 w-3" /> },
    THREEPEL: { label: "3PL", color: "bg-teal-100 text-teal-800", icon: <Truck className="h-3 w-3" /> },
  };
  const { label, color, icon } = labels[channel] || { label: channel, color: "bg-gray-100", icon: null };
  return (
    <Badge className={`${color} flex items-center gap-1`} variant="outline">
      {icon} {label}
    </Badge>
  );
}

export function ProductEditor({ product }: { product: Product }) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: product.name,
    status: product.status,
    brand: product.brand || "",
    manufacturer: product.manufacturer || "",
    modelNumber: product.modelNumber || "",
    upc: product.upc || "",
    ean: product.ean || "",
    gtin: product.gtin || "",
    asin: product.asin || "",
    mpn: product.mpn || "",
    shortDescription: product.shortDescription || "",
    longDescription: product.longDescription || "",
    bulletPoints: product.bulletPoints || [],
    searchTerms: product.searchTerms || [],
    seoTitle: product.seoTitle || "",
    seoDescription: product.seoDescription || "",
    weightValue: product.weightValue?.toString() || "",
    weightUnit: product.weightUnit || "lb",
    lengthValue: product.lengthValue?.toString() || "",
    widthValue: product.widthValue?.toString() || "",
    heightValue: product.heightValue?.toString() || "",
    dimensionUnit: product.dimensionUnit || "in",
    pkgWeightValue: product.pkgWeightValue?.toString() || "",
    pkgWeightUnit: product.pkgWeightUnit || "lb",
    pkgLengthValue: product.pkgLengthValue?.toString() || "",
    pkgWidthValue: product.pkgWidthValue?.toString() || "",
    pkgHeightValue: product.pkgHeightValue?.toString() || "",
    pkgDimensionUnit: product.pkgDimensionUnit || "in",
    countryOfOrigin: product.countryOfOrigin || "",
    hazmat: product.hazmat,
    ageRestriction: product.ageRestriction?.toString() || "",
    certifications: product.certifications || [],
    warrantyInfo: product.warrantyInfo || "",
    costPrice: product.costPrice?.toString() || "",
    msrp: product.msrp?.toString() || "",
  });

  const [newBullet, setNewBullet] = useState("");
  const [newSearchTerm, setNewSearchTerm] = useState("");
  const [newCert, setNewCert] = useState("");

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        ...formData,
        weightValue: formData.weightValue ? parseFloat(formData.weightValue) : undefined,
        lengthValue: formData.lengthValue ? parseFloat(formData.lengthValue) : undefined,
        widthValue: formData.widthValue ? parseFloat(formData.widthValue) : undefined,
        heightValue: formData.heightValue ? parseFloat(formData.heightValue) : undefined,
        pkgWeightValue: formData.pkgWeightValue ? parseFloat(formData.pkgWeightValue) : undefined,
        pkgLengthValue: formData.pkgLengthValue ? parseFloat(formData.pkgLengthValue) : undefined,
        pkgWidthValue: formData.pkgWidthValue ? parseFloat(formData.pkgWidthValue) : undefined,
        pkgHeightValue: formData.pkgHeightValue ? parseFloat(formData.pkgHeightValue) : undefined,
        ageRestriction: formData.ageRestriction ? parseInt(formData.ageRestriction) : undefined,
        costPrice: formData.costPrice ? parseFloat(formData.costPrice) : undefined,
        msrp: formData.msrp ? parseFloat(formData.msrp) : undefined,
      };

      const res = await fetch(`/api/products/${product.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("Failed to save");
      router.refresh();
    } catch (error) {
      console.error("Save failed:", error);
    } finally {
      setSaving(false);
    }
  };

  const addBullet = () => {
    if (newBullet.trim()) {
      setFormData({ ...formData, bulletPoints: [...formData.bulletPoints, newBullet.trim()] });
      setNewBullet("");
    }
  };

  const removeBullet = (index: number) => {
    setFormData({
      ...formData,
      bulletPoints: formData.bulletPoints.filter((_, i) => i !== index),
    });
  };

  const addSearchTerm = () => {
    if (newSearchTerm.trim()) {
      setFormData({ ...formData, searchTerms: [...formData.searchTerms, newSearchTerm.trim()] });
      setNewSearchTerm("");
    }
  };

  const removeSearchTerm = (index: number) => {
    setFormData({
      ...formData,
      searchTerms: formData.searchTerms.filter((_, i) => i !== index),
    });
  };

  const addCert = () => {
    if (newCert.trim()) {
      setFormData({ ...formData, certifications: [...formData.certifications, newCert.trim()] });
      setNewCert("");
    }
  };

  const removeCert = (index: number) => {
    setFormData({
      ...formData,
      certifications: formData.certifications.filter((_, i) => i !== index),
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Save Changes
        </Button>
      </div>

      <Tabs defaultValue="basic" className="w-full">
        <TabsList className="grid w-full grid-cols-8">
          <TabsTrigger value="basic">Basic</TabsTrigger>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="physical">Physical</TabsTrigger>
          <TabsTrigger value="identifiers">IDs</TabsTrigger>
          <TabsTrigger value="compliance">Compliance</TabsTrigger>
          <TabsTrigger value="vendors">Vendors</TabsTrigger>
          <TabsTrigger value="channels">Channels</TabsTrigger>
          <TabsTrigger value="media">Media</TabsTrigger>
        </TabsList>

        {/* Basic Info Tab */}
        <TabsContent value="basic">
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Core product identity and pricing</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Product Name</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="status">Status</Label>
                  <Select
                    value={formData.status}
                    onValueChange={(value) => setFormData({ ...formData, status: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="DRAFT">Draft</SelectItem>
                      <SelectItem value="ACTIVE">Active</SelectItem>
                      <SelectItem value="ARCHIVED">Archived</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="brand">Brand</Label>
                  <Input
                    id="brand"
                    value={formData.brand}
                    onChange={(e) => setFormData({ ...formData, brand: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="manufacturer">Manufacturer</Label>
                  <Input
                    id="manufacturer"
                    value={formData.manufacturer}
                    onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="modelNumber">Model Number</Label>
                  <Input
                    id="modelNumber"
                    value={formData.modelNumber}
                    onChange={(e) => setFormData({ ...formData, modelNumber: e.target.value })}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="costPrice">Cost Price ($)</Label>
                  <Input
                    id="costPrice"
                    type="number"
                    step="0.01"
                    value={formData.costPrice}
                    onChange={(e) => setFormData({ ...formData, costPrice: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="msrp">MSRP ($)</Label>
                  <Input
                    id="msrp"
                    type="number"
                    step="0.01"
                    value={formData.msrp}
                    onChange={(e) => setFormData({ ...formData, msrp: e.target.value })}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Content Tab */}
        <TabsContent value="content">
          <Card>
            <CardHeader>
              <CardTitle>Listing Content</CardTitle>
              <CardDescription>Descriptions, bullet points, and SEO for AI-generated listings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="shortDescription">Short Description</Label>
                <Textarea
                  id="shortDescription"
                  value={formData.shortDescription}
                  onChange={(e) => setFormData({ ...formData, shortDescription: e.target.value })}
                  placeholder="Brief product summary (1-2 sentences)"
                  rows={2}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="longDescription">Long Description</Label>
                <Textarea
                  id="longDescription"
                  value={formData.longDescription}
                  onChange={(e) => setFormData({ ...formData, longDescription: e.target.value })}
                  placeholder="Detailed product description (supports HTML)"
                  rows={6}
                />
              </div>

              <div className="space-y-2">
                <Label>Bullet Points / Key Features</Label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.bulletPoints.map((bullet, index) => (
                    <Badge key={index} variant="secondary" className="text-sm py-1 px-2">
                      {bullet}
                      <button onClick={() => removeBullet(index)} className="ml-2 hover:text-destructive">
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Input
                    value={newBullet}
                    onChange={(e) => setNewBullet(e.target.value)}
                    placeholder="Add a bullet point"
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addBullet())}
                  />
                  <Button type="button" variant="outline" onClick={addBullet}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Search Terms / Keywords</Label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.searchTerms.map((term, index) => (
                    <Badge key={index} variant="outline" className="text-sm">
                      {term}
                      <button onClick={() => removeSearchTerm(index)} className="ml-2 hover:text-destructive">
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Input
                    value={newSearchTerm}
                    onChange={(e) => setNewSearchTerm(e.target.value)}
                    placeholder="Add search term"
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addSearchTerm())}
                  />
                  <Button type="button" variant="outline" onClick={addSearchTerm}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="seoTitle">SEO Title</Label>
                  <Input
                    id="seoTitle"
                    value={formData.seoTitle}
                    onChange={(e) => setFormData({ ...formData, seoTitle: e.target.value })}
                    placeholder="Page title for search engines"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="seoDescription">SEO Description</Label>
                  <Textarea
                    id="seoDescription"
                    value={formData.seoDescription}
                    onChange={(e) => setFormData({ ...formData, seoDescription: e.target.value })}
                    placeholder="Meta description (150-160 chars)"
                    rows={2}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Physical Tab */}
        <TabsContent value="physical">
          <Card>
            <CardHeader>
              <CardTitle>Physical Attributes</CardTitle>
              <CardDescription>Product and package dimensions for shipping</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h3 className="font-medium mb-3">Product Dimensions</h3>
                <div className="grid grid-cols-5 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="weightValue">Weight</Label>
                    <Input
                      id="weightValue"
                      type="number"
                      step="0.001"
                      value={formData.weightValue}
                      onChange={(e) => setFormData({ ...formData, weightValue: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="weightUnit">Unit</Label>
                    <Select
                      value={formData.weightUnit}
                      onValueChange={(value) => setFormData({ ...formData, weightUnit: value })}
                    >
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="lb">lb</SelectItem>
                        <SelectItem value="oz">oz</SelectItem>
                        <SelectItem value="kg">kg</SelectItem>
                        <SelectItem value="g">g</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="lengthValue">Length</Label>
                    <Input id="lengthValue" type="number" step="0.01" value={formData.lengthValue}
                      onChange={(e) => setFormData({ ...formData, lengthValue: e.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="widthValue">Width</Label>
                    <Input id="widthValue" type="number" step="0.01" value={formData.widthValue}
                      onChange={(e) => setFormData({ ...formData, widthValue: e.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="heightValue">Height</Label>
                    <Input id="heightValue" type="number" step="0.01" value={formData.heightValue}
                      onChange={(e) => setFormData({ ...formData, heightValue: e.target.value })} />
                  </div>
                </div>
              </div>

              <div>
                <h3 className="font-medium mb-3">Package Dimensions</h3>
                <div className="grid grid-cols-5 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="pkgWeightValue">Weight</Label>
                    <Input id="pkgWeightValue" type="number" step="0.001" value={formData.pkgWeightValue}
                      onChange={(e) => setFormData({ ...formData, pkgWeightValue: e.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="pkgWeightUnit">Unit</Label>
                    <Select value={formData.pkgWeightUnit}
                      onValueChange={(value) => setFormData({ ...formData, pkgWeightUnit: value })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="lb">lb</SelectItem>
                        <SelectItem value="oz">oz</SelectItem>
                        <SelectItem value="kg">kg</SelectItem>
                        <SelectItem value="g">g</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="pkgLengthValue">Length</Label>
                    <Input id="pkgLengthValue" type="number" step="0.01" value={formData.pkgLengthValue}
                      onChange={(e) => setFormData({ ...formData, pkgLengthValue: e.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="pkgWidthValue">Width</Label>
                    <Input id="pkgWidthValue" type="number" step="0.01" value={formData.pkgWidthValue}
                      onChange={(e) => setFormData({ ...formData, pkgWidthValue: e.target.value })} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="pkgHeightValue">Height</Label>
                    <Input id="pkgHeightValue" type="number" step="0.01" value={formData.pkgHeightValue}
                      onChange={(e) => setFormData({ ...formData, pkgHeightValue: e.target.value })} />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Identifiers Tab */}
        <TabsContent value="identifiers">
          <Card>
            <CardHeader>
              <CardTitle>Product Identifiers</CardTitle>
              <CardDescription>Barcodes and marketplace identifiers</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="upc">UPC</Label>
                  <Input id="upc" value={formData.upc}
                    onChange={(e) => setFormData({ ...formData, upc: e.target.value })}
                    placeholder="Universal Product Code" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ean">EAN</Label>
                  <Input id="ean" value={formData.ean}
                    onChange={(e) => setFormData({ ...formData, ean: e.target.value })}
                    placeholder="European Article Number" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="gtin">GTIN</Label>
                  <Input id="gtin" value={formData.gtin}
                    onChange={(e) => setFormData({ ...formData, gtin: e.target.value })}
                    placeholder="Global Trade Item Number" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="asin">ASIN</Label>
                  <Input id="asin" value={formData.asin}
                    onChange={(e) => setFormData({ ...formData, asin: e.target.value })}
                    placeholder="Amazon Standard Identification Number" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="mpn">MPN</Label>
                  <Input id="mpn" value={formData.mpn}
                    onChange={(e) => setFormData({ ...formData, mpn: e.target.value })}
                    placeholder="Manufacturer Part Number" />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Compliance Tab */}
        <TabsContent value="compliance">
          <Card>
            <CardHeader>
              <CardTitle>Compliance & Safety</CardTitle>
              <CardDescription>Regulatory and shipping compliance information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="countryOfOrigin">Country of Origin</Label>
                  <Input id="countryOfOrigin" value={formData.countryOfOrigin}
                    onChange={(e) => setFormData({ ...formData, countryOfOrigin: e.target.value })}
                    placeholder="e.g., China, USA, Germany" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="ageRestriction">Age Restriction</Label>
                  <Input id="ageRestriction" type="number" value={formData.ageRestriction}
                    onChange={(e) => setFormData({ ...formData, ageRestriction: e.target.value })}
                    placeholder="Minimum age (leave empty if none)" />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Certifications</Label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.certifications.map((cert, index) => (
                    <Badge key={index} variant="secondary">
                      {cert}
                      <button onClick={() => removeCert(index)} className="ml-2 hover:text-destructive">
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Input value={newCert} onChange={(e) => setNewCert(e.target.value)}
                    placeholder="Add certification (e.g., FDA, CE, FCC)"
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCert())} />
                  <Button type="button" variant="outline" onClick={addCert}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="warrantyInfo">Warranty Information</Label>
                <Textarea id="warrantyInfo" value={formData.warrantyInfo}
                  onChange={(e) => setFormData({ ...formData, warrantyInfo: e.target.value })}
                  placeholder="Warranty terms and duration" rows={3} />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Vendors Tab */}
        <TabsContent value="vendors">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Vendor Sourcing</CardTitle>
                <CardDescription>Where you buy this product (procurement side)</CardDescription>
              </div>
              <VendorProductDialog productId={product.id} />
            </CardHeader>
            <CardContent>
              {product.vendors && product.vendors.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Vendor</TableHead>
                      <TableHead>Vendor SKU</TableHead>
                      <TableHead className="text-right">Unit Cost</TableHead>
                      <TableHead className="text-center">MOQ</TableHead>
                      <TableHead className="text-center">Case Pack</TableHead>
                      <TableHead className="text-center">Lead Time</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {product.vendors.map((vp) => (
                      <TableRow key={vp.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {vp.isPreferred && <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />}
                            <div>
                              <div className="font-medium">{vp.vendor.name}</div>
                              {vp.vendor.code && (
                                <div className="text-xs text-muted-foreground">{vp.vendor.code}</div>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-sm">{vp.vendorSku}</TableCell>
                        <TableCell className="text-right font-medium">
                          ${Number(vp.unitCost).toFixed(2)}
                        </TableCell>
                        <TableCell className="text-center">{vp.minOrderQty}</TableCell>
                        <TableCell className="text-center">
                          {vp.casePackQty ? `${vp.casePackQty} units` : "—"}
                        </TableCell>
                        <TableCell className="text-center">
                          {vp.leadTimeDays || vp.vendor.leadTimeDays} days
                        </TableCell>
                        <TableCell>
                          <VendorProductDialog
                            existingData={vp}
                            trigger={<Button variant="ghost" size="sm">Edit</Button>}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No vendors linked to this product yet.</p>
                  <p className="text-sm">Add a vendor to track sourcing costs and lead times.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Channels Tab */}
        <TabsContent value="channels">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Channel Listings</CardTitle>
                <CardDescription>Where you sell this product (marketplace side)</CardDescription>
              </div>
              <ChannelListingDialog productId={product.id} />
            </CardHeader>
            <CardContent>
              {product.listings && product.listings.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Channel</TableHead>
                      <TableHead>Channel SKU</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead className="text-right">Price</TableHead>
                      <TableHead>Fulfillment</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {product.listings.map((listing) => (
                      <TableRow key={listing.id}>
                        <TableCell>
                          <ChannelBadge channel={listing.channel} />
                        </TableCell>
                        <TableCell className="font-mono text-sm">{listing.channelSku}</TableCell>
                        <TableCell className="max-w-[200px] truncate">
                          {listing.title || <span className="text-muted-foreground italic">Using default</span>}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {listing.price ? `$${Number(listing.price).toFixed(2)}` : "—"}
                        </TableCell>
                        <TableCell>
                          <FulfillmentBadge channel={listing.fulfillmentChannel} />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={listing.status} />
                        </TableCell>
                        <TableCell>
                          <ChannelListingDialog
                            existingData={listing}
                            trigger={<Button variant="ghost" size="sm">Edit</Button>}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No channel listings yet.</p>
                  <p className="text-sm">Add a channel to start selling on marketplaces.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Media Tab */}
        <TabsContent value="media">
          <Card>
            <CardHeader>
              <CardTitle>Product Images</CardTitle>
              <CardDescription>Manage product photos and media</CardDescription>
            </CardHeader>
            <CardContent>
              {product.images.length > 0 ? (
                <div className="grid grid-cols-4 gap-4">
                  {product.images.map((image) => (
                    <div key={image.id} className="relative aspect-square rounded-lg border overflow-hidden">
                      <img src={image.url} alt={image.altText || ""} className="object-cover w-full h-full" />
                      {image.position === 0 && <Badge className="absolute top-2 left-2">Main</Badge>}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <ImageIcon className="h-12 w-12 mb-4" />
                  <p>No images yet</p>
                  <p className="text-sm">Add images via API or image upload (coming soon)</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="mt-4">
            <CardHeader>
              <CardTitle>Product Attributes</CardTitle>
              <CardDescription>Custom attributes (Material, Color, Size, etc.)</CardDescription>
            </CardHeader>
            <CardContent>
              {product.attributes.length > 0 ? (
                <div className="grid grid-cols-3 gap-4">
                  {product.attributes.map((attr) => (
                    <div key={attr.id} className="flex justify-between border rounded-lg p-3">
                      <span className="text-muted-foreground">{attr.name}</span>
                      <span className="font-medium">{attr.value}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-6">No attributes defined</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
