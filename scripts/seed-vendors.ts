/**
 * Seed script for vendor CRM data
 * Run: npx tsx scripts/seed-vendors.ts
 */

const API_URL = process.env.API_URL || "http://localhost:8000/api/v1";

const VENDORS = [
  {
    name: "Pacific Electronics Co.",
    legalName: "Pacific Electronics Company Ltd.",
    code: "PACELEC",
    taxId: "12-3456789",
    website: "https://pacificelectronics.com",
    tier: "STRATEGIC",
    category: "Electronics",
    leadTimeDays: 21,
    minOrderValue: 5000,
    paymentTerms: "Net 30",
    creditLimit: 100000,
    currency: "USD",
    accountManagerName: "Sarah Chen",
    accountManagerEmail: "sarah@company.com",
    notes: "Primary supplier for consumer electronics. Great quality, reliable shipping.",
  },
  {
    name: "Golden Dragon Manufacturing",
    legalName: "Golden Dragon Manufacturing (Shenzhen) Co., Ltd.",
    code: "GLDDRG",
    taxId: "91440300MA5EXAMPLE",
    website: "https://goldendragon.cn",
    tier: "PREFERRED",
    category: "Manufacturing",
    leadTimeDays: 35,
    minOrderValue: 10000,
    paymentTerms: "30% deposit, 70% before shipping",
    creditLimit: 50000,
    currency: "USD",
    accountManagerName: "James Wilson",
    notes: "Handles custom manufacturing. MOQs can be negotiated for repeat orders.",
  },
  {
    name: "TechSource Components",
    legalName: "TechSource Components Inc.",
    code: "TECHSRC",
    taxId: "45-6789012",
    website: "https://techsource.com",
    tier: "PREFERRED",
    category: "Components",
    leadTimeDays: 14,
    minOrderValue: 1000,
    paymentTerms: "Net 15",
    creditLimit: 25000,
    currency: "USD",
    accountManagerName: "Mike Johnson",
    accountManagerEmail: "mike@company.com",
  },
  {
    name: "Sunrise Packaging Solutions",
    legalName: "Sunrise Packaging Solutions LLC",
    code: "SUNPKG",
    taxId: "78-9012345",
    website: "https://sunrisepackaging.com",
    tier: "STANDARD",
    category: "Packaging",
    leadTimeDays: 7,
    minOrderValue: 500,
    paymentTerms: "Net 30",
    currency: "USD",
    notes: "Fast turnaround on custom packaging. Good for rush orders.",
  },
  {
    name: "Global Freight Partners",
    legalName: "Global Freight Partners International",
    code: "GLFRT",
    taxId: "23-4567890",
    website: "https://globalfreight.com",
    tier: "STRATEGIC",
    category: "Logistics",
    leadTimeDays: 3,
    paymentTerms: "Net 45",
    creditLimit: 75000,
    currency: "USD",
    accountManagerName: "Lisa Park",
    accountManagerEmail: "lisa@company.com",
  },
  {
    name: "Apex Industrial Supply",
    legalName: "Apex Industrial Supply Corporation",
    code: "APEXIND",
    taxId: "56-7890123",
    website: "https://apexindustrial.com",
    tier: "STANDARD",
    category: "Industrial",
    leadTimeDays: 10,
    minOrderValue: 2500,
    paymentTerms: "Net 30",
    currency: "USD",
  },
  {
    name: "EcoMaterials Inc.",
    legalName: "EcoMaterials Incorporated",
    code: "ECOMAT",
    taxId: "89-0123456",
    website: "https://ecomaterials.com",
    tier: "PREFERRED",
    category: "Sustainable Materials",
    leadTimeDays: 14,
    minOrderValue: 1500,
    paymentTerms: "Net 30",
    currency: "USD",
    accountManagerName: "Emily Green",
    notes: "Certified sustainable supplier. Premium pricing but great for eco-friendly products.",
  },
  {
    name: "Midwest Distribution Co.",
    legalName: "Midwest Distribution Company",
    code: "MWDIST",
    taxId: "34-5678901",
    tier: "STANDARD",
    category: "Distribution",
    leadTimeDays: 5,
    minOrderValue: 750,
    paymentTerms: "Net 15",
    currency: "USD",
  },
  {
    name: "Premier Textiles Ltd.",
    legalName: "Premier Textiles Limited",
    code: "PREMTEX",
    taxId: "67-8901234",
    website: "https://premiertextiles.com",
    tier: "PREFERRED",
    category: "Textiles",
    leadTimeDays: 28,
    minOrderValue: 3000,
    paymentTerms: "50% deposit, 50% on delivery",
    currency: "USD",
    accountManagerName: "David Kim",
    accountManagerEmail: "david@company.com",
    notes: "High-quality fabric supplier. Custom prints available with 45-day lead time.",
  },
  {
    name: "QuickShip Fulfillment",
    legalName: "QuickShip Fulfillment Services Inc.",
    code: "QKSHIP",
    taxId: "90-1234567",
    website: "https://quickshipfulfillment.com",
    tier: "STRATEGIC",
    category: "Fulfillment",
    leadTimeDays: 1,
    paymentTerms: "Net 30",
    creditLimit: 50000,
    currency: "USD",
    accountManagerName: "Tom Bradley",
    accountManagerEmail: "tom@company.com",
    notes: "3PL partner. Same-day shipping available. Integrates with our inventory system.",
  },
];

const ADDRESSES_BY_VENDOR: Record<string, Array<{
  type: string;
  label?: string;
  isPrimary: boolean;
  street1: string;
  street2?: string;
  city: string;
  state?: string;
  postalCode?: string;
  country: string;
  contactName?: string;
  contactPhone?: string;
  contactEmail?: string;
  shippingNotes?: string;
}>> = {
  "PACELEC": [
    {
      type: "CORPORATE",
      label: "Headquarters",
      isPrimary: true,
      street1: "888 Pacific Boulevard",
      street2: "Suite 500",
      city: "Los Angeles",
      state: "CA",
      postalCode: "90017",
      country: "US",
      contactName: "Reception Desk",
      contactPhone: "(213) 555-0100",
    },
    {
      type: "WAREHOUSE",
      label: "West Coast DC",
      isPrimary: true,
      street1: "1500 Distribution Way",
      city: "Ontario",
      state: "CA",
      postalCode: "91761",
      country: "US",
      contactName: "Warehouse Manager",
      contactPhone: "(909) 555-0200",
      shippingNotes: "Dock hours: 6AM-4PM. Call ahead for appointments.",
    },
  ],
  "GLDDRG": [
    {
      type: "WAREHOUSE",
      label: "Main Factory",
      isPrimary: true,
      street1: "Building 8, Longgang Industrial Park",
      street2: "Buji Street",
      city: "Shenzhen",
      state: "Guangdong",
      postalCode: "518112",
      country: "CN",
      contactName: "Factory Manager Wang",
      contactPhone: "+86 755 8888 0001",
      contactEmail: "factory@goldendragon.cn",
    },
    {
      type: "WAREHOUSE",
      label: "Export Warehouse",
      isPrimary: false,
      street1: "Yantian Port Logistics Center",
      city: "Shenzhen",
      state: "Guangdong",
      postalCode: "518081",
      country: "CN",
      shippingNotes: "FOB Yantian. Container pickup available.",
    },
  ],
  "TECHSRC": [
    {
      type: "CORPORATE",
      isPrimary: true,
      street1: "2200 Technology Drive",
      city: "San Jose",
      state: "CA",
      postalCode: "95110",
      country: "US",
      contactPhone: "(408) 555-0300",
    },
    {
      type: "WAREHOUSE",
      label: "East Coast Facility",
      isPrimary: false,
      street1: "500 Industrial Parkway",
      city: "Newark",
      state: "NJ",
      postalCode: "07102",
      country: "US",
      shippingNotes: "2-day ground to most East Coast locations.",
    },
  ],
  "SUNPKG": [
    {
      type: "WAREHOUSE",
      isPrimary: true,
      street1: "750 Packaging Lane",
      city: "Chicago",
      state: "IL",
      postalCode: "60609",
      country: "US",
      contactName: "Production Team",
      contactPhone: "(312) 555-0400",
    },
  ],
  "GLFRT": [
    {
      type: "CORPORATE",
      isPrimary: true,
      street1: "One World Trade Center",
      street2: "Floor 85",
      city: "New York",
      state: "NY",
      postalCode: "10007",
      country: "US",
    },
    {
      type: "WAREHOUSE",
      label: "LAX Hub",
      isPrimary: false,
      street1: "6000 Avion Drive",
      city: "Los Angeles",
      state: "CA",
      postalCode: "90045",
      country: "US",
    },
    {
      type: "WAREHOUSE",
      label: "JFK Hub",
      isPrimary: false,
      street1: "JFK International Airport",
      street2: "Building 75",
      city: "Jamaica",
      state: "NY",
      postalCode: "11430",
      country: "US",
    },
  ],
  "APEXIND": [
    {
      type: "WAREHOUSE",
      isPrimary: true,
      street1: "8800 Industrial Boulevard",
      city: "Houston",
      state: "TX",
      postalCode: "77012",
      country: "US",
      contactPhone: "(713) 555-0500",
    },
  ],
  "ECOMAT": [
    {
      type: "CORPORATE",
      isPrimary: true,
      street1: "100 Green Street",
      city: "Portland",
      state: "OR",
      postalCode: "97201",
      country: "US",
      contactEmail: "info@ecomaterials.com",
    },
    {
      type: "WAREHOUSE",
      label: "Recycling Center",
      isPrimary: false,
      street1: "2500 Sustainability Way",
      city: "Eugene",
      state: "OR",
      postalCode: "97401",
      country: "US",
    },
  ],
  "MWDIST": [
    {
      type: "WAREHOUSE",
      isPrimary: true,
      street1: "4400 Distribution Center Road",
      city: "Indianapolis",
      state: "IN",
      postalCode: "46241",
      country: "US",
      shippingNotes: "Central location - 2 day ground to 80% of US.",
    },
  ],
  "PREMTEX": [
    {
      type: "WAREHOUSE",
      label: "Main Mill",
      isPrimary: true,
      street1: "1200 Textile Avenue",
      city: "Greensboro",
      state: "NC",
      postalCode: "27401",
      country: "US",
      contactName: "Mill Operations",
      contactPhone: "(336) 555-0600",
    },
    {
      type: "WAREHOUSE",
      label: "Fabric Warehouse",
      isPrimary: false,
      street1: "800 Fabric Drive",
      city: "High Point",
      state: "NC",
      postalCode: "27260",
      country: "US",
    },
  ],
  "QKSHIP": [
    {
      type: "WAREHOUSE",
      label: "West Coast FC",
      isPrimary: true,
      street1: "9000 Fulfillment Way",
      city: "Reno",
      state: "NV",
      postalCode: "89502",
      country: "US",
      contactPhone: "(775) 555-0700",
      shippingNotes: "No sales tax. Same-day cutoff 2PM PST.",
    },
    {
      type: "WAREHOUSE",
      label: "East Coast FC",
      isPrimary: false,
      street1: "3000 Commerce Drive",
      city: "Carlisle",
      state: "PA",
      postalCode: "17013",
      country: "US",
      shippingNotes: "Same-day cutoff 4PM EST.",
    },
    {
      type: "WAREHOUSE",
      label: "Central FC",
      isPrimary: false,
      street1: "7500 Logistics Parkway",
      city: "Dallas",
      state: "TX",
      postalCode: "75247",
      country: "US",
    },
  ],
};

const CONTACTS_BY_VENDOR: Record<string, Array<{
  name: string;
  title?: string;
  email?: string;
  phone?: string;
  mobile?: string;
  role: string;
  isPrimary: boolean;
  notes?: string;
}>> = {
  "PACELEC": [
    { name: "Jennifer Wu", title: "Sales Director", email: "jennifer.wu@pacificelectronics.com", phone: "(213) 555-0101", role: "SALES", isPrimary: true },
    { name: "Robert Chang", title: "Account Executive", email: "robert.chang@pacificelectronics.com", phone: "(213) 555-0102", mobile: "(213) 555-0103", role: "ACCOUNT", isPrimary: false },
    { name: "Maria Santos", title: "Billing Coordinator", email: "billing@pacificelectronics.com", phone: "(213) 555-0104", role: "BILLING", isPrimary: false },
  ],
  "GLDDRG": [
    { name: "Tony Zhang", title: "Export Manager", email: "tony.zhang@goldendragon.cn", phone: "+86 755 8888 0010", role: "SALES", isPrimary: true, notes: "Speaks excellent English. Best contact for new orders." },
    { name: "Lucy Chen", title: "QC Manager", email: "lucy.chen@goldendragon.cn", phone: "+86 755 8888 0020", role: "SUPPORT", isPrimary: false },
  ],
  "TECHSRC": [
    { name: "Steve Miller", title: "Territory Manager", email: "steve.miller@techsource.com", phone: "(408) 555-0301", role: "SALES", isPrimary: true },
    { name: "Karen Lee", title: "Technical Support", email: "support@techsource.com", phone: "(408) 555-0302", role: "SUPPORT", isPrimary: false },
  ],
  "SUNPKG": [
    { name: "Brian O'Connor", title: "Owner", email: "brian@sunrisepackaging.com", phone: "(312) 555-0401", mobile: "(312) 555-0402", role: "EXECUTIVE", isPrimary: true },
  ],
  "GLFRT": [
    { name: "Amanda Foster", title: "Logistics Coordinator", email: "amanda.foster@globalfreight.com", phone: "(212) 555-0501", role: "SHIPPING", isPrimary: true },
    { name: "James Rodriguez", title: "Account Manager", email: "james.rodriguez@globalfreight.com", phone: "(212) 555-0502", role: "ACCOUNT", isPrimary: false },
    { name: "Finance Department", email: "invoices@globalfreight.com", phone: "(212) 555-0503", role: "BILLING", isPrimary: false },
  ],
  "APEXIND": [
    { name: "Bill Thompson", title: "Sales Rep", email: "bill@apexindustrial.com", phone: "(713) 555-0501", role: "SALES", isPrimary: true },
  ],
  "ECOMAT": [
    { name: "Rachel Green", title: "Sustainability Director", email: "rachel.green@ecomaterials.com", phone: "(503) 555-0601", role: "SALES", isPrimary: true },
    { name: "Mark Johnson", title: "Operations Manager", email: "operations@ecomaterials.com", phone: "(503) 555-0602", role: "SHIPPING", isPrimary: false },
  ],
  "MWDIST": [
    { name: "Customer Service", email: "orders@mwdist.com", phone: "(317) 555-0701", role: "GENERAL", isPrimary: true },
  ],
  "PREMTEX": [
    { name: "Susan Park", title: "Fabric Specialist", email: "susan.park@premiertextiles.com", phone: "(336) 555-0601", role: "SALES", isPrimary: true },
    { name: "Design Team", email: "design@premiertextiles.com", phone: "(336) 555-0602", role: "SUPPORT", isPrimary: false, notes: "For custom print inquiries" },
  ],
  "QKSHIP": [
    { name: "Operations Center", email: "ops@quickshipfulfillment.com", phone: "(775) 555-0701", role: "SHIPPING", isPrimary: true },
    { name: "Integration Support", email: "integration@quickshipfulfillment.com", phone: "(775) 555-0702", role: "SUPPORT", isPrimary: false },
    { name: "Billing Team", email: "billing@quickshipfulfillment.com", phone: "(775) 555-0703", role: "BILLING", isPrimary: false },
  ],
};

const PRODUCTS = [
  { sku: "ELEC-BT-001", name: "Bluetooth Speaker 10W", category: "Electronics", description: "Portable Bluetooth speaker with 10W output" },
  { sku: "ELEC-BT-002", name: "Bluetooth Speaker 20W", category: "Electronics", description: "Premium Bluetooth speaker with 20W output" },
  { sku: "ELEC-HP-001", name: "Wireless Headphones", category: "Electronics", description: "Over-ear wireless headphones with ANC" },
  { sku: "ELEC-CB-001", name: "USB-C Cable 6ft", category: "Electronics", description: "Braided USB-C charging cable" },
  { sku: "ELEC-CB-002", name: "USB-C Cable 10ft", category: "Electronics", description: "Extra long USB-C charging cable" },
  { sku: "HOME-ORG-001", name: "Storage Bins Set", category: "Home", description: "Set of 6 stackable storage bins" },
  { sku: "HOME-ORG-002", name: "Drawer Organizer", category: "Home", description: "Bamboo drawer organizer" },
  { sku: "APPRL-TS-001", name: "Cotton T-Shirt Basic", category: "Apparel", description: "100% cotton basic t-shirt" },
  { sku: "APPRL-TS-002", name: "Cotton T-Shirt Premium", category: "Apparel", description: "Premium ring-spun cotton t-shirt" },
  { sku: "APPRL-HT-001", name: "Snapback Cap", category: "Apparel", description: "Adjustable snapback baseball cap" },
  { sku: "OFFICE-PEN-001", name: "Gel Pen Set", category: "Office", description: "12-pack gel pens assorted colors" },
  { sku: "OFFICE-NB-001", name: "Spiral Notebook", category: "Office", description: "College-ruled spiral notebook 100 pages" },
  { sku: "OUTDOOR-BTL-001", name: "Water Bottle 32oz", category: "Outdoor", description: "Stainless steel insulated water bottle" },
  { sku: "OUTDOOR-BAG-001", name: "Daypack 25L", category: "Outdoor", description: "Lightweight hiking daypack" },
  { sku: "TECH-CASE-001", name: "Phone Case Universal", category: "Tech Accessories", description: "Clear TPU phone case" },
];

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

async function post(endpoint: string, data: unknown, retries = 3): Promise<any> {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(`POST ${endpoint} failed: ${err}`);
      }
      await sleep(50); // Small delay between requests
      return res.json();
    } catch (e) {
      if (i === retries - 1) throw e;
      await sleep(200);
    }
  }
}

async function get(endpoint: string) {
  const res = await fetch(`${API_URL}${endpoint}`);
  if (!res.ok) throw new Error(`GET ${endpoint} failed`);
  return res.json();
}

async function main() {
  console.log("🌱 Seeding vendor data...\n");

  // Create vendors (or fetch existing)
  const vendorMap: Record<string, string> = {};
  
  // First, get existing vendors
  const existingVendors = await get("/vendors");
  for (const v of existingVendors) {
    if (v.code) vendorMap[v.code] = v.id;
  }
  console.log(`Found ${Object.keys(vendorMap).length} existing vendors`);

  for (const vendor of VENDORS) {
    if (vendorMap[vendor.code!]) {
      console.log(`⏭ Vendor exists: ${vendor.name}`);
      continue;
    }
    try {
      const created = await post("/vendors", vendor);
      vendorMap[vendor.code!] = created.id;
      console.log(`✓ Vendor: ${vendor.name}`);
    } catch (e) {
      console.log(`✗ Vendor ${vendor.name}: ${e}`);
    }
  }

  // Create addresses
  console.log("\n📍 Adding addresses...");
  for (const [code, addresses] of Object.entries(ADDRESSES_BY_VENDOR)) {
    const vendorId = vendorMap[code];
    if (!vendorId) continue;
    for (const addr of addresses) {
      try {
        await post("/vendor-addresses", { vendorId, ...addr });
        console.log(`  ✓ ${code}: ${addr.type} ${addr.label || ""}`);
      } catch (e) {
        console.log(`  ✗ ${code} address: ${e}`);
      }
    }
  }

  // Create contacts
  console.log("\n👥 Adding contacts...");
  for (const [code, contacts] of Object.entries(CONTACTS_BY_VENDOR)) {
    const vendorId = vendorMap[code];
    if (!vendorId) continue;
    for (const contact of contacts) {
      try {
        await post(`/vendors/${vendorId}/contacts`, contact);
        console.log(`  ✓ ${code}: ${contact.name}`);
      } catch (e) {
        console.log(`  ✗ ${code} contact: ${e}`);
      }
    }
  }

  // Create products (or fetch existing)
  console.log("\n📦 Creating products...");
  const productMap: Record<string, string> = {};
  
  // First, get existing products
  const existingProducts = await get("/products");
  const prodList = existingProducts.products || existingProducts;
  for (const p of prodList) {
    if (p.sku) productMap[p.sku] = p.id;
  }
  console.log(`  Found ${Object.keys(productMap).length} existing products`);

  for (const product of PRODUCTS) {
    if (productMap[product.sku]) {
      console.log(`  ⏭ Product exists: ${product.sku}`);
      continue;
    }
    try {
      const created = await post("/products", product);
      productMap[product.sku] = created.id;
      console.log(`  ✓ ${product.sku}: ${product.name}`);
    } catch (e) {
      console.log(`  ✗ ${product.sku}: ${e}`);
    }
  }

  // Link products to vendors
  console.log("\n🔗 Linking products to vendors...");
  const links = [
    { vendor: "PACELEC", sku: "ELEC-BT-001", vendorSku: "PE-SPK-10W", unitCost: 12.50, isPreferred: true },
    { vendor: "PACELEC", sku: "ELEC-BT-002", vendorSku: "PE-SPK-20W", unitCost: 22.00, isPreferred: true },
    { vendor: "PACELEC", sku: "ELEC-HP-001", vendorSku: "PE-HP-ANC", unitCost: 35.00, isPreferred: true },
    { vendor: "GLDDRG", sku: "ELEC-BT-001", vendorSku: "GD-SPKR-10", unitCost: 9.80, isPreferred: false },
    { vendor: "GLDDRG", sku: "ELEC-HP-001", vendorSku: "GD-HDPH-01", unitCost: 28.00, isPreferred: false },
    { vendor: "TECHSRC", sku: "ELEC-CB-001", vendorSku: "TS-USBC-6", unitCost: 2.25, isPreferred: true },
    { vendor: "TECHSRC", sku: "ELEC-CB-002", vendorSku: "TS-USBC-10", unitCost: 3.50, isPreferred: true },
    { vendor: "TECHSRC", sku: "TECH-CASE-001", vendorSku: "TS-CASE-CLR", unitCost: 1.80, isPreferred: true },
    { vendor: "ECOMAT", sku: "HOME-ORG-001", vendorSku: "ECO-BIN-6PK", unitCost: 18.00, isPreferred: true },
    { vendor: "ECOMAT", sku: "HOME-ORG-002", vendorSku: "ECO-BAMB-ORG", unitCost: 12.00, isPreferred: true },
    { vendor: "PREMTEX", sku: "APPRL-TS-001", vendorSku: "PT-TEE-BASIC", unitCost: 4.50, isPreferred: true },
    { vendor: "PREMTEX", sku: "APPRL-TS-002", vendorSku: "PT-TEE-PREM", unitCost: 7.25, isPreferred: true },
    { vendor: "PREMTEX", sku: "APPRL-HT-001", vendorSku: "PT-CAP-SNAP", unitCost: 5.00, isPreferred: true },
    { vendor: "MWDIST", sku: "OFFICE-PEN-001", vendorSku: "MW-PEN-12GEL", unitCost: 3.00, isPreferred: true },
    { vendor: "MWDIST", sku: "OFFICE-NB-001", vendorSku: "MW-NB-SPIRAL", unitCost: 1.50, isPreferred: true },
    { vendor: "APEXIND", sku: "OUTDOOR-BTL-001", vendorSku: "APEX-BTL-32SS", unitCost: 8.50, isPreferred: true },
    { vendor: "APEXIND", sku: "OUTDOOR-BAG-001", vendorSku: "APEX-PACK-25L", unitCost: 22.00, isPreferred: true },
  ];

  for (const link of links) {
    const vendorId = vendorMap[link.vendor];
    const productId = productMap[link.sku];
    if (!vendorId || !productId) continue;
    try {
      await post("/vendor-products", {
        vendorId,
        productId,
        vendorSku: link.vendorSku,
        unitCost: link.unitCost,
        currency: "USD",
        minOrderQty: 100,
        orderMultiple: 10,
        isPreferred: link.isPreferred,
      });
      console.log(`  ✓ ${link.vendor} → ${link.sku}`);
    } catch (e) {
      console.log(`  ✗ ${link.vendor} → ${link.sku}: ${e}`);
    }
  }

  console.log("\n✅ Seeding complete!");
}

main().catch(console.error);
