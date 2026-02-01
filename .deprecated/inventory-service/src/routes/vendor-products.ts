import { Router, Request, Response } from 'express';
import { PrismaClient } from '@copio/core';

const prisma = new PrismaClient();
export const vendorProductsRouter = Router();

// List vendor products (with filters)
vendorProductsRouter.get('/', async (req: Request, res: Response) => {
  const { productId, vendorId } = req.query;
  
  const where: Record<string, string> = {};
  if (productId) where.productId = productId as string;
  if (vendorId) where.vendorId = vendorId as string;

  const vendorProducts = await prisma.vendorProduct.findMany({
    where,
    include: {
      product: { select: { id: true, sku: true, name: true } },
      vendor: { select: { id: true, name: true, code: true, leadTimeDays: true } },
    },
    orderBy: [{ isPreferred: 'desc' }, { createdAt: 'asc' }],
  });
  res.json(vendorProducts);
});

// Get single vendor product
vendorProductsRouter.get('/:id', async (req: Request, res: Response) => {
  const vendorProduct = await prisma.vendorProduct.findUnique({
    where: { id: req.params.id },
    include: {
      product: { select: { id: true, sku: true, name: true } },
      vendor: { select: { id: true, name: true, code: true, leadTimeDays: true } },
    },
  });
  if (!vendorProduct) {
    return res.status(404).json({ error: 'Vendor product not found' });
  }
  res.json(vendorProduct);
});

// Create vendor product link
vendorProductsRouter.post('/', async (req: Request, res: Response) => {
  const {
    productId,
    vendorId,
    vendorSku,
    vendorProductName,
    unitCost,
    currency = 'USD',
    minOrderQty = 1,
    orderMultiple = 1,
    casePackQty,
    leadTimeDays,
    isPreferred = false,
    isActive = true,
    notes,
  } = req.body;

  if (!productId || !vendorId || !vendorSku || unitCost === undefined) {
    return res.status(400).json({ 
      error: 'productId, vendorId, vendorSku, and unitCost are required' 
    });
  }

  // Check if link already exists
  const existing = await prisma.vendorProduct.findFirst({
    where: { productId, vendorId },
  });
  if (existing) {
    return res.status(409).json({ 
      error: 'This product is already linked to this vendor',
      existingId: existing.id,
    });
  }

  // If setting as preferred, unset other preferred for this product
  if (isPreferred) {
    await prisma.vendorProduct.updateMany({
      where: { productId, isPreferred: true },
      data: { isPreferred: false },
    });
  }

  const vendorProduct = await prisma.vendorProduct.create({
    data: {
      productId,
      vendorId,
      vendorSku,
      vendorProductName,
      unitCost,
      currency,
      minOrderQty,
      orderMultiple,
      casePackQty,
      leadTimeDays,
      isPreferred,
      isActive,
      notes,
    },
    include: {
      product: { select: { id: true, sku: true, name: true } },
      vendor: { select: { id: true, name: true, code: true, leadTimeDays: true } },
    },
  });

  res.status(201).json(vendorProduct);
});

// Update vendor product
vendorProductsRouter.patch('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;
  const {
    vendorSku,
    vendorProductName,
    unitCost,
    currency,
    minOrderQty,
    orderMultiple,
    casePackQty,
    leadTimeDays,
    isPreferred,
    isActive,
    notes,
  } = req.body;

  const existing = await prisma.vendorProduct.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Vendor product not found' });
  }

  // If setting as preferred, unset other preferred for this product
  if (isPreferred === true) {
    await prisma.vendorProduct.updateMany({
      where: { productId: existing.productId, isPreferred: true, id: { not: id } },
      data: { isPreferred: false },
    });
  }

  const vendorProduct = await prisma.vendorProduct.update({
    where: { id },
    data: {
      vendorSku,
      vendorProductName,
      unitCost,
      currency,
      minOrderQty,
      orderMultiple,
      casePackQty,
      leadTimeDays,
      isPreferred,
      isActive,
      notes,
    },
    include: {
      product: { select: { id: true, sku: true, name: true } },
      vendor: { select: { id: true, name: true, code: true, leadTimeDays: true } },
    },
  });

  res.json(vendorProduct);
});

// Delete vendor product link
vendorProductsRouter.delete('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;

  const existing = await prisma.vendorProduct.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Vendor product not found' });
  }

  await prisma.vendorProduct.delete({ where: { id } });
  res.status(204).send();
});

// Set preferred vendor for a product
vendorProductsRouter.post('/:id/set-preferred', async (req: Request, res: Response) => {
  const { id } = req.params;

  const existing = await prisma.vendorProduct.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Vendor product not found' });
  }

  // Unset all preferred for this product, then set this one
  await prisma.vendorProduct.updateMany({
    where: { productId: existing.productId },
    data: { isPreferred: false },
  });

  const vendorProduct = await prisma.vendorProduct.update({
    where: { id },
    data: { isPreferred: true },
    include: {
      product: { select: { id: true, sku: true, name: true } },
      vendor: { select: { id: true, name: true, code: true, leadTimeDays: true } },
    },
  });

  res.json(vendorProduct);
});

