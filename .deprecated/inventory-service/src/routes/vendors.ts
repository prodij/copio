import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { prisma } from '@copio/core';

const router = Router();

// =============================================================================
// SCHEMAS
// =============================================================================

const CreateVendorSchema = z.object({
  // Identity
  name: z.string().min(1),
  legalName: z.string().optional(),
  code: z.string().min(1).optional(),
  taxId: z.string().optional(),
  website: z.string().url().optional().or(z.literal('')),
  
  // Classification
  tier: z.enum(['STRATEGIC', 'PREFERRED', 'STANDARD', 'PROBATION', 'SUSPENDED']).optional(),
  category: z.string().optional(),
  tags: z.array(z.string()).optional(),
  
  // Address
  address: z.record(z.unknown()).optional(),
  billingAddress: z.record(z.unknown()).optional(),
  
  // Ordering & Terms
  leadTimeDays: z.number().int().positive().optional(),
  minOrderValue: z.number().positive().optional(),
  paymentTerms: z.string().optional(),
  creditLimit: z.number().positive().optional(),
  currency: z.string().length(3).optional(),
  
  // Account Management
  accountManagerName: z.string().optional(),
  accountManagerEmail: z.string().email().optional().or(z.literal('')),
  preferredContactMethod: z.string().optional(),
  
  // Contract & Compliance
  contractStartDate: z.string().datetime().optional(),
  contractEndDate: z.string().datetime().optional(),
  insuranceExpiry: z.string().datetime().optional(),
  w9OnFile: z.boolean().optional(),
  
  // Notes
  notes: z.string().optional(),
  internalNotes: z.string().optional(),
});

const UpdateVendorSchema = CreateVendorSchema.partial().extend({
  isActive: z.boolean().optional(),
  onboardedAt: z.string().datetime().optional(),
}).refine(data => Object.keys(data).length > 0, {
  message: 'At least one field must be provided',
});

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
    const data = {
      ...parsed.data,
      website: parsed.data.website || undefined,
      accountManagerEmail: parsed.data.accountManagerEmail || undefined,
      contractStartDate: parsed.data.contractStartDate ? new Date(parsed.data.contractStartDate) : undefined,
      contractEndDate: parsed.data.contractEndDate ? new Date(parsed.data.contractEndDate) : undefined,
      insuranceExpiry: parsed.data.insuranceExpiry ? new Date(parsed.data.insuranceExpiry) : undefined,
    };

    const vendor = await prisma.vendor.create({
      data,
      include: {
        contacts: { where: { isActive: true }, orderBy: { isPrimary: 'desc' } },
        _count: { select: { products: true, purchaseOrders: true } },
      },
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
  const { active, search, tier } = req.query;
  
  const where: Record<string, unknown> = {};
  if (active === 'true') where.isActive = true;
  if (active === 'false') where.isActive = false;
  if (tier) where.tier = tier;
  if (search) {
    where.OR = [
      { name: { contains: search as string, mode: 'insensitive' } },
      { code: { contains: search as string, mode: 'insensitive' } },
      { legalName: { contains: search as string, mode: 'insensitive' } },
    ];
  }

  const vendors = await prisma.vendor.findMany({
    where,
    include: {
      contacts: { where: { isActive: true, isPrimary: true }, take: 1 },
      _count: { select: { products: true, purchaseOrders: true } },
    },
    orderBy: { name: 'asc' },
  });
  res.json(vendors);
});

// Get single vendor
router.get('/:id', async (req: Request, res: Response) => {
  const vendor = await prisma.vendor.findUnique({
    where: { id: req.params.id },
    include: {
      contacts: { where: { isActive: true }, orderBy: [{ isPrimary: 'desc' }, { role: 'asc' }] },
      addresses: { where: { isActive: true }, orderBy: [{ isPrimary: 'desc' }, { type: 'asc' }] },
      documents: { where: { isActive: true }, orderBy: [{ type: 'asc' }, { uploadedAt: 'desc' }] },
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
    const data = {
      ...parsed.data,
      website: parsed.data.website === '' ? null : parsed.data.website,
      accountManagerEmail: parsed.data.accountManagerEmail === '' ? null : parsed.data.accountManagerEmail,
      contractStartDate: parsed.data.contractStartDate ? new Date(parsed.data.contractStartDate) : undefined,
      contractEndDate: parsed.data.contractEndDate ? new Date(parsed.data.contractEndDate) : undefined,
      insuranceExpiry: parsed.data.insuranceExpiry ? new Date(parsed.data.insuranceExpiry) : undefined,
      onboardedAt: parsed.data.onboardedAt ? new Date(parsed.data.onboardedAt) : undefined,
    };

    const vendor = await prisma.vendor.update({
      where: { id: req.params.id },
      data,
      include: {
        contacts: { where: { isActive: true }, orderBy: { isPrimary: 'desc' } },
        _count: { select: { products: true, purchaseOrders: true } },
      },
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

  // Delete contacts, vendor products, then vendor
  await prisma.vendorContact.deleteMany({ where: { vendorId: req.params.id } });
  await prisma.vendorProduct.deleteMany({ where: { vendorId: req.params.id } });
  await prisma.vendor.delete({ where: { id: req.params.id } });
  res.status(204).send();
});

// =============================================================================
// VENDOR CONTACTS (nested under vendor)
// =============================================================================

// List vendor contacts
router.get('/:id/contacts', async (req: Request, res: Response) => {
  const vendor = await prisma.vendor.findUnique({ where: { id: req.params.id } });
  if (!vendor) {
    return res.status(404).json({ error: 'Vendor not found' });
  }

  const contacts = await prisma.vendorContact.findMany({
    where: { vendorId: req.params.id },
    orderBy: [{ isPrimary: 'desc' }, { role: 'asc' }, { name: 'asc' }],
  });
  res.json(contacts);
});

// Add contact to vendor
router.post('/:id/contacts', async (req: Request, res: Response) => {
  const { name, title, email, phone, mobile, role, isPrimary, notes } = req.body;

  if (!name) {
    return res.status(400).json({ error: 'name is required' });
  }

  const vendor = await prisma.vendor.findUnique({ where: { id: req.params.id } });
  if (!vendor) {
    return res.status(404).json({ error: 'Vendor not found' });
  }

  // If setting as primary, unset other primary contacts
  if (isPrimary) {
    await prisma.vendorContact.updateMany({
      where: { vendorId: req.params.id, isPrimary: true },
      data: { isPrimary: false },
    });
  }

  const contact = await prisma.vendorContact.create({
    data: {
      vendorId: req.params.id,
      name,
      title,
      email,
      phone,
      mobile,
      role: role || 'GENERAL',
      isPrimary: isPrimary || false,
      notes,
    },
  });
  res.status(201).json(contact);
});

// =============================================================================
// QUICK STATS
// =============================================================================

router.get('/stats/summary', async (_req: Request, res: Response) => {
  const [total, byTier, expiringSoon] = await Promise.all([
    prisma.vendor.count({ where: { isActive: true } }),
    prisma.vendor.groupBy({
      by: ['tier'],
      where: { isActive: true },
      _count: true,
    }),
    prisma.vendor.count({
      where: {
        isActive: true,
        contractEndDate: {
          lte: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
          gte: new Date(),
        },
      },
    }),
  ]);

  res.json({
    total,
    byTier: byTier.reduce((acc, t) => ({ ...acc, [t.tier]: t._count }), {}),
    contractsExpiringSoon: expiringSoon,
  });
});

export { router as vendorsRouter };
