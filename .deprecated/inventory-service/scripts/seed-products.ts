import { prisma } from '@copio/core';

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

function randomElements<T>(arr: T[], min: number, max: number): T[] {
  const count = randomInt(min, max);
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count);
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

// ============================================================================
// DATA TEMPLATES
// ============================================================================

const CATEGORIES = [
  'Electronics', 'Home & Kitchen', 'Sports & Outdoors', 'Health & Beauty',
  'Toys & Games', 'Automotive', 'Pet Supplies', 'Office Products',
  'Garden & Outdoor', 'Tools & Home Improvement'
];

const BRANDS = [
  'TechPro', 'HomeEssentials', 'SportMax', 'VitaLife', 'PlayZone',
  'AutoCare', 'PetPal', 'OfficePro', 'GreenThumb', 'BuildRight',
  'NexGen', 'PureComfort', 'ActiveGear', 'SmartHome', 'EcoFriendly'
];

const PRODUCT_TEMPLATES = [
  // Electronics
  { name: 'Wireless Bluetooth Earbuds', category: 'Electronics', priceRange: [29, 149] },
  { name: 'USB-C Charging Cable 6ft', category: 'Electronics', priceRange: [8, 24] },
  { name: 'Portable Power Bank 10000mAh', category: 'Electronics', priceRange: [19, 49] },
  { name: 'Smart LED Light Bulb', category: 'Electronics', priceRange: [12, 35] },
  { name: 'Wireless Phone Charger Pad', category: 'Electronics', priceRange: [15, 45] },
  { name: 'Laptop Stand Adjustable', category: 'Electronics', priceRange: [25, 65] },
  { name: 'Webcam 1080p HD', category: 'Electronics', priceRange: [35, 89] },
  { name: 'Bluetooth Speaker Portable', category: 'Electronics', priceRange: [25, 79] },
  { name: 'Smart Plug WiFi Outlet', category: 'Electronics', priceRange: [12, 29] },
  { name: 'Ring Light with Tripod', category: 'Electronics', priceRange: [29, 69] },
  
  // Home & Kitchen
  { name: 'Stainless Steel Water Bottle', category: 'Home & Kitchen', priceRange: [15, 35] },
  { name: 'Silicone Baking Mat Set', category: 'Home & Kitchen', priceRange: [12, 28] },
  { name: 'Glass Food Storage Containers', category: 'Home & Kitchen', priceRange: [24, 48] },
  { name: 'Digital Kitchen Scale', category: 'Home & Kitchen', priceRange: [15, 35] },
  { name: 'Bamboo Cutting Board Set', category: 'Home & Kitchen', priceRange: [18, 42] },
  { name: 'French Press Coffee Maker', category: 'Home & Kitchen', priceRange: [22, 55] },
  { name: 'Dish Drying Rack', category: 'Home & Kitchen', priceRange: [25, 65] },
  { name: 'Reusable Produce Bags 12pk', category: 'Home & Kitchen', priceRange: [12, 24] },
  { name: 'Electric Kettle 1.7L', category: 'Home & Kitchen', priceRange: [28, 65] },
  { name: 'Cast Iron Skillet 12"', category: 'Home & Kitchen', priceRange: [35, 85] },
  
  // Sports & Outdoors
  { name: 'Yoga Mat Non-Slip', category: 'Sports & Outdoors', priceRange: [20, 55] },
  { name: 'Resistance Bands Set', category: 'Sports & Outdoors', priceRange: [15, 35] },
  { name: 'Foam Roller for Muscle Recovery', category: 'Sports & Outdoors', priceRange: [18, 42] },
  { name: 'Jump Rope Speed Training', category: 'Sports & Outdoors', priceRange: [12, 28] },
  { name: 'Camping Hammock Double', category: 'Sports & Outdoors', priceRange: [35, 75] },
  { name: 'Hiking Daypack 30L', category: 'Sports & Outdoors', priceRange: [45, 95] },
  { name: 'Bike Phone Mount', category: 'Sports & Outdoors', priceRange: [15, 35] },
  { name: 'Cooling Towel 3-Pack', category: 'Sports & Outdoors', priceRange: [12, 24] },
  { name: 'LED Headlamp Rechargeable', category: 'Sports & Outdoors', priceRange: [18, 45] },
  { name: 'Insulated Water Bottle 32oz', category: 'Sports & Outdoors', priceRange: [25, 55] },
  
  // Health & Beauty  
  { name: 'Electric Toothbrush Rechargeable', category: 'Health & Beauty', priceRange: [35, 89] },
  { name: 'Hair Dryer Professional', category: 'Health & Beauty', priceRange: [45, 125] },
  { name: 'Facial Cleansing Brush', category: 'Health & Beauty', priceRange: [25, 65] },
  { name: 'Massage Gun Deep Tissue', category: 'Health & Beauty', priceRange: [65, 185] },
  { name: 'Digital Body Weight Scale', category: 'Health & Beauty', priceRange: [22, 55] },
  { name: 'Makeup Brush Set 12pc', category: 'Health & Beauty', priceRange: [18, 42] },
  { name: 'Aromatherapy Diffuser', category: 'Health & Beauty', priceRange: [25, 55] },
  { name: 'Heated Eye Mask USB', category: 'Health & Beauty', priceRange: [22, 45] },
  { name: 'Electric Nail File Kit', category: 'Health & Beauty', priceRange: [28, 65] },
  { name: 'Posture Corrector Adjustable', category: 'Health & Beauty', priceRange: [18, 38] },
  
  // Pet Supplies
  { name: 'Dog Leash Retractable 16ft', category: 'Pet Supplies', priceRange: [18, 42] },
  { name: 'Cat Scratching Post Tower', category: 'Pet Supplies', priceRange: [35, 95] },
  { name: 'Pet Water Fountain 2L', category: 'Pet Supplies', priceRange: [28, 55] },
  { name: 'Dog Bed Orthopedic Large', category: 'Pet Supplies', priceRange: [45, 115] },
  { name: 'Cat Litter Mat XL', category: 'Pet Supplies', priceRange: [18, 38] },
  { name: 'Pet Grooming Brush Self-Cleaning', category: 'Pet Supplies', priceRange: [15, 32] },
  { name: 'Dog Training Treats Bag', category: 'Pet Supplies', priceRange: [12, 25] },
  { name: 'Interactive Cat Toy Automatic', category: 'Pet Supplies', priceRange: [22, 48] },
  { name: 'Pet Carrier Airline Approved', category: 'Pet Supplies', priceRange: [35, 85] },
  { name: 'Dog Poop Bag Dispenser', category: 'Pet Supplies', priceRange: [8, 18] },
  
  // Office Products
  { name: 'Desk Organizer Wooden', category: 'Office Products', priceRange: [22, 48] },
  { name: 'Monitor Stand with Drawer', category: 'Office Products', priceRange: [35, 75] },
  { name: 'Ergonomic Mouse Pad Wrist Rest', category: 'Office Products', priceRange: [15, 32] },
  { name: 'Desk Lamp LED Adjustable', category: 'Office Products', priceRange: [28, 65] },
  { name: 'Cable Management Box', category: 'Office Products', priceRange: [18, 38] },
  { name: 'Whiteboard Magnetic 24x36', category: 'Office Products', priceRange: [35, 75] },
  { name: 'Document Scanner Portable', category: 'Office Products', priceRange: [85, 195] },
  { name: 'Noise Canceling Headphones', category: 'Office Products', priceRange: [55, 175] },
  { name: 'Standing Desk Converter', category: 'Office Products', priceRange: [125, 295] },
  { name: 'Paper Shredder 8-Sheet', category: 'Office Products', priceRange: [45, 95] },
];

const COLORS = ['Black', 'White', 'Gray', 'Blue', 'Red', 'Green', 'Pink', 'Navy', 'Silver'];
const SIZES = ['Small', 'Medium', 'Large', 'XL', 'One Size'];

const CHANNELS = ['AMAZON', 'SHOPIFY', 'WALMART', 'EBAY'] as const;
const FULFILLMENT_CHANNELS = ['MERCHANT', 'MARKETPLACE'] as const;
const LISTING_STATUSES = ['DRAFT', 'PENDING', 'ACTIVE', 'INACTIVE', 'SUPPRESSED'] as const;

// ============================================================================
// SEED FUNCTIONS
// ============================================================================

async function seedProducts(count: number) {
  console.log(`\nCreating ${count} products...`);
  
  const vendors = await prisma.vendor.findMany({ select: { id: true } });
  const locations = await prisma.location.findMany({ select: { id: true, type: true } });
  
  if (vendors.length === 0) {
    console.error('No vendors found! Run vendor seed first.');
    return;
  }
  
  const products: any[] = [];
  
  for (let i = 1; i <= count; i++) {
    const template = randomElement(PRODUCT_TEMPLATES);
    const brand = randomElement(BRANDS);
    const color = randomElement(COLORS);
    const hasSize = Math.random() > 0.6;
    const size = hasSize ? randomElement(SIZES) : null;
    
    const variantSuffix = `${color}${size ? ` ${size}` : ''}`;
    const productName = `${brand} ${template.name} - ${variantSuffix}`;
    const sku = generateSKU(brand.substring(0, 3).toUpperCase(), i);
    
    const costPrice = randomFloat(template.priceRange[0] * 0.4, template.priceRange[0] * 0.6);
    const msrp = randomFloat(template.priceRange[0], template.priceRange[1]);
    
    const weight = randomFloat(0.1, 15, 2);
    const length = randomFloat(2, 24, 1);
    const width = randomFloat(2, 18, 1);
    const height = randomFloat(1, 12, 1);
    
    products.push({
      sku,
      name: productName,
      brand,
      status: randomElement(['DRAFT', 'ACTIVE', 'ACTIVE', 'ACTIVE', 'ARCHIVED']), // 60% active
      upc: Math.random() > 0.3 ? generateUPC() : null,
      asin: Math.random() > 0.4 ? generateASIN() : null,
      shortDescription: `High-quality ${template.name.toLowerCase()} from ${brand}. ${color} color${size ? `, ${size} size` : ''}.`,
      longDescription: `Introducing the ${brand} ${template.name}. This premium product features exceptional quality and design. Available in ${color}${size ? ` (${size})` : ''}. Perfect for everyday use with durable construction and modern aesthetics. Backed by our satisfaction guarantee.`,
      bulletPoints: [
        `Premium ${template.category.toLowerCase()} product`,
        `${color} color option`,
        `High-quality materials`,
        `Easy to use design`,
        `Great value for money`,
      ],
      costPrice,
      msrp,
      weightValue: weight,
      weightUnit: 'lb',
      lengthValue: length,
      widthValue: width,
      heightValue: height,
      dimensionUnit: 'in',
      pkgWeightValue: weight + randomFloat(0.1, 0.5),
      pkgLengthValue: length + randomFloat(1, 3),
      pkgWidthValue: width + randomFloat(1, 2),
      pkgHeightValue: height + randomFloat(0.5, 2),
      countryOfOrigin: randomElement(['CN', 'US', 'MX', 'VN', 'TW']),
      _category: template.category,
      _brand: brand,
    });
    
    if (i % 50 === 0) {
      console.log(`  Prepared ${i}/${count} products...`);
    }
  }
  
  // Batch insert products
  console.log('  Inserting products into database...');
  const createdProducts: { id: string; sku: string; costPrice: any; msrp: any; _category: string }[] = [];
  
  for (const p of products) {
    const { _category, _brand, ...productData } = p;
    const created = await prisma.product.create({
      data: productData,
      select: { id: true, sku: true, costPrice: true, msrp: true },
    });
    createdProducts.push({ ...created, _category });
  }
  
  console.log(`  Created ${createdProducts.length} products`);
  
  // Create channel listings
  console.log('\nCreating channel listings...');
  let listingCount = 0;
  
  for (const product of createdProducts) {
    // Each product gets 1-4 channel listings
    const channels = randomElements([...CHANNELS], 1, 4);
    
    for (const channel of channels) {
      const basePrice = product.msrp ? Number(product.msrp) : 29.99;
      const channelPrice = basePrice * randomFloat(0.9, 1.15); // ±15% variance
      
      let channelSku: string;
      switch (channel) {
        case 'AMAZON':
          channelSku = generateASIN();
          break;
        case 'SHOPIFY':
          channelSku = `SHP-${product.sku}`;
          break;
        case 'WALMART':
          channelSku = `WMT${randomInt(100000000, 999999999)}`;
          break;
        case 'EBAY':
          channelSku = `${randomInt(100000000000, 999999999999)}`;
          break;
      }
      
      await prisma.channelListing.create({
        data: {
          productId: product.id,
          channel,
          channelSku,
          channelProductId: `${channel.toLowerCase()}-${randomInt(10000, 99999)}`,
          price: channelPrice,
          compareAtPrice: Math.random() > 0.5 ? channelPrice * 1.2 : null,
          fulfillmentChannel: channel === 'AMAZON' && Math.random() > 0.4 ? 'MARKETPLACE' : 'MERCHANT',
          status: randomElement(['DRAFT', 'PENDING', 'ACTIVE', 'ACTIVE', 'ACTIVE', 'INACTIVE']),
          bufferStock: randomInt(0, 5),
          maxQuantity: Math.random() > 0.7 ? randomInt(50, 500) : null,
          handlingDays: randomInt(1, 3),
          listingUrl: channel === 'AMAZON' 
            ? `https://amazon.com/dp/${channelSku}`
            : channel === 'EBAY'
            ? `https://ebay.com/itm/${channelSku}`
            : null,
          syncedAt: Math.random() > 0.3 ? new Date(Date.now() - randomInt(0, 7 * 24 * 60 * 60 * 1000)) : null,
        },
      });
      listingCount++;
    }
  }
  
  console.log(`  Created ${listingCount} channel listings`);
  
  // Create vendor-product links
  console.log('\nLinking products to vendors...');
  let vpCount = 0;
  
  for (const product of createdProducts) {
    // Each product has 1-3 vendor sources
    const productVendors = randomElements(vendors, 1, Math.min(3, vendors.length));
    
    for (let i = 0; i < productVendors.length; i++) {
      const vendor = productVendors[i];
      const baseCost = product.costPrice ? Number(product.costPrice) : 10;
      
      await prisma.vendorProduct.create({
        data: {
          vendorId: vendor.id,
          productId: product.id,
          vendorSku: `V${vendor.id.substring(0, 4).toUpperCase()}-${product.sku}`,
          unitCost: baseCost * randomFloat(0.95, 1.1),
          currency: 'USD',
          minOrderQty: randomElement([1, 6, 12, 24, 48]),
          orderMultiple: randomElement([1, 1, 1, 6, 12]),
          casePackQty: Math.random() > 0.5 ? randomElement([6, 12, 24, 48]) : null,
          leadTimeDays: randomInt(3, 21),
          isPreferred: i === 0, // First vendor is preferred
          isActive: true,
        },
      });
      vpCount++;
    }
  }
  
  console.log(`  Created ${vpCount} vendor-product links`);
  
  // Create stock items at locations
  console.log('\nCreating stock items at locations...');
  let stockCount = 0;
  
  const warehouses = locations.filter(l => l.type === 'WAREHOUSE' || l.type === 'FBA');
  
  for (const product of createdProducts) {
    // Each product has stock at 1-3 locations
    const stockLocations = randomElements(warehouses, 1, Math.min(3, warehouses.length));
    
    for (const location of stockLocations) {
      await prisma.stockItem.create({
        data: {
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
  
  console.log(`  Created ${stockCount} stock items`);
  
  return { products: createdProducts.length, listings: listingCount, vendorProducts: vpCount, stockItems: stockCount };
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  console.log('🌱 Starting product seed...\n');
  
  // Check for existing products
  const existingCount = await prisma.product.count();
  if (existingCount > 0) {
    console.log(`Found ${existingCount} existing products.`);
    const readline = await import('readline');
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    
    const answer = await new Promise<string>((resolve) => {
      rl.question('Delete existing products and start fresh? (y/N): ', resolve);
    });
    rl.close();
    
    if (answer.toLowerCase() === 'y') {
      console.log('Deleting existing data...');
      await prisma.stockMovement.deleteMany({});
      await prisma.stockItem.deleteMany({});
      await prisma.channelListing.deleteMany({});
      await prisma.vendorProduct.deleteMany({});
      await prisma.pOLine.deleteMany({});
      await prisma.orderLine.deleteMany({});
      await prisma.productImage.deleteMany({});
      await prisma.productAttribute.deleteMany({});
      await prisma.product.deleteMany({});
      console.log('Deleted existing products and related data.\n');
    } else {
      console.log('Keeping existing data, adding new products.\n');
    }
  }
  
  const result = await seedProducts(250);
  
  console.log('\n✅ Seed complete!');
  console.log(`   Products: ${result?.products}`);
  console.log(`   Channel Listings: ${result?.listings}`);
  console.log(`   Vendor Products: ${result?.vendorProducts}`);
  console.log(`   Stock Items: ${result?.stockItems}`);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
