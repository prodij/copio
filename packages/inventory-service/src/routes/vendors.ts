import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { prisma } from '@copio/core';

const router = Router();

// =============================================================================
// SCHEMAS
// =============================================================================

const CreateVendorSchema = z.object({
  name: z.string().min(1),
  code: z.string().min(1).optional(),
  contact: z.record(z.unknown()).optional(),
  address: z.record(z.unknown()).optional(),
  leadTimeDays: z.number().int().positive().optional(),
  minOrderValue: z.number().positive().optional(),
  paymentTerms: z.string().optional(),
  currency: z.string().length(3).optional(),
  notes: z.string().optional(),
});

const UpdateVendorSchema = CreateVendorSchema.partial().extend({
  isActive: z.boolean().optional(),
}).refine(data => Object.keys(data).length > 0, {
  message: 'At least one field must be provided',
});

const VendorProductSchema = z.object({
  productId: z.string().uuid(),
  vendorSku: z.string().min(1),
  vendorProductName: z.string().optional(),
  unitCost: z.number().positive(),
  currency: z.string().length(3).optional(),
  minOrderQty: z.number().int().positive().optional(),
  orderMultiple: z.number().int().positive().optional(),
  casePackQty: z.number().int().positive().optional(),
  leadTimeDays: z.number().int().positive().optional(),
  isPreferred: z.boolean().optional(),
});

const UpdateVendorProductSchema = VendorProductSchema.partial().omit({ productId: true }).refine(
  data => Object.keys(data).length > 0,
  { message: 'At least one field must be provided' }
);

// =============================================================================
// VENDOR ROUTES
// =============================================================================

// Create vendor
router.post('/', async (req: Request, res: Response) => {
  const parsed = CreateVendorSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  try {
    const vendor = await prisma.vendor.create({
      data: parsed.data,
      include: { _count: { select: { products: true, purchaseOrders: true } } },
    });
    res.status(201).json(vendor);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'Vendor code already exists' });
    }
    throw error;
  }
});

// List vendors
router.get('/', async (req: Request, res: Response) => {
  const { active, search } = req.query;
  
  const where: Record<string, unknown> = {};
  if (active === 'true') where.isActive = true;
  if (active === 'false') where.isActive = false;
  if (search) {
    where.OR = [
      { name: { contains: search as string, mode: 'insensitive' } },
      { code: { contains: search as string, mode: 'insensitive' } },
    ];
  }

  const vendors = await prisma.vendor.findMany({
    where,
    include: { _count: { select: { products: true, purchaseOrders: true } } },
    orderBy: { name: 'asc' },
  });
  res.json(vendors);
});

// Get single vendor
router.get('/:id', async (req: Request, res: Response) => {
  const vendor = await prisma.vendor.findUnique({
    where: { id: req.params.id },
    include: {
      products: {
        include: {
          product: { select: { id: true, sku: true, name: true } },
        },
        orderBy: { createdAt: 'desc' },
      },
      _count: { select: { purchaseOrders: true } },
    },
  });
  if (!vendor) {
    return res.status(404).json({ error: 'Vendor not found' });
  }
  res.json(vendor);
});

// Update vendor
router.patch('/:id', async (req: Request, res: Response) => {
  const parsed = UpdateVendorSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const existing = await prisma.vendor.findUnique({ where: { id: req.params.id } });
  if (!existing) {
    return res.status(404).json({ error: 'Vendor not found' });
  }

  try {
    const vendor = await prisma.vendor.update({
      where: { id: req.params.id },
      data: parsed.data,
      include: { _count: { select: { products: true, purchaseOrders: true } } },
    });
    res.json(vendor);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'Vendor code already exists' });
    }
    throw error;
  }
});

// Delete vendor
router.delete('/:id', async (req: Request, res: Response) => {
  const existing = await prisma.vendor.findUnique({
    where: { id: req.params.id },
    include: { _count: { select: { products: true, purchaseOrders: true } } },
  });
  if (!existing) {
    return res.status(404).json({ error: 'Vendor not found' });
  }
  if (existing._count.purchaseOrders > 0) {
    return res.status(400).json({ error: 'Cannot delete vendor with purchase orders' });
  }

  // Delete vendor products first, then vendor
  await prisma.vendorProduct.deleteMany({ where: { vendorId: req.params.id } });
  await prisma.vendor.delete({ where: { id: req.params.id } });
  res.status(204).send();
});

// =============================================================================
// VENDOR PRODUCT ROUTES
// =============================================================================

// Add product to vendor
router.post('/:id/products', async (req: Request, res: Response) => {
  const parsed = VendorProductSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const [vendor, product] = await Promise.all([
    prisma.vendor.findUnique({ where: { id: req.params.id } }),
    prisma.product.findUnique({ where: { id: parsed.data.productId } }),
  ]);

  if (!vendor) return res.status(404).json({ error: 'Vendor not found' });
  if (!product) return res.status(404).json({ error: 'Product not found' });

  // If setting as preferred, unset other preferred first
  if (parsed.data.isPreferred) {
    await prisma.vendorProduct.updateMany({
      where: { productId: parsed.data.productId, isPreferred: true },
      data: { isPreferred: false },
    });
  }

  try {
    const vendorProduct = await prisma.vendorProduct.create({
      data: {
        vendorId: req.params.id,
        ...parsed.data,
      },
      include: {
        vendor: { select: { id: true, name: true, code: true } },
        product: { select: { id: true, sku: true, name: true } },
      },
    });
    res.status(201).json(vendorProduct);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'Product already linked to this vendor or vendor SKU already exists' });
    }
    throw error;
  }
});

// List vendor's products
router.get('/:id/products', async (req: Request, res: Response) => {
  const vendor = await prisma.vendor.findUnique({ where: { id: req.params.id } });
  if (!vendor) {
    return res.status(404).json({ error: 'Vendor not found' });
  }

  const products = await prisma.vendorProduct.findMany({
    where: { vendorId: req.params.id },
    include: {
      product: {
        select: {
          id: true,
          sku: true,
          name: true,
          brand: true,
          images: { take: 1, orderBy: { position: 'asc' } },
        },
      },
    },
    orderBy: { createdAt: 'desc' },
  });
  res.json(products);
});

// Update vendor product
router.patch('/:id/products/:productId', async (req: Request, res: Response) => {
  const parsed = UpdateVendorProductSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const vendorProduct = await prisma.vendorProduct.findFirst({
    where: { vendorId: req.params.id, productId: req.params.productId },
  });
  if (!vendorProduct) {
    return res.status(404).json({ error: 'Vendor product not found' });
  }

  // If setting as preferred, unset other preferred first
  if (parsed.data.isPreferred) {
    await prisma.vendorProduct.updateMany({
      where: { productId: req.params.productId, isPreferred: true, NOT: { id: vendorProduct.id } },
      data: { isPreferred: false },
    });
  }

  const updated = await prisma.vendorProduct.update({
    where: { id: vendorProduct.id },
    data: parsed.data,
    include: {
      vendor: { select: { id: true, name: true, code: true } },
      product: { select: { id: true, sku: true, name: true } },
    },
  });
  res.json(updated);
});

// Remove product from vendor
router.delete('/:id/products/:productId', async (req: Request, res: Response) => {
  const vendorProduct = await prisma.vendorProduct.findFirst({
    where: { vendorId: req.params.id, productId: req.params.productId },
  });
  if (!vendorProduct) {
    return res.status(404).json({ error: 'Vendor product not found' });
  }

  await prisma.vendorProduct.delete({ where: { id: vendorProduct.id } });
  res.status(204).send();
});

export { router as vendorsRouter };
