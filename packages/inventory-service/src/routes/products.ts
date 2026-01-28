import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { prisma, Channel, ListingStatus } from '@copio/core';

const router = Router();

const ChannelListingSchema = z.object({
  channel: z.nativeEnum(Channel),
  channelSku: z.string().min(1),
  channelData: z.record(z.unknown()).optional(),
  status: z.nativeEnum(ListingStatus).optional(),
});

const CreateProductSchema = z.object({
  name: z.string().min(1),
  sku: z.string().min(1),
  brand: z.string().optional(),
  category: z.string().optional(),
  attributes: z.record(z.unknown()).optional(),
  channelListings: z.array(ChannelListingSchema).optional(),
});

const UpdateProductSchema = z.object({
  name: z.string().min(1).optional(),
  brand: z.string().optional(),
  category: z.string().optional(),
  attributes: z.record(z.unknown()).optional(),
}).refine(data => Object.keys(data).length > 0, {
  message: 'At least one field must be provided',
});

router.post('/', async (req: Request, res: Response) => {
  const parsed = CreateProductSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const { channelListings, ...productData } = parsed.data;

  try {
    const product = await prisma.product.create({
      data: {
        ...productData,
        listings: channelListings
          ? { create: channelListings }
          : undefined,
      },
      include: { listings: true },
    });
    res.status(201).json(product);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'SKU already exists' });
    }
    throw error;
  }
});

router.get('/', async (_req: Request, res: Response) => {
  const products = await prisma.product.findMany({
    include: { listings: true },
  });
  res.json(products);
});

router.get('/:id', async (req: Request, res: Response) => {
  const product = await prisma.product.findUnique({
    where: { id: req.params.id },
    include: { listings: true },
  });
  if (!product) {
    return res.status(404).json({ error: 'Product not found' });
  }
  res.json(product);
});

router.patch('/:id', async (req: Request, res: Response) => {
  const parsed = UpdateProductSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const existing = await prisma.product.findUnique({
    where: { id: req.params.id },
  });
  if (!existing) {
    return res.status(404).json({ error: 'Product not found' });
  }

  const product = await prisma.product.update({
    where: { id: req.params.id },
    data: parsed.data,
    include: { listings: true },
  });
  res.json(product);
});

export { router as productsRouter };
