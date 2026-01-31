/**
 * Verify seed data
 */

import { prisma } from '@copio/core';

async function verify() {
  const tenants = await prisma.tenants.findMany({
    select: { name: true, slug: true }
  });
  
  console.log('\n✅ Verification Results');
  console.log('========================\n');
  console.log('Tenants:', tenants.length);
  for (const t of tenants) {
    console.log('  -', t.name, '(' + t.slug + ')');
  }
  
  const products = await prisma.product.count();
  const vendors = await prisma.vendor.count();
  const orders = await prisma.order.count();
  const purchaseOrders = await prisma.purchaseOrder.count();
  const stockItems = await prisma.stockItem.count();
  const channelListings = await prisma.channelListing.count();
  const productImages = await prisma.productImage.count();
  const productAttributes = await prisma.productAttribute.count();
  
  console.log('\nData Totals:');
  console.log('  Products:', products);
  console.log('  Product Images:', productImages);
  console.log('  Product Attributes:', productAttributes);
  console.log('  Vendors:', vendors);
  console.log('  Orders:', orders);
  console.log('  Purchase Orders:', purchaseOrders);
  console.log('  Stock Items:', stockItems);
  console.log('  Channel Listings:', channelListings);
  
  // Sample product with all relations
  const sample = await prisma.product.findFirst({
    include: {
      images: true,
      attributes: true,
      listings: true,
    }
  });
  
  console.log('\n📦 Sample Product:');
  console.log('  Name:', sample?.name);
  console.log('  SKU:', sample?.sku);
  console.log('  Price: $' + sample?.msrp);
  console.log('  Images:', sample?.images.length);
  if (sample?.images[0]) {
    console.log('    →', sample.images[0].url);
  }
  console.log('  Attributes:', sample?.attributes.map(a => a.name + ': ' + a.value).join(', '));
  console.log('  Listings:', sample?.listings.map(l => l.channel).join(', '));
  
  await prisma.$disconnect();
}

verify().catch(console.error);
