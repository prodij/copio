import { prisma } from '@copio/core';

const STATUSES = ['DRAFT', 'SUBMITTED', 'CONFIRMED', 'SHIPPED', 'PARTIAL', 'RECEIVED', 'CANCELLED'];

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomDate(daysBack: number): Date {
  const date = new Date();
  date.setDate(date.getDate() - randomInt(1, daysBack));
  return date;
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

async function generatePONumber(): Promise<string> {
  const year = new Date().getFullYear();
  const prefix = `PO-${year}-`;
  
  const lastPO = await prisma.purchaseOrder.findFirst({
    where: { poNumber: { startsWith: prefix } },
    orderBy: { poNumber: 'desc' },
  });
  
  let sequence = 1;
  if (lastPO) {
    const lastSeq = parseInt(lastPO.poNumber.replace(prefix, ''), 10);
    if (!isNaN(lastSeq)) sequence = lastSeq + 1;
  }
  
  return `${prefix}${String(sequence).padStart(4, '0')}`;
}

async function main() {
  console.log('Fetching vendors and locations...');
  
  const vendors = await prisma.vendor.findMany({ select: { id: true, name: true, leadTimeDays: true } });
  const locations = await prisma.location.findMany({ where: { type: { in: ['WAREHOUSE', 'FBA'] } }, select: { id: true, name: true } });
  
  if (vendors.length === 0) {
    console.error('No vendors found!');
    return;
  }
  
  if (locations.length === 0) {
    console.error('No locations found!');
    return;
  }
  
  console.log(`Found ${vendors.length} vendors and ${locations.length} locations`);
  
  let totalCreated = 0;
  
  for (const vendor of vendors) {
    const poCount = randomInt(5, 25);
    console.log(`Creating ${poCount} POs for ${vendor.name}...`);
    
    for (let i = 0; i < poCount; i++) {
      const poNumber = await generatePONumber();
      const destination = locations[randomInt(0, locations.length - 1)];
      const status = STATUSES[randomInt(0, STATUSES.length - 1)];
      
      // Generate realistic dates based on status
      let orderedAt: Date | null = null;
      let expectedAt: Date | null = null;
      let shippedAt: Date | null = null;
      let receivedAt: Date | null = null;
      
      const isActive = !['DRAFT'].includes(status);
      const isShipped = ['SHIPPED', 'PARTIAL', 'RECEIVED'].includes(status);
      const isReceived = ['RECEIVED'].includes(status);
      
      if (isActive) {
        orderedAt = randomDate(180); // Within last 6 months
        expectedAt = addDays(orderedAt, vendor.leadTimeDays + randomInt(-5, 10));
      }
      
      if (isShipped) {
        shippedAt = addDays(orderedAt!, randomInt(1, 7));
      }
      
      if (isReceived) {
        receivedAt = addDays(shippedAt!, randomInt(1, 5));
      }
      
      // Generate subtotal and total
      const subtotal = randomInt(500, 25000);
      const tax = Math.round(subtotal * 0.08); // 8% tax
      const shipping = randomInt(50, 500);
      const total = subtotal + tax + shipping;
      
      await prisma.purchaseOrder.create({
        data: {
          poNumber,
          vendorId: vendor.id,
          destinationId: destination.id,
          status: status as any,
          subtotal,
          tax,
          shipping,
          total,
          orderedAt,
          expectedAt,
          shippedAt,
          receivedAt,
          notes: randomInt(0, 3) === 0 ? `Auto-generated PO for testing` : null,
        },
      });
      
      totalCreated++;
    }
  }
  
  console.log(`\nCreated ${totalCreated} purchase orders across ${vendors.length} vendors.`);
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect());
