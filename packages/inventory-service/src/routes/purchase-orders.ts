import { Router, Request, Response } from 'express';
import { prisma } from '@copio/core';

export const purchaseOrdersRouter = Router();

// =============================================================================
// HELPER: Generate PO Number
// =============================================================================

async function generatePONumber(): Promise<string> {
  const year = new Date().getFullYear();
  const prefix = `PO-${year}-`;
  
  // Find the highest PO number for this year
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

// =============================================================================
// HELPER: Calculate PO Totals
// =============================================================================

function calculateTotals(lines: Array<{ quantityOrdered: number; unitCost: number }>) {
  const subtotal = lines.reduce((sum, line) => sum + (line.quantityOrdered * line.unitCost), 0);
  return { subtotal, total: subtotal }; // Tax/shipping can be added later
}

// =============================================================================
// LIST PURCHASE ORDERS
// =============================================================================

purchaseOrdersRouter.get('/', async (req: Request, res: Response) => {
  const { status, vendorId, destinationId, limit = '50', offset = '0' } = req.query;
  
  const where: Record<string, unknown> = {};
  if (status) where.status = status;
  if (vendorId) where.vendorId = vendorId;
  if (destinationId) where.destinationId = destinationId;

  const [purchaseOrders, total] = await Promise.all([
    prisma.purchaseOrder.findMany({
      where,
      include: {
        vendor: { select: { id: true, name: true, code: true } },
        destination: { select: { id: true, name: true, type: true } },
        _count: { select: { lines: true } },
      },
      orderBy: { createdAt: 'desc' },
      take: parseInt(limit as string),
      skip: parseInt(offset as string),
    }),
    prisma.purchaseOrder.count({ where }),
  ]);

  res.json({ purchaseOrders, total });
});

// =============================================================================
// GET SINGLE PURCHASE ORDER
// =============================================================================

purchaseOrdersRouter.get('/:id', async (req: Request, res: Response) => {
  const po = await prisma.purchaseOrder.findUnique({
    where: { id: req.params.id },
    include: {
      vendor: { select: { id: true, name: true, code: true, contact: true, leadTimeDays: true } },
      destination: { select: { id: true, name: true, type: true, address: true } },
      lines: {
        include: {
          product: {
            select: {
              id: true,
              sku: true,
              name: true,
              images: { take: 1, orderBy: { position: 'asc' } },
            },
          },
        },
        orderBy: { product: { sku: 'asc' } },
      },
    },
  });

  if (!po) {
    return res.status(404).json({ error: 'Purchase order not found' });
  }

  res.json(po);
});

// =============================================================================
// CREATE PURCHASE ORDER
// =============================================================================

purchaseOrdersRouter.post('/', async (req: Request, res: Response) => {
  const { vendorId, destinationId, notes, lines } = req.body;

  if (!vendorId || !destinationId) {
    return res.status(400).json({ error: 'vendorId and destinationId are required' });
  }

  // Verify vendor and destination exist
  const [vendor, destination] = await Promise.all([
    prisma.vendor.findUnique({ where: { id: vendorId } }),
    prisma.location.findUnique({ where: { id: destinationId } }),
  ]);

  if (!vendor) return res.status(400).json({ error: 'Vendor not found' });
  if (!destination) return res.status(400).json({ error: 'Destination location not found' });

  const poNumber = await generatePONumber();
  
  // Calculate expected arrival based on vendor lead time
  const expectedAt = new Date();
  expectedAt.setDate(expectedAt.getDate() + vendor.leadTimeDays);

  // If lines provided, validate and get costs from vendor products
  let lineData: Array<{ productId: string; quantityOrdered: number; unitCost: number; notes?: string }> = [];
  
  if (lines && lines.length > 0) {
    for (const line of lines) {
      if (!line.productId || !line.quantityOrdered) {
        return res.status(400).json({ error: 'Each line requires productId and quantityOrdered' });
      }
      
      // Get vendor product for pricing
      const vendorProduct = await prisma.vendorProduct.findFirst({
        where: { vendorId, productId: line.productId },
      });
      
      // Use provided unitCost, or vendor product cost, or 0
      const unitCost = line.unitCost ?? (vendorProduct ? Number(vendorProduct.unitCost) : 0);
      
      lineData.push({
        productId: line.productId,
        quantityOrdered: line.quantityOrdered,
        unitCost,
        notes: line.notes,
      });
    }
  }

  const totals = calculateTotals(lineData);

  const po = await prisma.purchaseOrder.create({
    data: {
      poNumber,
      vendorId,
      destinationId,
      notes,
      expectedAt,
      subtotal: totals.subtotal,
      total: totals.total,
      lines: lineData.length > 0 ? {
        create: lineData,
      } : undefined,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
      destination: { select: { id: true, name: true, type: true } },
      lines: {
        include: {
          product: { select: { id: true, sku: true, name: true } },
        },
      },
    },
  });

  res.status(201).json(po);
});

// =============================================================================
// UPDATE PURCHASE ORDER
// =============================================================================

purchaseOrdersRouter.patch('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;
  const { notes, status, expectedAt, tax, shipping } = req.body;

  const existing = await prisma.purchaseOrder.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Purchase order not found' });
  }

  // Only allow certain updates based on status
  if (existing.status === 'RECEIVED' || existing.status === 'CANCELLED') {
    return res.status(400).json({ error: 'Cannot modify a completed or cancelled PO' });
  }

  // Recalculate total if tax/shipping changed
  let total = existing.total ? Number(existing.total) : 0;
  if (tax !== undefined || shipping !== undefined) {
    const subtotal = existing.subtotal ? Number(existing.subtotal) : 0;
    const newTax = tax ?? (existing.tax ? Number(existing.tax) : 0);
    const newShipping = shipping ?? (existing.shipping ? Number(existing.shipping) : 0);
    total = subtotal + newTax + newShipping;
  }

  const po = await prisma.purchaseOrder.update({
    where: { id },
    data: {
      notes,
      status,
      expectedAt: expectedAt ? new Date(expectedAt) : undefined,
      tax,
      shipping,
      total,
      orderedAt: status === 'SUBMITTED' && !existing.orderedAt ? new Date() : undefined,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
      destination: { select: { id: true, name: true, type: true } },
      _count: { select: { lines: true } },
    },
  });

  res.json(po);
});

// =============================================================================
// ADD LINE TO PURCHASE ORDER
// =============================================================================

purchaseOrdersRouter.post('/:id/lines', async (req: Request, res: Response) => {
  const { id } = req.params;
  const { productId, quantityOrdered, unitCost, notes } = req.body;

  if (!productId || !quantityOrdered) {
    return res.status(400).json({ error: 'productId and quantityOrdered are required' });
  }

  const po = await prisma.purchaseOrder.findUnique({ where: { id } });
  if (!po) {
    return res.status(404).json({ error: 'Purchase order not found' });
  }

  if (po.status !== 'DRAFT') {
    return res.status(400).json({ error: 'Can only add lines to draft POs' });
  }

  // Check if line already exists for this product
  const existingLine = await prisma.pOLine.findFirst({
    where: { poId: id, productId },
  });
  if (existingLine) {
    return res.status(409).json({ error: 'Line for this product already exists. Update it instead.' });
  }

  // Get unit cost from vendor product if not provided
  let cost = unitCost;
  if (cost === undefined) {
    const vendorProduct = await prisma.vendorProduct.findFirst({
      where: { vendorId: po.vendorId, productId },
    });
    cost = vendorProduct ? Number(vendorProduct.unitCost) : 0;
  }

  const line = await prisma.pOLine.create({
    data: {
      poId: id,
      productId,
      quantityOrdered,
      unitCost: cost,
      notes,
    },
    include: {
      product: { select: { id: true, sku: true, name: true } },
    },
  });

  // Update PO totals
  const allLines = await prisma.pOLine.findMany({ where: { poId: id } });
  const totals = calculateTotals(allLines.map(l => ({
    quantityOrdered: l.quantityOrdered,
    unitCost: Number(l.unitCost),
  })));

  await prisma.purchaseOrder.update({
    where: { id },
    data: { subtotal: totals.subtotal, total: totals.total + Number(po.tax || 0) + Number(po.shipping || 0) },
  });

  res.status(201).json(line);
});

// =============================================================================
// UPDATE LINE
// =============================================================================

purchaseOrdersRouter.patch('/:id/lines/:lineId', async (req: Request, res: Response) => {
  const { id, lineId } = req.params;
  const { quantityOrdered, unitCost, notes } = req.body;

  const po = await prisma.purchaseOrder.findUnique({ where: { id } });
  if (!po) {
    return res.status(404).json({ error: 'Purchase order not found' });
  }

  const line = await prisma.pOLine.findFirst({
    where: { id: lineId, poId: id },
  });
  if (!line) {
    return res.status(404).json({ error: 'Line not found' });
  }

  if (po.status !== 'DRAFT' && po.status !== 'SUBMITTED') {
    return res.status(400).json({ error: 'Can only modify lines on draft or submitted POs' });
  }

  const updated = await prisma.pOLine.update({
    where: { id: lineId },
    data: { quantityOrdered, unitCost, notes },
    include: {
      product: { select: { id: true, sku: true, name: true } },
    },
  });

  // Update PO totals
  const allLines = await prisma.pOLine.findMany({ where: { poId: id } });
  const totals = calculateTotals(allLines.map(l => ({
    quantityOrdered: l.quantityOrdered,
    unitCost: Number(l.unitCost),
  })));

  await prisma.purchaseOrder.update({
    where: { id },
    data: { subtotal: totals.subtotal, total: totals.total + Number(po.tax || 0) + Number(po.shipping || 0) },
  });

  res.json(updated);
});

// =============================================================================
// DELETE LINE
// =============================================================================

purchaseOrdersRouter.delete('/:id/lines/:lineId', async (req: Request, res: Response) => {
  const { id, lineId } = req.params;

  const po = await prisma.purchaseOrder.findUnique({ where: { id } });
  if (!po) {
    return res.status(404).json({ error: 'Purchase order not found' });
  }

  if (po.status !== 'DRAFT') {
    return res.status(400).json({ error: 'Can only delete lines from draft POs' });
  }

  const line = await prisma.pOLine.findFirst({
    where: { id: lineId, poId: id },
  });
  if (!line) {
    return res.status(404).json({ error: 'Line not found' });
  }

  await prisma.pOLine.delete({ where: { id: lineId } });

  // Update PO totals
  const allLines = await prisma.pOLine.findMany({ where: { poId: id } });
  const totals = calculateTotals(allLines.map(l => ({
    quantityOrdered: l.quantityOrdered,
    unitCost: Number(l.unitCost),
  })));

  await prisma.purchaseOrder.update({
    where: { id },
    data: { subtotal: totals.subtotal, total: totals.total + Number(po.tax || 0) + Number(po.shipping || 0) },
  });

  res.status(204).send();
});

// =============================================================================
// RECEIVE ITEMS
// =============================================================================

purchaseOrdersRouter.post('/:id/receive', async (req: Request, res: Response) => {
  const { id } = req.params;
  const { lines } = req.body; // Array of { lineId, quantityReceived }

  if (!lines || !Array.isArray(lines)) {
    return res.status(400).json({ error: 'lines array is required' });
  }

  const po = await prisma.purchaseOrder.findUnique({
    where: { id },
    include: { lines: true },
  });

  if (!po) {
    return res.status(404).json({ error: 'Purchase order not found' });
  }

  if (po.status === 'RECEIVED' || po.status === 'CANCELLED') {
    return res.status(400).json({ error: 'Cannot receive items on a completed or cancelled PO' });
  }

  // Update each line's received quantity
  for (const { lineId, quantityReceived } of lines) {
    const line = po.lines.find(l => l.id === lineId);
    if (!line) continue;

    const newReceived = line.quantityReceived + quantityReceived;
    await prisma.pOLine.update({
      where: { id: lineId },
      data: { quantityReceived: newReceived },
    });

    // Update stock (create movement and update stock item)
    const stockItem = await prisma.stockItem.findUnique({
      where: { productId_locationId: { productId: line.productId, locationId: po.destinationId } },
    });

    if (stockItem) {
      await prisma.stockItem.update({
        where: { id: stockItem.id },
        data: {
          quantityAvailable: { increment: quantityReceived },
          quantityInbound: { decrement: Math.min(quantityReceived, stockItem.quantityInbound) },
        },
      });

      await prisma.stockMovement.create({
        data: {
          stockItemId: stockItem.id,
          type: 'RECEIVE',
          quantity: quantityReceived,
          reference: po.poNumber,
          notes: `Received from PO ${po.poNumber}`,
        },
      });
    } else {
      // Create stock item if it doesn't exist
      const newStockItem = await prisma.stockItem.create({
        data: {
          productId: line.productId,
          locationId: po.destinationId,
          quantityAvailable: quantityReceived,
          costBasis: line.unitCost,
        },
      });

      await prisma.stockMovement.create({
        data: {
          stockItemId: newStockItem.id,
          type: 'RECEIVE',
          quantity: quantityReceived,
          reference: po.poNumber,
          notes: `Received from PO ${po.poNumber}`,
        },
      });
    }
  }

  // Check if all lines are fully received
  const updatedLines = await prisma.pOLine.findMany({ where: { poId: id } });
  const allReceived = updatedLines.every(l => l.quantityReceived >= l.quantityOrdered);
  const someReceived = updatedLines.some(l => l.quantityReceived > 0);

  let newStatus = po.status;
  if (allReceived) {
    newStatus = 'RECEIVED';
  } else if (someReceived && po.status !== 'PARTIAL') {
    newStatus = 'PARTIAL';
  }

  const updatedPO = await prisma.purchaseOrder.update({
    where: { id },
    data: {
      status: newStatus,
      receivedAt: allReceived ? new Date() : undefined,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
      destination: { select: { id: true, name: true, type: true } },
      lines: {
        include: {
          product: { select: { id: true, sku: true, name: true } },
        },
      },
    },
  });

  res.json(updatedPO);
});

// =============================================================================
// DELETE PURCHASE ORDER
// =============================================================================

purchaseOrdersRouter.delete('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;

  const po = await prisma.purchaseOrder.findUnique({ where: { id } });
  if (!po) {
    return res.status(404).json({ error: 'Purchase order not found' });
  }

  if (po.status !== 'DRAFT' && po.status !== 'CANCELLED') {
    return res.status(400).json({ error: 'Can only delete draft or cancelled POs' });
  }

  // Delete lines first, then PO
  await prisma.pOLine.deleteMany({ where: { poId: id } });
  await prisma.purchaseOrder.delete({ where: { id } });

  res.status(204).send();
});

// =============================================================================
// QUICK CREATE FROM VENDOR PRODUCTS
// =============================================================================

purchaseOrdersRouter.post('/from-vendor/:vendorId', async (req: Request, res: Response) => {
  const { vendorId } = req.params;
  const { destinationId, productIds, notes } = req.body;

  if (!destinationId) {
    return res.status(400).json({ error: 'destinationId is required' });
  }

  const vendor = await prisma.vendor.findUnique({ where: { id: vendorId } });
  if (!vendor) {
    return res.status(404).json({ error: 'Vendor not found' });
  }

  // Get vendor products
  const where: Record<string, unknown> = { vendorId, isActive: true };
  if (productIds && productIds.length > 0) {
    where.productId = { in: productIds };
  }

  const vendorProducts = await prisma.vendorProduct.findMany({
    where,
    include: { product: { select: { id: true, sku: true, name: true } } },
  });

  if (vendorProducts.length === 0) {
    return res.status(400).json({ error: 'No active products found for this vendor' });
  }

  const poNumber = await generatePONumber();
  const expectedAt = new Date();
  expectedAt.setDate(expectedAt.getDate() + vendor.leadTimeDays);

  // Create lines with MOQ as default quantity
  const lineData = vendorProducts.map(vp => ({
    productId: vp.productId,
    quantityOrdered: vp.minOrderQty,
    unitCost: Number(vp.unitCost),
  }));

  const totals = calculateTotals(lineData);

  const po = await prisma.purchaseOrder.create({
    data: {
      poNumber,
      vendorId,
      destinationId,
      notes,
      expectedAt,
      subtotal: totals.subtotal,
      total: totals.total,
      lines: { create: lineData },
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
      destination: { select: { id: true, name: true, type: true } },
      lines: {
        include: {
          product: { select: { id: true, sku: true, name: true } },
        },
      },
    },
  });

  res.status(201).json(po);
});
