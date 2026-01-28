import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { prisma } from '@copio/core';

const router = Router();

const CreateStockItemSchema = z.object({
  productId: z.string().min(1),
  locationId: z.string().min(1),
  quantityAvailable: z.number().int().min(0).default(0),
  quantityReserved: z.number().int().min(0).optional(),
  quantityInbound: z.number().int().min(0).optional(),
  costBasis: z.number().positive().optional(),
});

router.post('/', async (req: Request, res: Response) => {
  const parsed = CreateStockItemSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  try {
    // Verify product exists
    const product = await prisma.product.findUnique({ where: { id: parsed.data.productId } });
    if (!product) {
      return res.status(400).json({ error: 'Product not found' });
    }

    // Verify location exists
    const location = await prisma.location.findUnique({ where: { id: parsed.data.locationId } });
    if (!location) {
      return res.status(400).json({ error: 'Location not found' });
    }

    const stockItem = await prisma.stockItem.create({ data: parsed.data });
    res.status(201).json(stockItem);
  } catch (error: unknown) {
    // Handle unique constraint violation (product+location already exists)
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'Stock item already exists for this product and location' });
    }
    throw error;
  }
});

router.get('/', async (_req: Request, res: Response) => {
  const stockItems = await prisma.stockItem.findMany({
    include: {
      product: true,
      location: true,
    },
  });
  res.json(stockItems);
});

router.get('/by-location/:locationId', async (req: Request, res: Response) => {
  const stockItems = await prisma.stockItem.findMany({
    where: { locationId: req.params.locationId },
    include: {
      product: true,
      location: true,
    },
  });
  res.json(stockItems);
});

router.get('/by-product/:productId', async (req: Request, res: Response) => {
  const stockItems = await prisma.stockItem.findMany({
    where: { productId: req.params.productId },
    include: {
      product: true,
      location: true,
    },
  });
  res.json(stockItems);
});

router.get('/:id', async (req: Request, res: Response) => {
  const stockItem = await prisma.stockItem.findUnique({
    where: { id: req.params.id },
    include: {
      product: true,
      location: true,
    },
  });
  if (!stockItem) {
    return res.status(404).json({ error: 'Stock item not found' });
  }
  res.json(stockItem);
});

export { router as stockItemsRouter };
