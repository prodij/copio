import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Package, FileText, Users, MapPin, AlertTriangle, Building2, Download, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VendorProductDialog } from "@/components/vendor-product-dialog";
import { VendorContactDialog } from "@/components/vendor-contact-dialog";
import { VendorAddressDialog } from "@/components/vendor-address-dialog";
import { VendorDocumentUpload } from "@/components/vendor-document-upload";
import { DocumentDownloadButton } from "@/components/document-download-button";

const API_URL = process.env.API_URL || "http://localhost:3002";

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
  product: { id: string; sku: string; name: string };
}

interface VendorContact {
  id: string;
  name: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  role: string;
  isPrimary: boolean;
  notes: string | null;
}

interface VendorAddress {
  id: string;
  type: string;
  label: string | null;
  isPrimary: boolean;
  street1: string;
  street2: string | null;
  city: string;
  state: string | null;
  postalCode: string | null;
  country: string;
  contactName: string | null;
  contactPhone: string | null;
  contactEmail: string | null;
  shippingNotes: string | null;
}

interface VendorDocument {
  id: string;
  type: string;
  name: string;
  description: string | null;
  mimeType: string;
  sizeBytes: number;
  expiresAt: string | null;
  uploadedAt: string;
}

interface Vendor {
  id: string;
  name: string;
  legalName: string | null;
  code: string | null;
  taxId: string | null;
  website: string | null;
  tier: string;
  category: string | null;
  contact: Record<string, unknown>;
  address: Record<string, unknown>;
  leadTimeDays: number;
  minOrderValue: number | null;
  paymentTerms: string | null;
  creditLimit: number | null;
  currency: string | null;
  accountManagerName: string | null;
  accountManagerEmail: string | null;
  notes: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  products: VendorProduct[];
  contacts: VendorContact[];
  addresses: VendorAddress[];
  documents: VendorDocument[];
  _count: { purchaseOrders: number };
}

async function getVendor(id: string): Promise<Vendor | null> {
  const res = await fetch(`${API_URL}/vendors/${id}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch vendor");
  return res.json();
}

const TIER_COLORS: Record<string, string> = {
  STRATEGIC: "bg-purple-100 text-purple-800",
  PREFERRED: "bg-blue-100 text-blue-800",
  STANDARD: "bg-gray-100 text-gray-800",
  PROBATIONARY: "bg-yellow-100 text-yellow-800",
  INACTIVE: "bg-red-100 text-red-800",
};

const ADDRESS_TYPE_LABELS: Record<string, string> = {
  CORPORATE: "Corporate HQ",
  WAREHOUSE: "Warehouse",
  MANUFACTURING: "Manufacturing",
  RETURNS: "Returns",
  BILLING: "Billing",
};

const CONTACT_ROLE_LABELS: Record<string, string> = {
  GENERAL: "General",
  SALES: "Sales",
  ACCOUNT: "Account Manager",
  SUPPORT: "Support",
  BILLING: "Billing",
  SHIPPING: "Shipping",
  EXECUTIVE: "Executive",
};

const DOC_TYPE_LABELS: Record<string, string> = {
  W9: "W-9",
  COI: "Certificate of Insurance",
  CONTRACT: "Contract",
  PRICE_LIST: "Price List",
  PRODUCT_CATALOG: "Product Catalog",
  SPEC_SHEET: "Spec Sheet",
  QUALITY_CERT: "Quality Certificate",
  COMPLIANCE: "Compliance",
  OTHER: "Other",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isExpiringSoon(dateStr: string | null): boolean {
  if (!dateStr) return false;
  const date = new Date(dateStr);
  const thirtyDaysFromNow = new Date();
  thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30);
  return date <= thirtyDaysFromNow && date >= new Date();
}

function isExpired(dateStr: string | null): boolean {
  if (!dateStr) return false;
  return new Date(dateStr) < new Date();
}

export default async function VendorDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const vendor = await getVendor(id);

  if (!vendor) {
    notFound();
  }

  const expiringDocs = vendor.documents?.filter(d => isExpiringSoon(d.expiresAt)) || [];
  const expiredDocs = vendor.documents?.filter(d => isExpired(d.expiresAt)) || [];
  const hasDocAlerts = expiringDocs.length > 0 || expiredDocs.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/vendors">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">{vendor.name}</h1>
            <Badge variant="outline" className={TIER_COLORS[vendor.tier] || TIER_COLORS.STANDARD}>
              {vendor.tier}
            </Badge>
            <Badge
              variant="outline"
              className={vendor.isActive ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}
            >
              {vendor.isActive ? "Active" : "Inactive"}
            </Badge>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
            {vendor.code && <span>Code: {vendor.code}</span>}
            {vendor.legalName && vendor.legalName !== vendor.name && (
              <span>Legal: {vendor.legalName}</span>
            )}
            {vendor.website && (
              <a href={vendor.website} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 hover:text-foreground">
                <ExternalLink className="h-3 w-3" />
                Website
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Alert Banner */}
      {hasDocAlerts && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-yellow-800">Document Attention Required</p>
            <p className="text-sm text-yellow-700">
              {expiredDocs.length > 0 && `${expiredDocs.length} expired document(s). `}
              {expiringDocs.length > 0 && `${expiringDocs.length} document(s) expiring soon.`}
            </p>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Lead Time</CardDescription>
            <CardTitle className="text-2xl">{vendor.leadTimeDays} days</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Min Order</CardDescription>
            <CardTitle className="text-2xl">
              {vendor.minOrderValue ? `$${Number(vendor.minOrderValue).toLocaleString()}` : "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Products</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <Package className="h-5 w-5" />
              {vendor.products?.length || 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Purchase Orders</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {vendor._count?.purchaseOrders || 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Locations</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <MapPin className="h-5 w-5" />
              {vendor.addresses?.length || 0}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Tabbed Content */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="contacts" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Contacts ({vendor.contacts?.length || 0})
          </TabsTrigger>
          <TabsTrigger value="addresses" className="flex items-center gap-2">
            <MapPin className="h-4 w-4" />
            Addresses ({vendor.addresses?.length || 0})
          </TabsTrigger>
          <TabsTrigger value="documents" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Documents ({vendor.documents?.length || 0})
            {hasDocAlerts && <span className="h-2 w-2 bg-yellow-500 rounded-full" />}
          </TabsTrigger>
          <TabsTrigger value="products" className="flex items-center gap-2">
            <Package className="h-4 w-4" />
            Products ({vendor.products?.length || 0})
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Vendor Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Payment Terms</p>
                    <p className="font-medium">{vendor.paymentTerms || "Not specified"}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Currency</p>
                    <p className="font-medium">{vendor.currency || "USD"}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Credit Limit</p>
                    <p className="font-medium">
                      {vendor.creditLimit ? `$${Number(vendor.creditLimit).toLocaleString()}` : "Not set"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Tax ID</p>
                    <p className="font-medium">{vendor.taxId || "Not provided"}</p>
                  </div>
                </div>
                {vendor.category && (
                  <div>
                    <p className="text-sm text-muted-foreground">Category</p>
                    <p className="font-medium">{vendor.category}</p>
                  </div>
                )}
                {vendor.notes && (
                  <div>
                    <p className="text-sm text-muted-foreground">Notes</p>
                    <p className="text-sm whitespace-pre-wrap">{vendor.notes}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Account Management</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {vendor.accountManagerName || vendor.accountManagerEmail ? (
                  <div className="space-y-2">
                    <div>
                      <p className="text-sm text-muted-foreground">Internal Owner</p>
                      <p className="font-medium">{vendor.accountManagerName || "—"}</p>
                    </div>
                    {vendor.accountManagerEmail && (
                      <div>
                        <p className="text-sm text-muted-foreground">Email</p>
                        <a href={`mailto:${vendor.accountManagerEmail}`} className="text-sm text-primary hover:underline">
                          {vendor.accountManagerEmail}
                        </a>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-sm">No account manager assigned</p>
                )}
                <div className="pt-4 border-t">
                  <p className="text-sm text-muted-foreground">Member Since</p>
                  <p className="font-medium">{new Date(vendor.createdAt).toLocaleDateString()}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Contacts Tab */}
        <TabsContent value="contacts">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Contacts</CardTitle>
                <CardDescription>People you work with at {vendor.name}</CardDescription>
              </div>
              <VendorContactDialog vendorId={vendor.id} />
            </CardHeader>
            <CardContent>
              {vendor.contacts && vendor.contacts.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Phone</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {vendor.contacts.map((contact) => (
                      <TableRow key={contact.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div>
                              <p className="font-medium">{contact.name}</p>
                              {contact.title && (
                                <p className="text-xs text-muted-foreground">{contact.title}</p>
                              )}
                            </div>
                            {contact.isPrimary && (
                              <Badge variant="outline" className="text-xs">Primary</Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{CONTACT_ROLE_LABELS[contact.role] || contact.role}</TableCell>
                        <TableCell>
                          {contact.email ? (
                            <a href={`mailto:${contact.email}`} className="text-primary hover:underline">
                              {contact.email}
                            </a>
                          ) : "—"}
                        </TableCell>
                        <TableCell>
                          {contact.phone || contact.mobile || "—"}
                        </TableCell>
                        <TableCell>
                          <VendorContactDialog vendorId={vendor.id} existingData={contact} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No contacts added yet.</p>
                  <p className="text-sm">Add contacts to keep track of who you work with.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Addresses Tab */}
        <TabsContent value="addresses">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Addresses</CardTitle>
                <CardDescription>Warehouses, offices, and shipping locations</CardDescription>
              </div>
              <VendorAddressDialog vendorId={vendor.id} />
            </CardHeader>
            <CardContent>
              {vendor.addresses && vendor.addresses.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {vendor.addresses.map((addr) => (
                    <div key={addr.id} className="border rounded-lg p-4 relative">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="outline">
                            {ADDRESS_TYPE_LABELS[addr.type] || addr.type}
                          </Badge>
                          {addr.isPrimary && (
                            <Badge variant="outline" className="bg-blue-100 text-blue-800">Primary</Badge>
                          )}
                        </div>
                        <VendorAddressDialog vendorId={vendor.id} existingData={addr} />
                      </div>
                      {addr.label && (
                        <p className="font-medium text-sm mb-1">{addr.label}</p>
                      )}
                      <div className="text-sm text-muted-foreground space-y-0.5">
                        <p>{addr.street1}</p>
                        {addr.street2 && <p>{addr.street2}</p>}
                        <p>
                          {addr.city}{addr.state && `, ${addr.state}`} {addr.postalCode}
                        </p>
                        <p>{addr.country}</p>
                      </div>
                      {addr.contactName && (
                        <div className="mt-3 pt-3 border-t text-sm">
                          <p className="font-medium">{addr.contactName}</p>
                          {addr.contactPhone && <p className="text-muted-foreground">{addr.contactPhone}</p>}
                          {addr.contactEmail && <p className="text-muted-foreground">{addr.contactEmail}</p>}
                        </div>
                      )}
                      {addr.shippingNotes && (
                        <p className="text-xs text-muted-foreground mt-2 italic">
                          {addr.shippingNotes}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Building2 className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No addresses added yet.</p>
                  <p className="text-sm">Add warehouse and office locations.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Documents Tab */}
        <TabsContent value="documents">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Documents</CardTitle>
                <CardDescription>W-9s, certificates, contracts, and more</CardDescription>
              </div>
              <VendorDocumentUpload vendorId={vendor.id} />
            </CardHeader>
            <CardContent>
              {vendor.documents && vendor.documents.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Document</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Uploaded</TableHead>
                      <TableHead>Expires</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {vendor.documents.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">{doc.name}</span>
                          </div>
                        </TableCell>
                        <TableCell>{DOC_TYPE_LABELS[doc.type] || doc.type}</TableCell>
                        <TableCell className="text-muted-foreground">{formatBytes(doc.sizeBytes)}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(doc.uploadedAt).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          {doc.expiresAt ? (
                            <span className={
                              isExpired(doc.expiresAt) 
                                ? "text-red-600 font-medium" 
                                : isExpiringSoon(doc.expiresAt) 
                                  ? "text-yellow-600 font-medium" 
                                  : ""
                            }>
                              {new Date(doc.expiresAt).toLocaleDateString()}
                              {isExpired(doc.expiresAt) && " (Expired)"}
                              {isExpiringSoon(doc.expiresAt) && !isExpired(doc.expiresAt) && " (Soon)"}
                            </span>
                          ) : "—"}
                        </TableCell>
                        <TableCell>
                          <DocumentDownloadButton docId={doc.id} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No documents uploaded yet.</p>
                  <p className="text-sm">Upload W-9s, certificates, and contracts.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Products Tab */}
        <TabsContent value="products">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Products from this Vendor</CardTitle>
                <CardDescription>Products you source from {vendor.name}</CardDescription>
              </div>
              <VendorProductDialog vendorId={vendor.id} />
            </CardHeader>
            <CardContent>
              {vendor.products && vendor.products.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Product</TableHead>
                      <TableHead>Vendor SKU</TableHead>
                      <TableHead className="text-right">Unit Cost</TableHead>
                      <TableHead className="text-center">MOQ</TableHead>
                      <TableHead className="text-center">Order Multiple</TableHead>
                      <TableHead className="text-center">Case Pack</TableHead>
                      <TableHead className="text-center">Lead Time</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {vendor.products.map((vp) => (
                      <TableRow key={vp.id}>
                        <TableCell>
                          <Link href={`/products/${vp.product.id}`} className="hover:underline">
                            <div className="font-medium">{vp.product.name}</div>
                            <div className="text-xs text-muted-foreground">{vp.product.sku}</div>
                          </Link>
                        </TableCell>
                        <TableCell className="font-mono text-sm">{vp.vendorSku}</TableCell>
                        <TableCell className="text-right font-medium">
                          ${Number(vp.unitCost).toFixed(2)}
                        </TableCell>
                        <TableCell className="text-center">{vp.minOrderQty}</TableCell>
                        <TableCell className="text-center">{vp.orderMultiple}</TableCell>
                        <TableCell className="text-center">{vp.casePackQty || "—"}</TableCell>
                        <TableCell className="text-center">
                          {vp.leadTimeDays ? `${vp.leadTimeDays} days` : "Default"}
                        </TableCell>
                        <TableCell>
                          {vp.isPreferred && (
                            <Badge variant="outline" className="bg-yellow-100 text-yellow-800">
                              Preferred
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Package className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No products linked to this vendor yet.</p>
                  <p className="text-sm">Add products to track what you source from this vendor.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
