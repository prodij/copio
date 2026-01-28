import { Router, Request, Response } from 'express';
import { prisma } from '@copio/core';

export const channelListingsRouter = Router();

// =============================================================================
// LIST CHANNEL LISTINGS
// =============================================================================

channelListingsRouter.get('/', async (req: Request, res: Response) => {
  const { productId, channel, status, limit = '50', offset = '0' } = req.query;
  
  const where: Record<string, unknown> = {};
  if (productId) where.productId = productId;
  if (channel) where.channel = channel;
  if (status) where.status = status;

  const [listings, total] = await Promise.all([
    prisma.channelListing.findMany({
      where,
      include: {
        product: {
          select: {
            id: true,
            sku: true,
            name: true,
            msrp: true,
            images: { take: 1, orderBy: { position: 'asc' } },
          },
        },
      },
      orderBy: [{ channel: 'asc' }, { createdAt: 'desc' }],
      take: parseInt(limit as string),
      skip: parseInt(offset as string),
    }),
    prisma.channelListing.count({ where }),
  ]);

  res.json({ listings, total });
});

// =============================================================================
// GET SINGLE LISTING
// =============================================================================

channelListingsRouter.get('/:id', async (req: Request, res: Response) => {
  const listing = await prisma.channelListing.findUnique({
    where: { id: req.params.id },
    include: {
      product: {
        select: {
          id: true,
          sku: true,
          name: true,
          shortDescription: true,
          longDescription: true,
          bulletPoints: true,
          msrp: true,
          costPrice: true,
          images: { orderBy: { position: 'asc' } },
        },
      },
    },
  });

  if (!listing) {
    return res.status(404).json({ error: 'Listing not found' });
  }

  res.json(listing);
});

// =============================================================================
// CREATE LISTING
// =============================================================================

channelListingsRouter.post('/', async (req: Request, res: Response) => {
  const {
    productId,
    channel,
    channelSku,
    channelProductId,
    title,
    description,
    bulletPoints,
    searchTerms,
    price,
    compareAtPrice,
    minPrice,
    maxPrice,
    fulfillmentChannel = 'MERCHANT',
    handlingDays,
    bufferStock = 0,
    maxQuantity,
    listingUrl,
    status = 'DRAFT',
  } = req.body;

  if (!productId || !channel || !channelSku) {
    return res.status(400).json({ error: 'productId, channel, and channelSku are required' });
  }

  // Verify product exists
  const product = await prisma.product.findUnique({ where: { id: productId } });
  if (!product) {
    return res.status(400).json({ error: 'Product not found' });
  }

  // Check for duplicate
  const existing = await prisma.channelListing.findFirst({
    where: { channel, channelSku },
  });
  if (existing) {
    return res.status(409).json({ error: 'A listing with this channel and SKU already exists' });
  }

  const listing = await prisma.channelListing.create({
    data: {
      productId,
      channel,
      channelSku,
      channelProductId,
      title,
      description,
      bulletPoints: bulletPoints || [],
      searchTerms: searchTerms || [],
      price,
      compareAtPrice,
      minPrice,
      maxPrice,
      fulfillmentChannel,
      handlingDays,
      bufferStock,
      maxQuantity,
      listingUrl,
      status,
    },
    include: {
      product: { select: { id: true, sku: true, name: true } },
    },
  });

  res.status(201).json(listing);
});

// =============================================================================
// UPDATE LISTING
// =============================================================================

channelListingsRouter.patch('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;
  const {
    channelSku,
    channelProductId,
    title,
    description,
    bulletPoints,
    searchTerms,
    price,
    compareAtPrice,
    minPrice,
    maxPrice,
    fulfillmentChannel,
    handlingDays,
    bufferStock,
    maxQuantity,
    listingUrl,
    status,
  } = req.body;

  const existing = await prisma.channelListing.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Listing not found' });
  }

  // Check for SKU conflict if changing
  if (channelSku && channelSku !== existing.channelSku) {
    const conflict = await prisma.channelListing.findFirst({
      where: { channel: existing.channel, channelSku, id: { not: id } },
    });
    if (conflict) {
      return res.status(409).json({ error: 'Another listing with this channel SKU already exists' });
    }
  }

  const listing = await prisma.channelListing.update({
    where: { id },
    data: {
      channelSku,
      channelProductId,
      title,
      description,
      bulletPoints,
      searchTerms,
      price,
      compareAtPrice,
      minPrice,
      maxPrice,
      fulfillmentChannel,
      handlingDays,
      bufferStock,
      maxQuantity,
      listingUrl,
      status,
    },
    include: {
      product: { select: { id: true, sku: true, name: true } },
    },
  });

  res.json(listing);
});

// =============================================================================
// DELETE LISTING
// =============================================================================

channelListingsRouter.delete('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;

  const existing = await prisma.channelListing.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Listing not found' });
  }

  await prisma.channelListing.delete({ where: { id } });
  res.status(204).send();
});

// =============================================================================
// BULK CREATE FROM PRODUCT
// =============================================================================

channelListingsRouter.post('/bulk-create', async (req: Request, res: Response) => {
  const { productId, channels } = req.body;
  // channels: [{ channel: 'AMAZON', channelSku: 'ABC123', price: 29.99 }, ...]

  if (!productId || !channels || !Array.isArray(channels)) {
    return res.status(400).json({ error: 'productId and channels array are required' });
  }

  const product = await prisma.product.findUnique({
    where: { id: productId },
    select: { id: true, sku: true, name: true, shortDescription: true, bulletPoints: true, msrp: true },
  });
  if (!product) {
    return res.status(400).json({ error: 'Product not found' });
  }

  const created = [];
  const errors = [];

  for (const ch of channels) {
    if (!ch.channel || !ch.channelSku) {
      errors.push({ channel: ch.channel, error: 'channel and channelSku are required' });
      continue;
    }

    // Check for existing
    const existing = await prisma.channelListing.findFirst({
      where: { channel: ch.channel, channelSku: ch.channelSku },
    });
    if (existing) {
      errors.push({ channel: ch.channel, channelSku: ch.channelSku, error: 'Already exists' });
      continue;
    }

    try {
      const listing = await prisma.channelListing.create({
        data: {
          productId,
          channel: ch.channel,
          channelSku: ch.channelSku,
          title: ch.title || product.name,
          description: ch.description || product.shortDescription,
          bulletPoints: ch.bulletPoints || product.bulletPoints || [],
          price: ch.price || product.msrp,
          fulfillmentChannel: ch.fulfillmentChannel || 'MERCHANT',
          status: 'DRAFT',
        },
      });
      created.push(listing);
    } catch (err) {
      errors.push({ channel: ch.channel, error: String(err) });
    }
  }

  res.status(201).json({ created, errors });
});

// =============================================================================
// SYNC STATUS (placeholder for future marketplace integration)
// =============================================================================

channelListingsRouter.post('/:id/sync', async (req: Request, res: Response) => {
  const { id } = req.params;

  const listing = await prisma.channelListing.findUnique({ where: { id } });
  if (!listing) {
    return res.status(404).json({ error: 'Listing not found' });
  }

  // This would integrate with marketplace APIs
  // For now, just update syncedAt
  const updated = await prisma.channelListing.update({
    where: { id },
    data: { syncedAt: new Date() },
    include: {
      product: { select: { id: true, sku: true, name: true } },
    },
  });

  res.json({ message: 'Sync initiated', listing: updated });
});
