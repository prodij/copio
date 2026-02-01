/**
 * Database Seed Script
 * 
 * Populates the database with realistic dummy data for testing and development.
 * Idempotent: Can be run multiple times without duplicating data.
 * 
 * Usage: pnpm db:seed
 */

import { PrismaClient } from '@prisma/client';
import { faker } from '@faker-js/faker';
import { randomUUID } from 'crypto';

const prisma = new PrismaClient();

// Configuration
const SEED_PREFIX = 'seed-'; // Prefix for seed data identification
const TENANTS = [
  { name: 'Outdoor Adventures Co', slug: 'outdoor-adventures' },
  { name: 'Home & Garden Supply', slug: 'home-garden-supply' },
  { name: 'Tech Gadgets Direct', slug: 'tech-gadgets-direct' },
];

// Password hash for "password123" (using fastapi-users format)
// In real usage, this would be properly hashed
const SEED_PASSWORD_HASH = '$argon2id$v=19$m=65536,t=3,p=4$dummy_hash_for_seed_data';

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomDecimal(min: number, max: number, decimals: number = 2): number {
  const value = Math.random() * (max - min) + min;
  return Number(value.toFixed(decimals));
}

function randomElement<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomElements<T>(arr: T[], count: number): T[] {
  const shuffled = [...arr].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, count);
}

// Product categories by tenant type
const PRODUCT_CATEGORIES = {
  'outdoor-adventures': [
    { name: 'Camping Gear', slug: 'camping-gear' },
    { name: 'Hiking Equipment', slug: 'hiking-equipment' },
    { name: 'Fishing Supplies', slug: 'fishing-supplies' },
    { name: 'Outdoor Apparel', slug: 'outdoor-apparel' },
    { name: 'Water Sports', slug: 'water-sports' },
  ],
  'home-garden-supply': [
    { name: 'Garden Tools', slug: 'garden-tools' },
    { name: 'Outdoor Furniture', slug: 'outdoor-furniture' },
    { name: 'Planters & Pots', slug: 'planters-pots' },
    { name: 'Home Decor', slug: 'home-decor' },
    { name: 'Kitchen Supplies', slug: 'kitchen-supplies' },
  ],
  'tech-gadgets-direct': [
    { name: 'Smart Home', slug: 'smart-home' },
    { name: 'Audio & Video', slug: 'audio-video' },
    { name: 'Computer Accessories', slug: 'computer-accessories' },
    { name: 'Mobile Accessories', slug: 'mobile-accessories' },
    { name: 'Gaming', slug: 'gaming' },
  ],
};

const VENDOR_TIERS = ['STRATEGIC', 'PREFERRED', 'STANDARD', 'PROBATION'] as const;
const PRODUCT_STATUSES = ['DRAFT', 'ACTIVE', 'ARCHIVED'] as const;
const ORDER_STATUSES = ['PENDING', 'ALLOCATED', 'PICKING', 'PACKED', 'SHIPPED', 'DELIVERED', 'CANCELLED'] as const;
const PO_STATUSES = ['DRAFT', 'SUBMITTED', 'CONFIRMED', 'SHIPPED', 'PARTIAL', 'RECEIVED'] as const;
const CHANNELS = ['AMAZON', 'SHOPIFY'] as const;
const CONTACT_ROLES = ['GENERAL', 'SALES', 'ACCOUNT', 'SUPPORT', 'BILLING', 'SHIPPING'] as const;

// =============================================================================
// SEED FUNCTIONS
// =============================================================================

async function seedTenants(): Promise<Map<string, string>> {
  console.log('Seeding tenants...');
  const tenantMap = new Map<string, string>();
  
  for (const tenant of TENANTS) {
    const existing = await prisma.tenants.findUnique({
      where: { slug: tenant.slug },
    });
    
    if (existing) {
      console.log(`  Tenant ${tenant.slug} already exists, skipping...`);
      tenantMap.set(tenant.slug, existing.id);
      continue;
    }
    
    const id = randomUUID();
    await prisma.tenants.create({
      data: {
        id,
        name: tenant.name,
        slug: tenant.slug,
        timezone: 'America/Los_Angeles',
        base_currency: 'USD',
        settings: {},
      },
    });
    
    console.log(`  Created tenant: ${tenant.name}`);
    tenantMap.set(tenant.slug, id);
  }
  
  return tenantMap;
}

async function seedUsers(tenantMap: Map<string, string>): Promise<void> {
  console.log('Seeding users...');
  
  for (const [slug, tenantId] of tenantMap) {
    const adminEmail = `admin@${slug}.test`;
    
    // Check if admin exists
    const existingAdmin = await prisma.users.findUnique({
      where: { email: adminEmail },
    });
    
    if (existingAdmin) {
      console.log(`  Users for ${slug} already exist, skipping...`);
      continue;
    }
    
    // Create admin
    await prisma.users.create({
      data: {
        id: randomUUID(),
        tenant_id: tenantId,
        email: adminEmail,
        hashed_password: SEED_PASSWORD_HASH,
        first_name: faker.person.firstName(),
        last_name: faker.person.lastName(),
        role: 'admin',
        is_active: true,
        is_superuser: false,
        is_verified: true,
      },
    });
    
    // Create 1-2 member users
    const memberCount = randomInt(1, 2);
    for (let i = 0; i < memberCount; i++) {
      await prisma.users.create({
        data: {
          id: randomUUID(),
          tenant_id: tenantId,
          email: `member${i + 1}@${slug}.test`,
          hashed_password: SEED_PASSWORD_HASH,
          first_name: faker.person.firstName(),
          last_name: faker.person.lastName(),
          role: 'member',
          is_active: true,
          is_superuser: false,
          is_verified: true,
        },
      });
    }
    
    console.log(`  Created ${memberCount + 1} users for ${slug}`);
  }
}

async function seedCategories(tenantMap: Map<string, string>): Promise<Map<string, string[]>> {
  console.log('Seeding categories...');
  const categoryMap = new Map<string, string[]>();
  
  for (const [slug, tenantId] of tenantMap) {
    const categories = PRODUCT_CATEGORIES[slug as keyof typeof PRODUCT_CATEGORIES] || [];
    const categoryIds: string[] = [];
    
    for (const cat of categories) {
      const existing = await prisma.category.findUnique({
        where: { slug: `${slug}-${cat.slug}` },
      });
      
      if (existing) {
        categoryIds.push(existing.id);
        continue;
      }
      
      const category = await prisma.category.create({
        data: {
          tenantId,
          name: cat.name,
          slug: `${slug}-${cat.slug}`,
          amazonBrowseNode: faker.string.numeric(10),
          shopifyProductType: cat.name,
        },
      });
      categoryIds.push(category.id);
    }
    
    categoryMap.set(tenantId, categoryIds);
    console.log(`  Created ${categories.length} categories for ${slug}`);
  }
  
  return categoryMap;
}

async function seedVendors(tenantMap: Map<string, string>): Promise<Map<string, string[]>> {
  console.log('Seeding vendors...');
  const vendorMap = new Map<string, string[]>();
  
  for (const [slug, tenantId] of tenantMap) {
    const vendorIds: string[] = [];
    const vendorCount = randomInt(10, 20);
    
    // Check if vendors exist for this tenant
    const existingVendors = await prisma.vendor.findMany({
      where: { tenantId },
      take: 1,
    });
    
    if (existingVendors.length > 0) {
      const allVendors = await prisma.vendor.findMany({
        where: { tenantId },
        select: { id: true },
      });
      vendorMap.set(tenantId, allVendors.map(v => v.id));
      console.log(`  Vendors for ${slug} already exist, skipping...`);
      continue;
    }
    
    for (let i = 0; i < vendorCount; i++) {
      const companyName = faker.company.name();
      const code = companyName.substring(0, 4).toUpperCase().replace(/[^A-Z]/g, '') + faker.string.numeric(3);
      
      const vendor = await prisma.vendor.create({
        data: {
          tenantId,
          name: companyName,
          legalName: `${companyName} LLC`,
          code,
          taxId: faker.string.numeric(9),
          website: faker.internet.url(),
          tier: randomElement([...VENDOR_TIERS]),
          category: faker.commerce.department(),
          tags: [faker.commerce.department(), faker.commerce.productAdjective()],
          leadTimeDays: randomInt(7, 30),
          minOrderValue: randomDecimal(100, 1000),
          paymentTerms: randomElement(['Net 30', 'Net 45', '2/10 Net 30', 'COD']),
          currency: 'USD',
          isActive: Math.random() > 0.1,
        },
      });
      
      vendorIds.push(vendor.id);
      
      // Add 1-3 contacts
      const contactCount = randomInt(1, 3);
      for (let j = 0; j < contactCount; j++) {
        await prisma.vendorContact.create({
          data: {
            vendorId: vendor.id,
            name: faker.person.fullName(),
            title: faker.person.jobTitle(),
            email: faker.internet.email(),
            phone: faker.phone.number(),
            role: randomElement([...CONTACT_ROLES]),
            isPrimary: j === 0,
            isActive: true,
          },
        });
      }
      
      // Add 1-2 addresses
      const addressCount = randomInt(1, 2);
      for (let j = 0; j < addressCount; j++) {
        await prisma.vendorAddress.create({
          data: {
            vendorId: vendor.id,
            type: j === 0 ? 'WAREHOUSE' : randomElement(['CORPORATE', 'BILLING', 'RETURNS']),
            label: j === 0 ? 'Main Warehouse' : undefined,
            isPrimary: j === 0,
            street1: faker.location.streetAddress(),
            street2: Math.random() > 0.7 ? faker.location.secondaryAddress() : undefined,
            city: faker.location.city(),
            state: faker.location.state({ abbreviated: true }),
            postalCode: faker.location.zipCode(),
            country: 'US',
            contactName: faker.person.fullName(),
            contactPhone: faker.phone.number(),
            isActive: true,
          },
        });
      }
    }
    
    vendorMap.set(tenantId, vendorIds);
    console.log(`  Created ${vendorCount} vendors with contacts/addresses for ${slug}`);
  }
  
  return vendorMap;
}

async function seedLocations(tenantMap: Map<string, string>): Promise<Map<string, string[]>> {
  console.log('Seeding locations...');
  const locationMap = new Map<string, string[]>();
  
  for (const [slug, tenantId] of tenantMap) {
    const existingLocations = await prisma.location.findMany({
      where: { tenantId },
      take: 1,
    });
    
    if (existingLocations.length > 0) {
      const allLocations = await prisma.location.findMany({
        where: { tenantId },
        select: { id: true },
      });
      locationMap.set(tenantId, allLocations.map(l => l.id));
      console.log(`  Locations for ${slug} already exist, skipping...`);
      continue;
    }
    
    const locationIds: string[] = [];
    
    // Create 2-3 warehouses
    const warehouseCount = randomInt(2, 3);
    const warehouseNames = ['Main Warehouse', 'East Coast DC', 'West Coast DC', 'Central Hub'];
    
    for (let i = 0; i < warehouseCount; i++) {
      const loc = await prisma.location.create({
        data: {
          tenantId,
          name: warehouseNames[i] || `Warehouse ${i + 1}`,
          type: 'WAREHOUSE',
          address: {
            street: faker.location.streetAddress(),
            city: faker.location.city(),
            state: faker.location.state({ abbreviated: true }),
            zip: faker.location.zipCode(),
            country: 'US',
          },
          isActive: true,
        },
      });
      locationIds.push(loc.id);
    }
    
    // Create 2-3 FBA locations
    const fbaLocations = ['PHX3', 'ONT8', 'BFI4', 'SDF8'];
    const fbaCount = randomInt(2, 3);
    
    for (let i = 0; i < fbaCount; i++) {
      const loc = await prisma.location.create({
        data: {
          tenantId,
          name: `Amazon FBA - ${fbaLocations[i]}`,
          type: 'FBA',
          channel: 'AMAZON',
          address: {},
          isActive: true,
        },
      });
      locationIds.push(loc.id);
    }
    
    locationMap.set(tenantId, locationIds);
    console.log(`  Created ${warehouseCount + fbaCount} locations for ${slug}`);
  }
  
  return locationMap;
}

async function seedProducts(
  tenantMap: Map<string, string>,
  categoryMap: Map<string, string[]>,
  vendorMap: Map<string, string[]>
): Promise<Map<string, string[]>> {
  console.log('Seeding products...');
  const productMap = new Map<string, string[]>();
  
  for (const [slug, tenantId] of tenantMap) {
    const existingProducts = await prisma.product.findMany({
      where: { tenantId },
      take: 1,
    });
    
    if (existingProducts.length > 0) {
      const allProducts = await prisma.product.findMany({
        where: { tenantId },
        select: { id: true },
      });
      productMap.set(tenantId, allProducts.map(p => p.id));
      console.log(`  Products for ${slug} already exist, skipping...`);
      continue;
    }
    
    const productIds: string[] = [];
    const productCount = randomInt(50, 100);
    const categoryIds = categoryMap.get(tenantId) || [];
    const vendorIds = vendorMap.get(tenantId) || [];
    
    for (let i = 0; i < productCount; i++) {
      const productName = faker.commerce.productName();
      const sku = `${slug.substring(0, 3).toUpperCase()}-${faker.string.alphanumeric(6).toUpperCase()}`;
      
      const product = await prisma.product.create({
        data: {
          tenantId,
          sku,
          name: productName,
          productType: 'SIMPLE',
          status: randomElement([...PRODUCT_STATUSES]),
          brand: faker.company.name(),
          manufacturer: faker.company.name(),
          shortDescription: faker.commerce.productDescription(),
          longDescription: faker.lorem.paragraphs(2),
          bulletPoints: Array.from({ length: 5 }, () => faker.commerce.productDescription().substring(0, 100)),
          searchTerms: Array.from({ length: 5 }, () => faker.commerce.productAdjective()),
          upc: faker.string.numeric(12),
          weightValue: randomDecimal(0.1, 50, 2),
          weightUnit: 'lb',
          lengthValue: randomDecimal(1, 30, 2),
          widthValue: randomDecimal(1, 30, 2),
          heightValue: randomDecimal(1, 30, 2),
          dimensionUnit: 'in',
          countryOfOrigin: randomElement(['US', 'CN', 'MX', 'VN', 'IN']),
          costPrice: randomDecimal(5, 100),
          msrp: randomDecimal(15, 300),
        },
      });
      
      productIds.push(product.id);
      
      // Add 1-4 images
      const imageCount = randomInt(1, 4);
      for (let j = 0; j < imageCount; j++) {
        await prisma.productImage.create({
          data: {
            productId: product.id,
            url: `https://picsum.photos/seed/${product.id}-${j}/800/800`,
            altText: `${productName} - Image ${j + 1}`,
            position: j,
            width: 800,
            height: 800,
          },
        });
      }
      
      // Add 2-5 attributes
      const attributes = [
        { name: 'Material', value: faker.commerce.productMaterial() },
        { name: 'Color', value: faker.color.human() },
        { name: 'Size', value: randomElement(['Small', 'Medium', 'Large', 'XL']) },
        { name: 'Style', value: faker.commerce.productAdjective() },
        { name: 'Season', value: randomElement(['Spring', 'Summer', 'Fall', 'Winter', 'All Season']) },
      ];
      const attrCount = randomInt(2, 5);
      for (let j = 0; j < attrCount; j++) {
        await prisma.productAttribute.create({
          data: {
            productId: product.id,
            name: attributes[j].name,
            value: attributes[j].value,
          },
        });
      }
      
      // Assign to 1-2 categories
      if (categoryIds.length > 0) {
        const catCount = randomInt(1, 2);
        const selectedCats = randomElements(categoryIds, catCount);
        for (let j = 0; j < selectedCats.length; j++) {
          await prisma.productCategory.create({
            data: {
              productId: product.id,
              categoryId: selectedCats[j],
              isPrimary: j === 0,
            },
          });
        }
      }
      
      // Create channel listings (Amazon and/or Shopify)
      const channels = Math.random() > 0.3 ? ['AMAZON', 'SHOPIFY'] : [randomElement(['AMAZON', 'SHOPIFY'])];
      for (const channel of channels) {
        const price = randomDecimal(15, 300);
        await prisma.channelListing.create({
          data: {
            tenantId,
            productId: product.id,
            channel: channel as 'AMAZON' | 'SHOPIFY',
            channelSku: channel === 'AMAZON' 
              ? `B${faker.string.alphanumeric(9).toUpperCase()}`
              : `${faker.string.numeric(13)}`,
            price,
            compareAtPrice: Math.random() > 0.5 ? price * 1.2 : undefined,
            status: randomElement(['DRAFT', 'ACTIVE', 'ACTIVE', 'ACTIVE', 'INACTIVE']),
            fulfillmentChannel: channel === 'AMAZON' && Math.random() > 0.5 ? 'MARKETPLACE' : 'MERCHANT',
            bufferStock: randomInt(0, 5),
          },
        });
      }
      
      // Link to 1-2 vendors
      if (vendorIds.length > 0) {
        const vpCount = randomInt(1, 2);
        const selectedVendors = randomElements(vendorIds, vpCount);
        for (let j = 0; j < selectedVendors.length; j++) {
          await prisma.vendorProduct.create({
            data: {
              vendorId: selectedVendors[j],
              productId: product.id,
              vendorSku: `V-${faker.string.alphanumeric(8).toUpperCase()}`,
              unitCost: randomDecimal(3, 80, 4),
              minOrderQty: randomElement([1, 6, 12, 24, 48]),
              orderMultiple: randomElement([1, 6, 12]),
              leadTimeDays: randomInt(7, 30),
              isPreferred: j === 0,
              isActive: true,
            },
          });
        }
      }
    }
    
    productMap.set(tenantId, productIds);
    console.log(`  Created ${productCount} products with images/attributes/listings for ${slug}`);
  }
  
  return productMap;
}

async function seedStockItems(
  tenantMap: Map<string, string>,
  productMap: Map<string, string[]>,
  locationMap: Map<string, string[]>
): Promise<void> {
  console.log('Seeding stock items...');
  
  for (const [slug, tenantId] of tenantMap) {
    const existingStock = await prisma.stockItem.findMany({
      where: { tenantId },
      take: 1,
    });
    
    if (existingStock.length > 0) {
      console.log(`  Stock items for ${slug} already exist, skipping...`);
      continue;
    }
    
    const productIds = productMap.get(tenantId) || [];
    const locationIds = locationMap.get(tenantId) || [];
    
    if (productIds.length === 0 || locationIds.length === 0) continue;
    
    let stockCount = 0;
    
    for (const productId of productIds) {
      // Each product has stock in 1-3 locations
      const locCount = randomInt(1, Math.min(3, locationIds.length));
      const selectedLocs = randomElements(locationIds, locCount);
      
      for (const locationId of selectedLocs) {
        const qty = randomInt(0, 500);
        await prisma.stockItem.create({
          data: {
            tenantId,
            productId,
            locationId,
            quantityAvailable: qty,
            quantityReserved: Math.floor(qty * Math.random() * 0.2),
            quantityInbound: Math.random() > 0.7 ? randomInt(10, 100) : 0,
            reorderPoint: randomInt(10, 50),
            reorderQty: randomInt(50, 200),
            costBasis: randomDecimal(5, 80),
            binLocation: `${faker.string.alpha(1).toUpperCase()}-${randomInt(1, 50)}-${randomInt(1, 5)}`,
          },
        });
        stockCount++;
      }
    }
    
    console.log(`  Created ${stockCount} stock items for ${slug}`);
  }
}

async function seedOrders(
  tenantMap: Map<string, string>,
  productMap: Map<string, string[]>,
  locationMap: Map<string, string[]>
): Promise<void> {
  console.log('Seeding orders...');
  
  for (const [slug, tenantId] of tenantMap) {
    const existingOrders = await prisma.order.findMany({
      where: { tenantId },
      take: 1,
    });
    
    if (existingOrders.length > 0) {
      console.log(`  Orders for ${slug} already exist, skipping...`);
      continue;
    }
    
    const productIds = productMap.get(tenantId) || [];
    const locationIds = locationMap.get(tenantId) || [];
    
    if (productIds.length === 0) continue;
    
    const orderCount = randomInt(20, 50);
    
    for (let i = 0; i < orderCount; i++) {
      const channel = randomElement([...CHANNELS]);
      const placedAt = faker.date.recent({ days: 30 });
      const status = randomElement([...ORDER_STATUSES]);
      
      const order = await prisma.order.create({
        data: {
          tenantId,
          channel,
          channelOrderId: channel === 'AMAZON'
            ? `${randomInt(100, 999)}-${randomInt(1000000, 9999999)}-${randomInt(1000000, 9999999)}`
            : `#${randomInt(1000, 9999)}`,
          status,
          customer: {
            name: faker.person.fullName(),
            email: faker.internet.email(),
            phone: faker.phone.number(),
          },
          shippingAddress: {
            name: faker.person.fullName(),
            street1: faker.location.streetAddress(),
            street2: Math.random() > 0.7 ? faker.location.secondaryAddress() : undefined,
            city: faker.location.city(),
            state: faker.location.state({ abbreviated: true }),
            zip: faker.location.zipCode(),
            country: 'US',
          },
          totals: {
            subtotal: 0, // Will be calculated
            shipping: randomDecimal(5, 20),
            tax: 0,
            total: 0,
          },
          placedAt,
          shippedAt: ['SHIPPED', 'DELIVERED'].includes(status) ? faker.date.between({ from: placedAt, to: new Date() }) : undefined,
          deliveredAt: status === 'DELIVERED' ? faker.date.recent({ days: 7 }) : undefined,
        },
      });
      
      // Add 1-5 order lines
      const lineCount = randomInt(1, 5);
      const selectedProducts = randomElements(productIds, lineCount);
      let subtotal = 0;
      
      for (const productId of selectedProducts) {
        const qty = randomInt(1, 5);
        const price = randomDecimal(15, 150);
        subtotal += qty * price;
        
        await prisma.orderLine.create({
          data: {
            orderId: order.id,
            productId,
            channelSku: `SKU-${faker.string.alphanumeric(8).toUpperCase()}`,
            quantity: qty,
            unitPrice: price,
            allocatedFromId: locationIds.length > 0 && Math.random() > 0.3 
              ? randomElement(locationIds) 
              : undefined,
          },
        });
      }
      
      // Update totals
      const tax = subtotal * 0.08;
      const shipping = randomDecimal(5, 20);
      await prisma.order.update({
        where: { id: order.id },
        data: {
          totals: {
            subtotal,
            shipping,
            tax,
            total: subtotal + shipping + tax,
          },
        },
      });
    }
    
    console.log(`  Created ${orderCount} orders with lines for ${slug}`);
  }
}

async function seedPurchaseOrders(
  tenantMap: Map<string, string>,
  productMap: Map<string, string[]>,
  vendorMap: Map<string, string[]>,
  locationMap: Map<string, string[]>
): Promise<void> {
  console.log('Seeding purchase orders...');
  
  for (const [slug, tenantId] of tenantMap) {
    const existingPOs = await prisma.purchaseOrder.findMany({
      where: { tenantId },
      take: 1,
    });
    
    if (existingPOs.length > 0) {
      console.log(`  Purchase orders for ${slug} already exist, skipping...`);
      continue;
    }
    
    const productIds = productMap.get(tenantId) || [];
    const vendorIds = vendorMap.get(tenantId) || [];
    const locationIds = locationMap.get(tenantId) || [];
    
    if (productIds.length === 0 || vendorIds.length === 0 || locationIds.length === 0) continue;
    
    // Get only warehouse locations
    const warehouseLocations = await prisma.location.findMany({
      where: { 
        tenantId,
        type: 'WAREHOUSE',
      },
      select: { id: true },
    });
    
    if (warehouseLocations.length === 0) continue;
    
    const poCount = randomInt(5, 10);
    
    for (let i = 0; i < poCount; i++) {
      const vendorId = randomElement(vendorIds);
      const destinationId = randomElement(warehouseLocations.map(l => l.id));
      const status = randomElement([...PO_STATUSES]);
      const orderedAt = faker.date.recent({ days: 60 });
      
      const po = await prisma.purchaseOrder.create({
        data: {
          tenantId,
          poNumber: `PO-${slug.substring(0, 3).toUpperCase()}-${faker.string.numeric(6)}`,
          vendorId,
          destinationId,
          status,
          notes: Math.random() > 0.5 ? faker.lorem.sentence() : undefined,
          orderedAt: status !== 'DRAFT' ? orderedAt : undefined,
          expectedAt: status !== 'DRAFT' ? faker.date.soon({ days: 30, refDate: orderedAt }) : undefined,
          shippedAt: ['SHIPPED', 'PARTIAL', 'RECEIVED'].includes(status) 
            ? faker.date.between({ from: orderedAt, to: new Date() }) 
            : undefined,
          receivedAt: status === 'RECEIVED' ? faker.date.recent({ days: 14 }) : undefined,
          carrier: ['SHIPPED', 'PARTIAL', 'RECEIVED'].includes(status) 
            ? randomElement(['UPS', 'FedEx', 'USPS', 'DHL', 'Freight']) 
            : undefined,
          trackingNumber: ['SHIPPED', 'PARTIAL', 'RECEIVED'].includes(status) 
            ? faker.string.alphanumeric(18).toUpperCase() 
            : undefined,
        },
      });
      
      // Add 2-8 PO lines
      const lineCount = randomInt(2, 8);
      const selectedProducts = randomElements(productIds, lineCount);
      let subtotal = 0;
      
      for (const productId of selectedProducts) {
        const qty = randomInt(10, 200);
        const cost = randomDecimal(5, 80);
        subtotal += qty * cost;
        
        const received = status === 'RECEIVED' ? qty : 
                        status === 'PARTIAL' ? Math.floor(qty * Math.random()) : 0;
        
        await prisma.pOLine.create({
          data: {
            poId: po.id,
            productId,
            quantityOrdered: qty,
            quantityReceived: received,
            unitCost: cost,
            notes: Math.random() > 0.8 ? faker.lorem.words(5) : undefined,
          },
        });
      }
      
      // Update totals
      const shipping = randomDecimal(50, 300);
      const tax = subtotal * 0.08;
      await prisma.purchaseOrder.update({
        where: { id: po.id },
        data: {
          subtotal,
          shipping,
          tax,
          total: subtotal + shipping + tax,
        },
      });
    }
    
    console.log(`  Created ${poCount} purchase orders with lines for ${slug}`);
  }
}

// =============================================================================
// MAIN
// =============================================================================

async function main() {
  console.log('🌱 Starting database seed...\n');
  
  try {
    // Step 1: Create tenants
    const tenantMap = await seedTenants();
    console.log('');
    
    // Step 2: Create users for each tenant
    await seedUsers(tenantMap);
    console.log('');
    
    // Step 3: Create categories
    const categoryMap = await seedCategories(tenantMap);
    console.log('');
    
    // Step 4: Create vendors with contacts and addresses
    const vendorMap = await seedVendors(tenantMap);
    console.log('');
    
    // Step 5: Create locations
    const locationMap = await seedLocations(tenantMap);
    console.log('');
    
    // Step 6: Create products with images, attributes, listings, vendor links
    const productMap = await seedProducts(tenantMap, categoryMap, vendorMap);
    console.log('');
    
    // Step 7: Create stock items
    await seedStockItems(tenantMap, productMap, locationMap);
    console.log('');
    
    // Step 8: Create orders with order lines
    await seedOrders(tenantMap, productMap, locationMap);
    console.log('');
    
    // Step 9: Create purchase orders with PO lines
    await seedPurchaseOrders(tenantMap, productMap, vendorMap, locationMap);
    console.log('');
    
    console.log('✅ Database seed completed successfully!\n');
    
    // Print summary
    console.log('📊 Summary:');
    for (const [slug, tenantId] of tenantMap) {
      const [userCount, vendorCount, productCount, locationCount, stockCount, orderCount, poCount] = await Promise.all([
        prisma.users.count({ where: { tenant_id: tenantId } }),
        prisma.vendor.count({ where: { tenantId } }),
        prisma.product.count({ where: { tenantId } }),
        prisma.location.count({ where: { tenantId } }),
        prisma.stockItem.count({ where: { tenantId } }),
        prisma.order.count({ where: { tenantId } }),
        prisma.purchaseOrder.count({ where: { tenantId } }),
      ]);
      
      console.log(`\n  ${slug}:`);
      console.log(`    Users: ${userCount}`);
      console.log(`    Vendors: ${vendorCount}`);
      console.log(`    Products: ${productCount}`);
      console.log(`    Locations: ${locationCount}`);
      console.log(`    Stock Items: ${stockCount}`);
      console.log(`    Orders: ${orderCount}`);
      console.log(`    Purchase Orders: ${poCount}`);
    }
    
    console.log('\n🔑 Test Credentials:');
    console.log('  Email: admin@<tenant-slug>.test');
    console.log('  Password: (use hashed_password from database or register new)');
    console.log('\n  Example tenants:');
    for (const t of TENANTS) {
      console.log(`    - ${t.slug}`);
    }
    
  } catch (error) {
    console.error('❌ Seed failed:', error);
    throw error;
  } finally {
    await prisma.$disconnect();
  }
}

main();
