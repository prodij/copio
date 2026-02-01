import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { prisma, Channel, ListingStatus, ProductType, ProductStatus } from '@copio/core';

const router = Router();

// =============================================================================
// SCHEMAS
// =============================================================================

const ChannelListingSchema = z.object({
  channel: z.nativeEnum(Channel),
  channelSku: z.string().min(1),
  title: z.string().optional(),
  description: z.string().optional(),
  bulletPoints: z.array(z.string()).optional(),
  price: z.number().positive().optional(),
  channelData: z.record(z.unknown()).optional(),
  status: z.nativeEnum(ListingStatus).optional(),
});

const ProductImageSchema = z.object({
  url: z.string().url(),
  altText: z.string().optional(),
  position: z.number().int().min(0).optional(),
  width: z.number().int().positive().optional(),
  height: z.number().int().positive().optional(),
});

const ProductAttributeSchema = z.object({
  name: z.string().min(1),
  value: z.string().min(1),
  group: z.string().optional(),
});

const CreateProductSchema = z.object({
  // Core
  sku: z.string().min(1),
  name: z.string().min(1),
  productType: z.nativeEnum(ProductType).optional(),
  status: z.nativeEnum(ProductStatus).optional(),
  
  // Variation hierarchy
  parentId: z.string().uuid().optional(),
  variationType: z.string().optional(),
  variationValue: z.string().optional(),
  
  // Identity
  brand: z.string().optional(),
  manufacturer: z.string().optional(),
  modelNumber: z.string().optional(),
  
  // Identifiers
  upc: z.string().optional(),
  ean: z.string().optional(),
  gtin: z.string().optional(),
  asin: z.string().optional(),
  mpn: z.string().optional(),
  
  // AI Content
  shortDescription: z.string().optional(),
  longDescription: z.string().optional(),
  bulletPoints: z.array(z.string()).optional(),
  searchTerms: z.array(z.string()).optional(),
  seoTitle: z.string().optional(),
  seoDescription: z.string().optional(),
  
  // Physical
  weightValue: z.number().positive().optional(),
  weightUnit: z.string().optional(),
  lengthValue: z.number().positive().optional(),
  widthValue: z.number().positive().optional(),
  heightValue: z.number().positive().optional(),
  dimensionUnit: z.string().optional(),
  
  // Package
  pkgWeightValue: z.number().positive().optional(),
  pkgWeightUnit: z.string().optional(),
  pkgLengthValue: z.number().positive().optional(),
  pkgWidthValue: z.number().positive().optional(),
  pkgHeightValue: z.number().positive().optional(),
  pkgDimensionUnit: z.string().optional(),
  
  // Compliance
  countryOfOrigin: z.string().optional(),
  hazmat: z.boolean().optional(),
  hazmatInfo: z.record(z.unknown()).optional(),
  ageRestriction: z.number().int().positive().optional(),
  certifications: z.array(z.string()).optional(),
  warrantyInfo: z.string().optional(),
  
  // Pricing
  costPrice: z.number().positive().optional(),
  msrp: z.number().positive().optional(),
  
  // Nested creates
  images: z.array(ProductImageSchema).optional(),
  attributes: z.array(ProductAttributeSchema).optional(),
  channelListings: z.array(ChannelListingSchema).optional(),
});

const UpdateProductSchema = CreateProductSchema.partial().omit({ sku: true }).refine(
  data => Object.keys(data).length > 0,
  { message: 'At least one field must be provided' }
);

// =============================================================================
// ROUTES
// =============================================================================

// Create product
router.post('/', async (req: Request, res: Response) => {
  const parsed = CreateProductSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const { images, attributes, channelListings, ...productData } = parsed.data;

  try {
    const product = await prisma.product.create({
      data: {
        ...productData,
        images: images ? { create: images } : undefined,
        attributes: attributes ? { create: attributes } : undefined,
        listings: channelListings ? { create: channelListings } : undefined,
      },
      include: {
        images: { orderBy: { position: 'asc' } },
        attributes: true,
        listings: true,
        parent: { select: { id: true, sku: true, name: true } },
        variations: { select: { id: true, sku: true, name: true, variationType: true, variationValue: true } },
      },
    });
    res.status(201).json(product);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'SKU already exists' });
    }
    throw error;
  }
});

// List products
router.get('/', async (req: Request, res: Response) => {
  const { type, status, parentId, search, page = '1', pageSize = '25' } = req.query;
  
  const where: Record<string, unknown> = {};
  if (type) where.productType = type;
  if (status) where.status = status;
  if (parentId === 'null') where.parentId = null;
  else if (parentId) where.parentId = parentId;
  if (search) {
    where.OR = [
      { name: { contains: search as string, mode: 'insensitive' } },
      { sku: { contains: search as string, mode: 'insensitive' } },
      { brand: { contains: search as string, mode: 'insensitive' } },
    ];
  }

  const pageNum = Math.max(1, parseInt(page as string) || 1);
  const pageSizeNum = Math.min(100, Math.max(1, parseInt(pageSize as string) || 25));
  const skip = (pageNum - 1) * pageSizeNum;

  const [products, total] = await Promise.all([
    prisma.product.findMany({
      where,
      include: {
        images: { orderBy: { position: 'asc' }, take: 1 },
        listings: { select: { id: true, channel: true, status: true } },
        _count: { select: { variations: true } },
      },
      orderBy: { updatedAt: 'desc' },
      skip,
      take: pageSizeNum,
    }),
    prisma.product.count({ where }),
  ]);

  res.json({
    data: products,
    pagination: {
      page: pageNum,
      pageSize: pageSizeNum,
      total,
      totalPages: Math.ceil(total / pageSizeNum),
    },
  });
});

// Get single product
router.get('/:id', async (req: Request, res: Response) => {
  const product = await prisma.product.findUnique({
    where: { id: req.params.id },
    include: {
      images: { orderBy: { position: 'asc' } },
      attributes: { orderBy: { name: 'asc' } },
      listings: true,
      categories: { include: { category: true } },
      parent: { select: { id: true, sku: true, name: true } },
      variations: {
        select: {
          id: true,
          sku: true,
          name: true,
          variationType: true,
          variationValue: true,
          status: true,
          images: { take: 1, orderBy: { position: 'asc' } },
        },
      },
      vendors: {
        include: {
          vendor: { select: { id: true, name: true, code: true, leadTimeDays: true } },
        },
        orderBy: [{ isPreferred: 'desc' }, { createdAt: 'asc' }],
      },
    },
  });
  if (!product) {
    return res.status(404).json({ error: 'Product not found' });
  }
  res.json(product);
});

// Update product
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

  const { images, attributes, channelListings, ...productData } = parsed.data;

  // Handle nested updates separately
  const product = await prisma.product.update({
    where: { id: req.params.id },
    data: productData,
    include: {
      images: { orderBy: { position: 'asc' } },
      attributes: true,
      listings: true,
      parent: { select: { id: true, sku: true, name: true } },
      variations: { select: { id: true, sku: true, name: true, variationType: true, variationValue: true } },
    },
  });
  res.json(product);
});

// Delete product
router.delete('/:id', async (req: Request, res: Response) => {
  const existing = await prisma.product.findUnique({
    where: { id: req.params.id },
  });
  if (!existing) {
    return res.status(404).json({ error: 'Product not found' });
  }

  await prisma.product.delete({ where: { id: req.params.id } });
  res.status(204).send();
});

// =============================================================================
// PRODUCT IMAGES
// =============================================================================

router.post('/:id/images', async (req: Request, res: Response) => {
  const parsed = ProductImageSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const product = await prisma.product.findUnique({ where: { id: req.params.id } });
  if (!product) {
    return res.status(404).json({ error: 'Product not found' });
  }

  const image = await prisma.productImage.create({
    data: {
      ...parsed.data,
      productId: req.params.id,
    },
  });
  res.status(201).json(image);
});

router.delete('/:id/images/:imageId', async (req: Request, res: Response) => {
  const image = await prisma.productImage.findFirst({
    where: { id: req.params.imageId, productId: req.params.id },
  });
  if (!image) {
    return res.status(404).json({ error: 'Image not found' });
  }

  await prisma.productImage.delete({ where: { id: req.params.imageId } });
  res.status(204).send();
});

// =============================================================================
// PRODUCT ATTRIBUTES
// =============================================================================

router.post('/:id/attributes', async (req: Request, res: Response) => {
  const parsed = ProductAttributeSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const product = await prisma.product.findUnique({ where: { id: req.params.id } });
  if (!product) {
    return res.status(404).json({ error: 'Product not found' });
  }

  try {
    const attribute = await prisma.productAttribute.create({
      data: {
        ...parsed.data,
        productId: req.params.id,
      },
    });
    res.status(201).json(attribute);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'Attribute already exists for this product' });
    }
    throw error;
  }
});

router.patch('/:id/attributes/:attrId', async (req: Request, res: Response) => {
  const parsed = ProductAttributeSchema.partial().safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const attribute = await prisma.productAttribute.findFirst({
    where: { id: req.params.attrId, productId: req.params.id },
  });
  if (!attribute) {
    return res.status(404).json({ error: 'Attribute not found' });
  }

  const updated = await prisma.productAttribute.update({
    where: { id: req.params.attrId },
    data: parsed.data,
  });
  res.json(updated);
});

router.delete('/:id/attributes/:attrId', async (req: Request, res: Response) => {
  const attribute = await prisma.productAttribute.findFirst({
    where: { id: req.params.attrId, productId: req.params.id },
  });
  if (!attribute) {
    return res.status(404).json({ error: 'Attribute not found' });
  }

  await prisma.productAttribute.delete({ where: { id: req.params.attrId } });
  res.status(204).send();
});

export { router as productsRouter };
