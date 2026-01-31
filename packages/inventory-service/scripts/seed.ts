/**
 * Copio Seed Script
 * 
 * Creates comprehensive test data for 3 tenants:
 * - Acme Electronics (consumer electronics)
 * - Green Garden Supply (garden/outdoor products)
 * - Urban Style Co (fashion/apparel)
 * 
 * Each tenant gets users, vendors, products, locations, orders, and POs.
 * 
 * Run: pnpm seed
 */

import { prisma } from '@copio/core';
import { faker } from '@faker-js/faker';
import { randomUUID } from 'crypto';

// ============================================================================
// CONFIGURATION
// ============================================================================

const SEED_TENANTS = [
  {
    name: 'Acme Electronics',
    slug: 'acme-electronics',
    timezone: 'America/Los_Angeles',
    baseCurrency: 'USD',
    theme: 'electronics',
  },
  {
    name: 'Green Garden Supply',
    slug: 'green-garden-supply',
    timezone: 'America/Chicago',
    baseCurrency: 'USD',
    theme: 'garden',
  },
  {
    name: 'Urban Style Co',
    slug: 'urban-style-co',
    timezone: 'America/New_York',
    baseCurrency: 'USD',
    theme: 'fashion',
  },
];

// Product templates by theme
const PRODUCT_TEMPLATES = {
  electronics: [
    { name: 'Wireless Bluetooth Earbuds', category: 'Audio', priceRange: [29, 149], attributes: { connectivity: 'Bluetooth 5.0', battery: '24hr' } },
    { name: 'USB-C Fast Charging Cable', category: 'Cables & Chargers', priceRange: [8, 24], attributes: { length: '6ft', material: 'Braided Nylon' } },
    { name: 'Portable Power Bank', category: 'Cables & Chargers', priceRange: [19, 59], attributes: { capacity: '10000mAh', ports: '2 USB' } },
    { name: 'Smart LED Light Bulb', category: 'Smart Home', priceRange: [12, 35], attributes: { wattage: '9W', lumens: '800' } },
    { name: 'Wireless Phone Charger', category: 'Cables & Chargers', priceRange: [15, 45], attributes: { power: '15W', compatibility: 'Qi' } },
    { name: 'Laptop Stand Adjustable', category: 'Computer Accessories', priceRange: [25, 65], attributes: { material: 'Aluminum', size: 'Universal' } },
    { name: 'HD Webcam 1080p', category: 'Computer Accessories', priceRange: [35, 89], attributes: { resolution: '1080p', fps: '30' } },
    { name: 'Portable Bluetooth Speaker', category: 'Audio', priceRange: [25, 79], attributes: { waterproof: 'IPX7', battery: '12hr' } },
    { name: 'Smart Plug WiFi', category: 'Smart Home', priceRange: [12, 29], attributes: { compatibility: 'Alexa/Google', amperage: '15A' } },
    { name: 'Ring Light with Tripod', category: 'Camera Accessories', priceRange: [29, 69], attributes: { diameter: '10 inch', modes: '3 color' } },
    { name: 'Mechanical Gaming Keyboard', category: 'Computer Accessories', priceRange: [49, 129], attributes: { switches: 'Blue', backlit: 'RGB' } },
    { name: 'Wireless Gaming Mouse', category: 'Computer Accessories', priceRange: [29, 89], attributes: { dpi: '16000', buttons: '6' } },
    { name: 'USB Hub 7-Port', category: 'Computer Accessories', priceRange: [19, 45], attributes: { ports: '7', speed: 'USB 3.0' } },
    { name: 'HDMI Cable 4K', category: 'Cables & Chargers', priceRange: [12, 28], attributes: { length: '6ft', version: 'HDMI 2.1' } },
    { name: 'Noise Canceling Headphones', category: 'Audio', priceRange: [79, 249], attributes: { anc: 'Active', battery: '30hr' } },
  ],
  garden: [
    { name: 'Garden Hose 50ft', category: 'Watering', priceRange: [25, 55], attributes: { material: 'Rubber', diameter: '5/8 inch' } },
    { name: 'Pruning Shears Pro', category: 'Hand Tools', priceRange: [15, 35], attributes: { blade: 'Carbon Steel', grip: 'Ergonomic' } },
    { name: 'Raised Garden Bed Kit', category: 'Planters', priceRange: [45, 129], attributes: { material: 'Cedar Wood', size: '4x4ft' } },
    { name: 'Solar Garden Lights 8-Pack', category: 'Lighting', priceRange: [24, 48], attributes: { lumens: '15', runtime: '8hr' } },
    { name: 'Potting Soil 40lb', category: 'Soil & Fertilizer', priceRange: [12, 24], attributes: { type: 'All-Purpose', organic: 'Yes' } },
    { name: 'Garden Trowel Set', category: 'Hand Tools', priceRange: [12, 28], attributes: { pieces: '3', material: 'Stainless Steel' } },
    { name: 'Plant Support Stakes 20pk', category: 'Plant Care', priceRange: [14, 28], attributes: { height: '4ft', material: 'Bamboo' } },
    { name: 'Wheelbarrow Steel', category: 'Carts & Wheelbarrows', priceRange: [65, 149], attributes: { capacity: '6 cu ft', wheels: '2' } },
    { name: 'Sprinkler System Timer', category: 'Watering', priceRange: [35, 89], attributes: { zones: '4', wifi: 'Yes' } },
    { name: 'Garden Gloves 3-Pack', category: 'Apparel', priceRange: [12, 24], attributes: { material: 'Nitrile', sizes: 'S/M/L' } },
    { name: 'Compost Bin 80gal', category: 'Composting', priceRange: [55, 129], attributes: { material: 'Recycled Plastic', tumbler: 'Yes' } },
    { name: 'Leaf Blower Electric', category: 'Power Tools', priceRange: [49, 119], attributes: { power: '400 CFM', weight: '4.5lb' } },
    { name: 'Bird Feeder Hanging', category: 'Bird & Wildlife', priceRange: [18, 45], attributes: { capacity: '2lb', material: 'Cedar' } },
    { name: 'Outdoor Plant Stand', category: 'Planters', priceRange: [28, 65], attributes: { tiers: '3', material: 'Iron' } },
    { name: 'Garden Kneeling Pad', category: 'Apparel', priceRange: [15, 32], attributes: { thickness: '2 inch', waterproof: 'Yes' } },
  ],
  fashion: [
    { name: 'Classic Cotton T-Shirt', category: 'Tops', priceRange: [18, 35], attributes: { material: '100% Cotton', fit: 'Regular' } },
    { name: 'Slim Fit Jeans', category: 'Bottoms', priceRange: [45, 89], attributes: { material: 'Stretch Denim', rise: 'Mid' } },
    { name: 'Leather Belt', category: 'Accessories', priceRange: [25, 55], attributes: { material: 'Genuine Leather', width: '1.5 inch' } },
    { name: 'Casual Sneakers', category: 'Footwear', priceRange: [49, 99], attributes: { material: 'Canvas', sole: 'Rubber' } },
    { name: 'Wool Blend Sweater', category: 'Tops', priceRange: [55, 125], attributes: { material: 'Wool Blend', style: 'Crew Neck' } },
    { name: 'Denim Jacket', category: 'Outerwear', priceRange: [65, 149], attributes: { material: 'Cotton Denim', wash: 'Medium' } },
    { name: 'Canvas Tote Bag', category: 'Bags', priceRange: [28, 55], attributes: { material: 'Canvas', closure: 'Zipper' } },
    { name: 'Silk Scarf', category: 'Accessories', priceRange: [35, 89], attributes: { material: '100% Silk', size: '35x35 inch' } },
    { name: 'Chino Pants', category: 'Bottoms', priceRange: [45, 85], attributes: { material: 'Cotton Twill', fit: 'Slim' } },
    { name: 'Sunglasses Classic', category: 'Accessories', priceRange: [29, 75], attributes: { lens: 'UV400', frame: 'Acetate' } },
    { name: 'Oxford Button-Down Shirt', category: 'Tops', priceRange: [45, 85], attributes: { material: 'Oxford Cotton', collar: 'Button-Down' } },
    { name: 'Ankle Boots', category: 'Footwear', priceRange: [79, 169], attributes: { material: 'Leather', heel: '2 inch' } },
    { name: 'Linen Shorts', category: 'Bottoms', priceRange: [35, 65], attributes: { material: 'Linen Blend', length: '7 inch' } },
    { name: 'Crossbody Bag', category: 'Bags', priceRange: [45, 99], attributes: { material: 'Vegan Leather', strap: 'Adjustable' } },
    { name: 'Baseball Cap', category: 'Accessories', priceRange: [22, 42], attributes: { material: 'Cotton Twill', closure: 'Adjustable' } },
  ],
};

const CATEGORY_HIERARCHIES = {
  electronics: [
    { name: 'Electronics', slug: 'electronics', children: [
      { name: 'Audio', slug: 'audio' },
      { name: 'Smart Home', slug: 'smart-home' },
      { name: 'Computer Accessories', slug: 'computer-accessories' },
      { name: 'Cables & Chargers', slug: 'cables-chargers' },
      { name: 'Camera Accessories', slug: 'camera-accessories' },
    ]},
  ],
  garden: [
    { name: 'Garden & Outdoor', slug: 'garden-outdoor', children: [
      { name: 'Watering', slug: 'watering' },
      { name: 'Hand Tools', slug: 'hand-tools' },
      { name: 'Power Tools', slug: 'power-tools' },
      { name: 'Planters', slug: 'planters' },
      { name: 'Soil & Fertilizer', slug: 'soil-fertilizer' },
      { name: 'Plant Care', slug: 'plant-care' },
      { name: 'Lighting', slug: 'lighting' },
      { name: 'Carts & Wheelbarrows', slug: 'carts-wheelbarrows' },
      { name: 'Composting', slug: 'composting' },
      { name: 'Bird & Wildlife', slug: 'bird-wildlife' },
      { name: 'Apparel', slug: 'garden-apparel' },
    ]},
  ],
  fashion: [
    { name: 'Apparel', slug: 'apparel', children: [
      { name: 'Tops', slug: 'tops' },
      { name: 'Bottoms', slug: 'bottoms' },
      { name: 'Outerwear', slug: 'outerwear' },
      { name: 'Footwear', slug: 'footwear' },
      { name: 'Accessories', slug: 'accessories' },
      { name: 'Bags', slug: 'bags' },
    ]},
  ],
};

const COLORS = {
  electronics: ['Black', 'White', 'Space Gray', 'Silver', 'Navy', 'Rose Gold'],
  garden: ['Green', 'Brown', 'Natural', 'Terracotta', 'Black', 'Gray'],
  fashion: ['Black', 'White', 'Navy', 'Gray', 'Olive', 'Burgundy', 'Cream', 'Tan'],
};

const SIZES = {
  electronics: null, // No sizes for electronics
  garden: ['Small', 'Medium', 'Large'],
  fashion: ['XS', 'S', 'M', 'L', 'XL', 'XXL'],
};

const VENDOR_PREFIXES = {
  electronics: ['Tech', 'Digital', 'Smart', 'Pro', 'Elite', 'Prime', 'Core', 'Apex'],
  garden: ['Green', 'Eco', 'Nature', 'Garden', 'Bloom', 'Terra', 'Grow', 'Plant'],
  fashion: ['Urban', 'Metro', 'Style', 'Thread', 'Fabric', 'Lux', 'Mode', 'Trend'],
};

const VENDOR_SUFFIXES = {
  electronics: ['Solutions', 'Dynamics', 'Systems', 'Tech', 'Labs', 'Electronics', 'Innovations'],
  garden: ['Supply', 'Products', 'Goods', 'Co', 'Works', 'Essentials', 'Direct'],
  fashion: ['Apparel', 'Wear', 'Collection', 'Brand', 'Co', 'Fashion', 'Designs'],
};

// ============================================================================
// HELPERS
// ============================================================================

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomFloat(min: number, max: number, decimals = 2): number {
  return parseFloat((Math.random() * (max - min) + min).toFixed(decimals));
}

function randomElement<T>(arr: T[]): T {
  return arr[randomInt(0, arr.length - 1)];
}

function randomElements<T>(arr: T[], count: number): T[] {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, Math.min(count, arr.length));
}

function generateSKU(prefix: string, index: number): string {
  return `${prefix}-${String(index).padStart(5, '0')}`;
}

function generateASIN(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  return 'B0' + Array.from({ length: 8 }, () => chars[randomInt(0, chars.length - 1)]).join('');
}

function generateUPC(): string {
  return Array.from({ length: 12 }, () => randomInt(0, 9)).join('');
}

function generateOrderId(channel: string): string {
  const prefix = channel === 'AMAZON' ? '111' : channel === 'SHOPIFY' ? 'SHP' : channel === 'WALMART' ? 'WMT' : 'EB';
  return `${prefix}-${randomInt(1000000, 9999999)}`;
}

function generatePONumber(vendorCode: string, index: number): string {
  const date = new Date();
  return `PO-${vendorCode}-${date.getFullYear()}${String(date.getMonth() + 1).padStart(2, '0')}-${String(index).padStart(3, '0')}`;
}

function hashPassword(password: string): string {
  // Simple hash for seed data - in production this would be bcrypt
  // Using a recognizable prefix so we know it's seed data
  return `$argon2id$v=19$m=65536,t=3,p=4$SEEDDATA$${Buffer.from(password).toString('base64')}`;
}

// ============================================================================
// SEED FUNCTIONS
// ============================================================================

async function checkExistingSeedData(): Promise<string[]> {
  const existingSlugs: string[] = [];
  
  for (const tenant of SEED_TENANTS) {
    const existing = await prisma.tenants.findUnique({
      where: { slug: tenant.slug },
    });
    if (existing) {
      existingSlugs.push(tenant.slug);
    }
  }
  
  return existingSlugs;
}

async function cleanTenantData(tenantId: string): Promise<void> {
  console.log(`    Cleaning existing data for tenant...`);
  
  // Delete in reverse dependency order
  await prisma.stockMovement.deleteMany({ where: { tenantId } });
  await prisma.orderLine.deleteMany({ where: { order: { tenantId } } });
  await prisma.order.deleteMany({ where: { tenantId } });
  await prisma.pOLine.deleteMany({ where: { purchaseOrder: { tenantId } } });
  await prisma.purchaseOrder.deleteMany({ where: { tenantId } });
  await prisma.stockItem.deleteMany({ where: { tenantId } });
  await prisma.channelListing.deleteMany({ where: { tenantId } });
  await prisma.vendorProduct.deleteMany({ where: { vendor: { tenantId } } });
  await prisma.productAttribute.deleteMany({ where: { product: { tenantId } } });
  await prisma.productImage.deleteMany({ where: { product: { tenantId } } });
  await prisma.productCategory.deleteMany({ where: { product: { tenantId } } });
  await prisma.product.deleteMany({ where: { tenantId } });
  await prisma.vendorDocument.deleteMany({ where: { vendor: { tenantId } } });
  await prisma.vendorAddress.deleteMany({ where: { vendor: { tenantId } } });
  await prisma.vendorContact.deleteMany({ where: { vendor: { tenantId } } });
  await prisma.vendor.deleteMany({ where: { tenantId } });
  await prisma.location.deleteMany({ where: { tenantId } });
  await prisma.category.deleteMany({ where: { tenantId } });
  await prisma.users.deleteMany({ where: { tenant_id: tenantId } });
}

async function seedTenant(
  tenantConfig: typeof SEED_TENANTS[0]
): Promise<{ tenantId: string; stats: Record<string, number> }> {
  const theme = tenantConfig.theme as keyof typeof PRODUCT_TEMPLATES;
  const stats: Record<string, number> = {};
  
  console.log(`\n📦 Seeding tenant: ${tenantConfig.name}`);
  
  // Check if tenant exists
  let tenant = await prisma.tenants.findUnique({
    where: { slug: tenantConfig.slug },
  });
  
  if (tenant) {
    console.log(`  Tenant exists, cleaning data...`);
    await cleanTenantData(tenant.id);
  } else {
    // Create tenant
    tenant = await prisma.tenants.create({
      data: {
        id: randomUUID(),
        name: tenantConfig.name,
        slug: tenantConfig.slug,
        timezone: tenantConfig.timezone,
        base_currency: tenantConfig.baseCurrency,
        settings: {},
      },
    });
    console.log(`  Created tenant: ${tenant.id}`);
  }
  
  const tenantId = tenant.id;
  
  // Create users (1 admin + 2 members)
  console.log(`  Creating users...`);
  const users = [
    { firstName: faker.person.firstName(), lastName: faker.person.lastName(), role: 'admin' },
    { firstName: faker.person.firstName(), lastName: faker.person.lastName(), role: 'member' },
    { firstName: faker.person.firstName(), lastName: faker.person.lastName(), role: 'member' },
  ];
  
  for (const user of users) {
    const email = `${user.firstName.toLowerCase()}.${user.lastName.toLowerCase()}@${tenantConfig.slug.replace(/-/g, '')}.test`;
    await prisma.users.create({
      data: {
        id: randomUUID(),
        tenant_id: tenantId,
        first_name: user.firstName,
        last_name: user.lastName,
        email,
        role: user.role,
        hashed_password: hashPassword('password123'),
        is_active: true,
        is_superuser: user.role === 'admin',
        is_verified: true,
      },
    });
  }
  stats.users = users.length;
  
  // Create categories
  console.log(`  Creating categories...`);
  const categoryMap: Record<string, string> = {};
  const categoryHierarchy = CATEGORY_HIERARCHIES[theme];
  
  for (const parent of categoryHierarchy) {
    const parentSlug = `${tenantConfig.slug}-${parent.slug}`;
    const parentCat = await prisma.category.create({
      data: {
        tenantId,
        name: parent.name,
        slug: parentSlug,
        description: `${parent.name} products`,
      },
    });
    categoryMap[parent.name] = parentCat.id;
    
    for (const child of parent.children) {
      const childSlug = `${tenantConfig.slug}-${child.slug}`;
      const childCat = await prisma.category.create({
        data: {
          tenantId,
          name: child.name,
          slug: childSlug,
          parentId: parentCat.id,
          description: `${child.name} products`,
        },
      });
      categoryMap[child.name] = childCat.id;
    }
  }
  stats.categories = Object.keys(categoryMap).length;
  
  // Create vendors (15 per tenant)
  console.log(`  Creating vendors...`);
  const vendors: { id: string; code: string }[] = [];
  const prefixes = VENDOR_PREFIXES[theme];
  const suffixes = VENDOR_SUFFIXES[theme];
  
  for (let i = 0; i < 15; i++) {
    const vendorName = `${randomElement(prefixes)} ${faker.company.name().split(' ')[0]} ${randomElement(suffixes)}`;
    const vendorCode = vendorName.substring(0, 3).toUpperCase() + String(i + 1).padStart(2, '0');
    
    const vendor = await prisma.vendor.create({
      data: {
        tenantId,
        name: vendorName,
        legalName: `${vendorName} LLC`,
        code: `${tenantConfig.slug.substring(0, 3).toUpperCase()}-${vendorCode}`,
        taxId: faker.string.numeric(9),
        website: `https://www.${vendorName.toLowerCase().replace(/\s+/g, '')}.com`,
        tier: randomElement(['STRATEGIC', 'PREFERRED', 'STANDARD', 'STANDARD', 'STANDARD']),
        leadTimeDays: randomInt(7, 28),
        minOrderValue: randomFloat(100, 1000),
        paymentTerms: randomElement(['Net 30', 'Net 45', '2/10 Net 30', 'Net 60']),
        currency: 'USD',
        isActive: true,
        contacts: {
          create: [
            {
              name: faker.person.fullName(),
              title: 'Sales Representative',
              email: faker.internet.email(),
              phone: faker.phone.number(),
              role: 'SALES',
              isPrimary: true,
            },
            {
              name: faker.person.fullName(),
              title: 'Account Manager',
              email: faker.internet.email(),
              phone: faker.phone.number(),
              role: 'ACCOUNT',
              isPrimary: false,
            },
          ],
        },
        addresses: {
          create: [
            {
              type: 'WAREHOUSE',
              label: 'Main Warehouse',
              isPrimary: true,
              street1: faker.location.streetAddress(),
              city: faker.location.city(),
              state: faker.location.state({ abbreviated: true }),
              postalCode: faker.location.zipCode(),
              country: 'US',
              contactName: faker.person.fullName(),
              contactPhone: faker.phone.number(),
            },
          ],
        },
      },
    });
    
    vendors.push({ id: vendor.id, code: vendorCode });
  }
  stats.vendors = vendors.length;
  
  // Create locations (2 warehouses, 2 FBA, 1 store)
  console.log(`  Creating locations...`);
  const locations: { id: string; type: string }[] = [];
  
  const locationConfigs = [
    { name: 'Main Warehouse', type: 'WAREHOUSE' as const },
    { name: 'West Coast DC', type: 'WAREHOUSE' as const },
    { name: 'Amazon FBA - East', type: 'FBA' as const, channel: 'AMAZON' as const },
    { name: 'Amazon FBA - West', type: 'FBA' as const, channel: 'AMAZON' as const },
    { name: 'Flagship Store', type: 'STORE' as const },
  ];
  
  for (const loc of locationConfigs) {
    const location = await prisma.location.create({
      data: {
        tenantId,
        name: loc.name,
        type: loc.type,
        channel: loc.channel || null,
        address: {
          street1: faker.location.streetAddress(),
          city: faker.location.city(),
          state: faker.location.state({ abbreviated: true }),
          postalCode: faker.location.zipCode(),
          country: 'US',
        },
        isActive: true,
      },
    });
    locations.push({ id: location.id, type: loc.type });
  }
  stats.locations = locations.length;
  
  // Create products (75 per tenant)
  console.log(`  Creating products...`);
  const templates = PRODUCT_TEMPLATES[theme];
  const colors = COLORS[theme];
  const sizes = SIZES[theme];
  const products: { id: string; costPrice: number; msrp: number; categoryName: string }[] = [];
  
  let productIndex = 0;
  const skuPrefix = tenantConfig.slug.substring(0, 3).toUpperCase();
  
  // Create 5 variations of each template = 75 products
  for (const template of templates) {
    for (let v = 0; v < 5; v++) {
      productIndex++;
      const color = randomElement(colors);
      const size = sizes ? randomElement(sizes) : null;
      
      const variantSuffix = size ? `${color} / ${size}` : color;
      const productName = `${template.name} - ${variantSuffix}`;
      const sku = generateSKU(skuPrefix, productIndex);
      
      const costPrice = randomFloat(template.priceRange[0] * 0.4, template.priceRange[0] * 0.6);
      const msrp = randomFloat(template.priceRange[0], template.priceRange[1]);
      
      const product = await prisma.product.create({
        data: {
          tenantId,
          sku,
          name: productName,
          brand: tenantConfig.name.split(' ')[0],
          status: randomElement(['DRAFT', 'ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE']),
          upc: generateUPC(),
          asin: Math.random() > 0.3 ? generateASIN() : null,
          shortDescription: faker.commerce.productDescription().substring(0, 150),
          longDescription: faker.lorem.paragraphs(2),
          bulletPoints: [
            faker.commerce.productAdjective() + ' quality',
            `Available in ${color}`,
            faker.commerce.productAdjective() + ' design',
            'Easy to use',
            'Great value',
          ],
          costPrice,
          msrp,
          weightValue: randomFloat(0.1, 10),
          weightUnit: 'lb',
          lengthValue: randomFloat(2, 20),
          widthValue: randomFloat(2, 15),
          heightValue: randomFloat(1, 10),
          dimensionUnit: 'in',
          countryOfOrigin: randomElement(['CN', 'US', 'MX', 'VN']),
        },
      });
      
      // Add product images (2-4 per product)
      const imageCount = randomInt(2, 4);
      for (let img = 0; img < imageCount; img++) {
        await prisma.productImage.create({
          data: {
            productId: product.id,
            url: `https://picsum.photos/400/400?random=${productIndex * 10 + img}`,
            altText: `${productName} - Image ${img + 1}`,
            position: img,
            width: 400,
            height: 400,
          },
        });
      }
      
      // Add product attributes (deduplicate by name)
      const attrMap = new Map<string, { name: string; value: string; group: string }>();
      
      // Add variant attributes first
      attrMap.set('Color', { name: 'Color', value: color, group: 'Variant' });
      if (size) {
        attrMap.set('Size', { name: 'Size', value: size, group: 'Variant' });
      }
      
      // Add template-specific attributes (won't overwrite existing)
      for (const [name, value] of Object.entries(template.attributes)) {
        const attrName = name.charAt(0).toUpperCase() + name.slice(1);
        if (!attrMap.has(attrName)) {
          attrMap.set(attrName, { name: attrName, value: String(value), group: 'Specifications' });
        }
      }
      
      for (const attr of attrMap.values()) {
        await prisma.productAttribute.create({
          data: {
            productId: product.id,
            name: attr.name,
            value: attr.value,
            group: attr.group,
          },
        });
      }
      
      // Link to category
      const categoryId = categoryMap[template.category];
      if (categoryId) {
        await prisma.productCategory.create({
          data: {
            productId: product.id,
            categoryId,
            isPrimary: true,
          },
        });
      }
      
      products.push({ id: product.id, costPrice, msrp, categoryName: template.category });
    }
  }
  stats.products = products.length;
  
  // Create channel listings (mix of Amazon and Shopify)
  console.log(`  Creating channel listings...`);
  let listingCount = 0;
  
  for (const product of products) {
    const channels = randomElements(['AMAZON', 'SHOPIFY'] as const, randomInt(1, 2));
    
    for (const channel of channels) {
      const channelSku = channel === 'AMAZON' ? generateASIN() : `SHP-${randomInt(100000, 999999)}`;
      
      await prisma.channelListing.create({
        data: {
          tenantId,
          productId: product.id,
          channel,
          channelSku,
          channelProductId: `${channel.toLowerCase()}-${randomInt(10000, 99999)}`,
          price: product.msrp * randomFloat(0.95, 1.1),
          compareAtPrice: Math.random() > 0.5 ? product.msrp * 1.2 : null,
          fulfillmentChannel: channel === 'AMAZON' && Math.random() > 0.5 ? 'MARKETPLACE' : 'MERCHANT',
          status: randomElement(['ACTIVE', 'ACTIVE', 'ACTIVE', 'PENDING', 'DRAFT']),
          bufferStock: randomInt(0, 5),
          syncedAt: new Date(Date.now() - randomInt(0, 7 * 24 * 60 * 60 * 1000)),
        },
      });
      listingCount++;
    }
  }
  stats.channelListings = listingCount;
  
  // Create vendor-product links
  console.log(`  Linking products to vendors...`);
  let vpCount = 0;
  
  for (const product of products) {
    const productVendors = randomElements(vendors, randomInt(1, 3));
    
    for (let i = 0; i < productVendors.length; i++) {
      const vendor = productVendors[i];
      
      await prisma.vendorProduct.create({
        data: {
          vendorId: vendor.id,
          productId: product.id,
          vendorSku: `V-${vendor.code}-${randomInt(10000, 99999)}`,
          unitCost: product.costPrice * randomFloat(0.9, 1.1),
          currency: 'USD',
          minOrderQty: randomElement([1, 6, 12, 24]),
          orderMultiple: randomElement([1, 1, 1, 6]),
          leadTimeDays: randomInt(5, 21),
          isPreferred: i === 0,
          isActive: true,
        },
      });
      vpCount++;
    }
  }
  stats.vendorProducts = vpCount;
  
  // Create stock items
  console.log(`  Creating stock items...`);
  let stockCount = 0;
  
  const warehouses = locations.filter(l => l.type === 'WAREHOUSE' || l.type === 'FBA');
  
  for (const product of products) {
    const stockLocations = randomElements(warehouses, randomInt(2, 4));
    
    for (const location of stockLocations) {
      await prisma.stockItem.create({
        data: {
          tenantId,
          productId: product.id,
          locationId: location.id,
          quantityAvailable: randomInt(0, 500),
          quantityReserved: randomInt(0, 20),
          quantityInbound: Math.random() > 0.7 ? randomInt(50, 200) : 0,
          reorderPoint: randomInt(10, 50),
          reorderQty: randomInt(50, 200),
          binLocation: `${String.fromCharCode(65 + randomInt(0, 5))}-${randomInt(1, 20)}-${randomInt(1, 4)}`,
        },
      });
      stockCount++;
    }
  }
  stats.stockItems = stockCount;
  
  // Create orders (30 per tenant)
  console.log(`  Creating orders...`);
  
  for (let o = 0; o < 30; o++) {
    const channel = randomElement(['AMAZON', 'SHOPIFY', 'AMAZON', 'AMAZON'] as const);
    const lineCount = randomInt(1, 5);
    const orderProducts = randomElements(products, lineCount);
    
    const placedAt = new Date(Date.now() - randomInt(0, 30 * 24 * 60 * 60 * 1000));
    const status = randomElement(['PENDING', 'ALLOCATED', 'SHIPPED', 'DELIVERED', 'DELIVERED', 'DELIVERED']);
    
    const order = await prisma.order.create({
      data: {
        tenantId,
        channel,
        channelOrderId: generateOrderId(channel),
        status,
        customer: {
          name: faker.person.fullName(),
          email: faker.internet.email(),
          phone: faker.phone.number(),
        },
        shippingAddress: {
          name: faker.person.fullName(),
          street1: faker.location.streetAddress(),
          city: faker.location.city(),
          state: faker.location.state({ abbreviated: true }),
          postalCode: faker.location.zipCode(),
          country: 'US',
        },
        totals: {
          subtotal: 0, // Will calculate
          shipping: randomFloat(0, 15),
          tax: 0,
          total: 0,
        },
        placedAt,
        shippedAt: ['SHIPPED', 'DELIVERED'].includes(status) 
          ? new Date(placedAt.getTime() + randomInt(1, 3) * 24 * 60 * 60 * 1000)
          : null,
        deliveredAt: status === 'DELIVERED'
          ? new Date(placedAt.getTime() + randomInt(3, 7) * 24 * 60 * 60 * 1000)
          : null,
      },
    });
    
    // Create order lines
    let subtotal = 0;
    for (const product of orderProducts) {
      const qty = randomInt(1, 3);
      const unitPrice = product.msrp * randomFloat(0.9, 1.05);
      subtotal += qty * unitPrice;
      
      await prisma.orderLine.create({
        data: {
          orderId: order.id,
          productId: product.id,
          channelSku: generateASIN(),
          quantity: qty,
          unitPrice,
          allocatedFromId: ['ALLOCATED', 'SHIPPED', 'DELIVERED'].includes(status)
            ? randomElement(warehouses).id
            : null,
        },
      });
    }
    
    // Update totals
    const tax = subtotal * 0.08;
    await prisma.order.update({
      where: { id: order.id },
      data: {
        totals: {
          subtotal,
          shipping: randomFloat(0, 15),
          tax,
          total: subtotal + tax + randomFloat(0, 15),
        },
      },
    });
  }
  stats.orders = 30;
  
  // Create purchase orders (8 per tenant)
  console.log(`  Creating purchase orders...`);
  
  const warehouseLocations = locations.filter(l => l.type === 'WAREHOUSE');
  
  for (let po = 0; po < 8; po++) {
    const vendor = randomElement(vendors);
    const destination = randomElement(warehouseLocations);
    const lineCount = randomInt(3, 8);
    const poProducts = randomElements(products, lineCount);
    
    const status = randomElement(['DRAFT', 'SUBMITTED', 'CONFIRMED', 'SHIPPED', 'RECEIVED', 'RECEIVED']);
    const orderedAt = status !== 'DRAFT' 
      ? new Date(Date.now() - randomInt(5, 60) * 24 * 60 * 60 * 1000)
      : null;
    
    const purchaseOrder = await prisma.purchaseOrder.create({
      data: {
        tenantId,
        poNumber: generatePONumber(vendor.code, po + 1),
        vendorId: vendor.id,
        destinationId: destination.id,
        status,
        notes: Math.random() > 0.5 ? faker.lorem.sentence() : null,
        orderedAt,
        expectedAt: orderedAt 
          ? new Date(orderedAt.getTime() + randomInt(14, 30) * 24 * 60 * 60 * 1000)
          : null,
        shippedAt: ['SHIPPED', 'PARTIAL', 'RECEIVED'].includes(status)
          ? new Date((orderedAt?.getTime() || Date.now()) + randomInt(3, 10) * 24 * 60 * 60 * 1000)
          : null,
        receivedAt: status === 'RECEIVED'
          ? new Date((orderedAt?.getTime() || Date.now()) + randomInt(14, 28) * 24 * 60 * 60 * 1000)
          : null,
        carrier: ['SHIPPED', 'PARTIAL', 'RECEIVED'].includes(status)
          ? randomElement(['UPS', 'FedEx', 'USPS', 'DHL'])
          : null,
        trackingNumber: ['SHIPPED', 'PARTIAL', 'RECEIVED'].includes(status)
          ? `1Z${faker.string.alphanumeric(16).toUpperCase()}`
          : null,
      },
    });
    
    // Create PO lines
    let subtotal = 0;
    for (const product of poProducts) {
      const qty = randomInt(24, 200);
      const unitCost = product.costPrice * randomFloat(0.95, 1.05);
      subtotal += qty * unitCost;
      
      await prisma.pOLine.create({
        data: {
          poId: purchaseOrder.id,
          productId: product.id,
          quantityOrdered: qty,
          quantityReceived: status === 'RECEIVED' ? qty : 
                           status === 'PARTIAL' ? Math.floor(qty * randomFloat(0.3, 0.7)) : 0,
          unitCost,
        },
      });
    }
    
    // Update totals
    const shipping = randomFloat(50, 300);
    await prisma.purchaseOrder.update({
      where: { id: purchaseOrder.id },
      data: {
        subtotal,
        shipping,
        tax: 0,
        total: subtotal + shipping,
      },
    });
  }
  stats.purchaseOrders = 8;
  
  return { tenantId, stats };
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  console.log('🌱 Copio Seed Script');
  console.log('====================\n');
  
  // Check for existing seed data
  const existingSlugs = await checkExistingSeedData();
  
  if (existingSlugs.length > 0) {
    console.log(`Found existing seed tenants: ${existingSlugs.join(', ')}`);
    console.log('Existing data will be cleaned and re-seeded.\n');
  }
  
  const results: { tenant: string; stats: Record<string, number> }[] = [];
  
  for (const tenantConfig of SEED_TENANTS) {
    try {
      const { stats } = await seedTenant(tenantConfig);
      results.push({ tenant: tenantConfig.name, stats });
    } catch (error) {
      console.error(`\n❌ Error seeding ${tenantConfig.name}:`, error);
      throw error;
    }
  }
  
  // Print summary
  console.log('\n\n✅ Seed Complete!');
  console.log('==================\n');
  
  console.log('Summary by Tenant:\n');
  for (const result of results) {
    console.log(`📦 ${result.tenant}`);
    for (const [key, value] of Object.entries(result.stats)) {
      console.log(`   ${key}: ${value}`);
    }
    console.log();
  }
  
  // Print totals
  const totals: Record<string, number> = {};
  for (const result of results) {
    for (const [key, value] of Object.entries(result.stats)) {
      totals[key] = (totals[key] || 0) + value;
    }
  }
  
  console.log('📊 Totals:');
  for (const [key, value] of Object.entries(totals)) {
    console.log(`   ${key}: ${value}`);
  }
  
  console.log('\n🔑 Test credentials:');
  console.log('   Email: <firstname>.<lastname>@<tenant-slug>.test');
  console.log('   Password: password123');
}

main()
  .catch((error) => {
    console.error('Seed failed:', error);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
