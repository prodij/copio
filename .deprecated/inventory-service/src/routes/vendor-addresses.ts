import { Router, Request, Response } from 'express';
import { prisma } from '@copio/core';

export const vendorAddressesRouter = Router();

// =============================================================================
// LIST ADDRESSES FOR A VENDOR
// =============================================================================

vendorAddressesRouter.get('/', async (req: Request, res: Response) => {
  const { vendorId, type, country } = req.query;
  
  const where: Record<string, unknown> = { isActive: true };
  if (vendorId) where.vendorId = vendorId;
  if (type) where.type = type;
  if (country) where.country = country;

  const addresses = await prisma.vendorAddress.findMany({
    where,
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
    orderBy: [{ isPrimary: 'desc' }, { type: 'asc' }],
  });

  res.json(addresses);
});

// =============================================================================
// GET SINGLE ADDRESS
// =============================================================================

vendorAddressesRouter.get('/:id', async (req: Request, res: Response) => {
  const address = await prisma.vendorAddress.findUnique({
    where: { id: req.params.id },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  if (!address) {
    return res.status(404).json({ error: 'Address not found' });
  }

  res.json(address);
});

// =============================================================================
// CREATE ADDRESS
// =============================================================================

vendorAddressesRouter.post('/', async (req: Request, res: Response) => {
  const {
    vendorId,
    type = 'WAREHOUSE',
    label,
    isPrimary = false,
    street1,
    street2,
    city,
    state,
    postalCode,
    country,
    latitude,
    longitude,
    timezone,
    taxJurisdiction,
    ftzZone,
    portOfEntry,
    contactName,
    contactPhone,
    contactEmail,
    shippingNotes,
  } = req.body;

  if (!vendorId || !street1 || !city || !country) {
    return res.status(400).json({ error: 'vendorId, street1, city, and country are required' });
  }

  // Verify vendor exists
  const vendor = await prisma.vendor.findUnique({ where: { id: vendorId } });
  if (!vendor) {
    return res.status(400).json({ error: 'Vendor not found' });
  }

  // If setting as primary for this type, unset others
  if (isPrimary) {
    await prisma.vendorAddress.updateMany({
      where: { vendorId, type, isPrimary: true },
      data: { isPrimary: false },
    });
  }

  const address = await prisma.vendorAddress.create({
    data: {
      vendorId,
      type,
      label,
      isPrimary,
      street1,
      street2,
      city,
      state,
      postalCode,
      country,
      latitude,
      longitude,
      timezone,
      taxJurisdiction,
      ftzZone,
      portOfEntry,
      contactName,
      contactPhone,
      contactEmail,
      shippingNotes,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  res.status(201).json(address);
});

// =============================================================================
// UPDATE ADDRESS
// =============================================================================

vendorAddressesRouter.patch('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;
  const {
    type,
    label,
    isPrimary,
    street1,
    street2,
    city,
    state,
    postalCode,
    country,
    latitude,
    longitude,
    timezone,
    taxJurisdiction,
    ftzZone,
    portOfEntry,
    contactName,
    contactPhone,
    contactEmail,
    shippingNotes,
    isActive,
  } = req.body;

  const existing = await prisma.vendorAddress.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Address not found' });
  }

  // If setting as primary, unset others of same type
  if (isPrimary === true) {
    const targetType = type || existing.type;
    await prisma.vendorAddress.updateMany({
      where: { vendorId: existing.vendorId, type: targetType, isPrimary: true, id: { not: id } },
      data: { isPrimary: false },
    });
  }

  const address = await prisma.vendorAddress.update({
    where: { id },
    data: {
      type,
      label,
      isPrimary,
      street1,
      street2,
      city,
      state,
      postalCode,
      country,
      latitude,
      longitude,
      timezone,
      taxJurisdiction,
      ftzZone,
      portOfEntry,
      contactName,
      contactPhone,
      contactEmail,
      shippingNotes,
      isActive,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  res.json(address);
});

// =============================================================================
// DELETE ADDRESS
// =============================================================================

vendorAddressesRouter.delete('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;

  const existing = await prisma.vendorAddress.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Address not found' });
  }

  await prisma.vendorAddress.delete({ where: { id } });
  res.status(204).send();
});

// =============================================================================
// GET WAREHOUSES BY COUNTRY (for tariff/shipping analysis)
// =============================================================================

vendorAddressesRouter.get('/stats/by-country', async (_req: Request, res: Response) => {
  const stats = await prisma.vendorAddress.groupBy({
    by: ['country', 'type'],
    where: { isActive: true },
    _count: true,
  });

  // Reshape into { country: { WAREHOUSE: n, CORPORATE: n } }
  const byCountry: Record<string, Record<string, number>> = {};
  for (const row of stats) {
    if (!byCountry[row.country]) byCountry[row.country] = {};
    byCountry[row.country][row.type] = row._count;
  }

  res.json(byCountry);
});
