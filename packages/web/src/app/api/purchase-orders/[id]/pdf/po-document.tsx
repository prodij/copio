import React from "react";
import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";

const styles = StyleSheet.create({
  page: {
    padding: 40,
    fontSize: 10,
    fontFamily: "Helvetica",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 30,
  },
  title: {
    fontSize: 24,
    fontWeight: "bold",
    color: "#1a1a1a",
  },
  subtitle: {
    fontSize: 10,
    color: "#666",
    marginTop: 4,
  },
  poNumber: {
    fontSize: 14,
    fontWeight: "bold",
    textAlign: "right",
  },
  status: {
    fontSize: 10,
    color: "#666",
    textAlign: "right",
    marginTop: 4,
  },
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "bold",
    marginBottom: 8,
    color: "#333",
    borderBottomWidth: 1,
    borderBottomColor: "#e5e5e5",
    paddingBottom: 4,
  },
  row: {
    flexDirection: "row",
    marginBottom: 4,
  },
  label: {
    width: 100,
    color: "#666",
  },
  value: {
    flex: 1,
    color: "#1a1a1a",
  },
  infoGrid: {
    flexDirection: "row",
    gap: 40,
  },
  infoBox: {
    flex: 1,
  },
  table: {
    marginTop: 10,
  },
  tableHeader: {
    flexDirection: "row",
    backgroundColor: "#f5f5f5",
    borderBottomWidth: 1,
    borderBottomColor: "#e5e5e5",
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  tableRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: "#f0f0f0",
    paddingVertical: 8,
    paddingHorizontal: 8,
  },
  colSku: { width: "15%" },
  colProduct: { width: "35%" },
  colQty: { width: "12%", textAlign: "center" },
  colCost: { width: "15%", textAlign: "right" },
  colTotal: { width: "18%", textAlign: "right" },
  headerText: {
    fontWeight: "bold",
    fontSize: 9,
    color: "#666",
  },
  totalsSection: {
    marginTop: 20,
    alignItems: "flex-end",
  },
  totalsBox: {
    width: 200,
  },
  totalRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  totalLabel: {
    color: "#666",
  },
  totalValue: {
    fontWeight: "bold",
  },
  grandTotal: {
    borderTopWidth: 1,
    borderTopColor: "#333",
    marginTop: 4,
    paddingTop: 8,
  },
  grandTotalLabel: {
    fontSize: 12,
    fontWeight: "bold",
  },
  grandTotalValue: {
    fontSize: 12,
    fontWeight: "bold",
  },
  notes: {
    marginTop: 20,
    padding: 12,
    backgroundColor: "#f9f9f9",
    borderRadius: 4,
  },
  notesTitle: {
    fontWeight: "bold",
    marginBottom: 4,
  },
  footer: {
    position: "absolute",
    bottom: 30,
    left: 40,
    right: 40,
    textAlign: "center",
    color: "#999",
    fontSize: 8,
  },
});

interface POLine {
  id: string;
  quantityOrdered: number;
  quantityReceived: number;
  unitCost: number;
  notes: string | null;
  product: {
    sku: string;
    name: string;
  };
}

interface PurchaseOrder {
  id: string;
  poNumber: string;
  status: string;
  notes: string | null;
  subtotal: number | null;
  tax: number | null;
  shipping: number | null;
  total: number | null;
  orderedAt: string | null;
  expectedAt: string | null;
  createdAt: string;
  vendor: {
    name: string;
    code: string | null;
    contacts?: Array<{ name: string; email?: string; phone?: string }>;
  };
  destination: {
    name: string;
    type: string;
    address: Record<string, string>;
  };
  lines: POLine[];
}

function formatDate(dateString: string | null) {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined) return "$0.00";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

export function PODocument({ po }: { po: PurchaseOrder }) {
  const primaryContact = po.vendor.contacts?.[0];

  return (
    <Document>
      <Page size="LETTER" style={styles.page}>
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>Purchase Order</Text>
            <Text style={styles.subtitle}>Generated {formatDate(new Date().toISOString())}</Text>
          </View>
          <View>
            <Text style={styles.poNumber}>{po.poNumber}</Text>
            <Text style={styles.status}>Status: {po.status}</Text>
          </View>
        </View>

        {/* Vendor & Destination Info */}
        <View style={styles.infoGrid}>
          <View style={styles.infoBox}>
            <Text style={styles.sectionTitle}>Vendor</Text>
            <Text style={{ fontWeight: "bold", marginBottom: 4 }}>{po.vendor.name}</Text>
            {po.vendor.code && <Text style={{ color: "#666" }}>Code: {po.vendor.code}</Text>}
            {primaryContact && (
              <View style={{ marginTop: 8 }}>
                <Text>{primaryContact.name}</Text>
                {primaryContact.email && <Text style={{ color: "#666" }}>{primaryContact.email}</Text>}
                {primaryContact.phone && <Text style={{ color: "#666" }}>{primaryContact.phone}</Text>}
              </View>
            )}
          </View>
          <View style={styles.infoBox}>
            <Text style={styles.sectionTitle}>Ship To</Text>
            <Text style={{ fontWeight: "bold", marginBottom: 4 }}>{po.destination.name}</Text>
            <Text style={{ color: "#666" }}>{po.destination.type}</Text>
            {po.destination.address && (
              <View style={{ marginTop: 4 }}>
                {po.destination.address.street1 && <Text>{po.destination.address.street1}</Text>}
                {po.destination.address.city && (
                  <Text>
                    {po.destination.address.city}
                    {po.destination.address.state && `, ${po.destination.address.state}`}{" "}
                    {po.destination.address.postalCode}
                  </Text>
                )}
              </View>
            )}
          </View>
        </View>

        {/* Dates */}
        <View style={[styles.section, { marginTop: 20 }]}>
          <View style={styles.row}>
            <Text style={styles.label}>Order Date:</Text>
            <Text style={styles.value}>{formatDate(po.orderedAt || po.createdAt)}</Text>
            <Text style={[styles.label, { marginLeft: 40 }]}>Expected:</Text>
            <Text style={styles.value}>{formatDate(po.expectedAt)}</Text>
          </View>
        </View>

        {/* Line Items Table */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Order Items</Text>
          <View style={styles.table}>
            <View style={styles.tableHeader}>
              <Text style={[styles.headerText, styles.colSku]}>SKU</Text>
              <Text style={[styles.headerText, styles.colProduct]}>Product</Text>
              <Text style={[styles.headerText, styles.colQty]}>Qty</Text>
              <Text style={[styles.headerText, styles.colCost]}>Unit Cost</Text>
              <Text style={[styles.headerText, styles.colTotal]}>Total</Text>
            </View>
            {po.lines.map((line) => (
              <View key={line.id} style={styles.tableRow}>
                <Text style={styles.colSku}>{line.product.sku}</Text>
                <Text style={styles.colProduct}>{line.product.name}</Text>
                <Text style={styles.colQty}>{line.quantityOrdered}</Text>
                <Text style={styles.colCost}>{formatCurrency(line.unitCost)}</Text>
                <Text style={styles.colTotal}>{formatCurrency(line.quantityOrdered * line.unitCost)}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* Totals */}
        <View style={styles.totalsSection}>
          <View style={styles.totalsBox}>
            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>Subtotal</Text>
              <Text style={styles.totalValue}>{formatCurrency(po.subtotal)}</Text>
            </View>
            {po.tax && Number(po.tax) > 0 && (
              <View style={styles.totalRow}>
                <Text style={styles.totalLabel}>Tax</Text>
                <Text style={styles.totalValue}>{formatCurrency(po.tax)}</Text>
              </View>
            )}
            {po.shipping && Number(po.shipping) > 0 && (
              <View style={styles.totalRow}>
                <Text style={styles.totalLabel}>Shipping</Text>
                <Text style={styles.totalValue}>{formatCurrency(po.shipping)}</Text>
              </View>
            )}
            <View style={[styles.totalRow, styles.grandTotal]}>
              <Text style={styles.grandTotalLabel}>Total</Text>
              <Text style={styles.grandTotalValue}>{formatCurrency(po.total)}</Text>
            </View>
          </View>
        </View>

        {/* Notes */}
        {po.notes && (
          <View style={styles.notes}>
            <Text style={styles.notesTitle}>Notes</Text>
            <Text>{po.notes}</Text>
          </View>
        )}

        {/* Footer */}
        <Text style={styles.footer}>
          {po.poNumber} • Generated by Copio
        </Text>
      </Page>
    </Document>
  );
}
