import { Router, Request, Response } from 'express';
import { prisma } from '@copio/core';

export const vendorContactsRouter = Router();

// =============================================================================
// LIST CONTACTS FOR A VENDOR
// =============================================================================

vendorContactsRouter.get('/', async (req: Request, res: Response) => {
  const { vendorId, role, active } = req.query;
  
  const where: Record<string, unknown> = {};
  if (vendorId) where.vendorId = vendorId;
  if (role) where.role = role;
  if (active === 'true') where.isActive = true;
  if (active === 'false') where.isActive = false;

  const contacts = await prisma.vendorContact.findMany({
    where,
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
    orderBy: [{ isPrimary: 'desc' }, { name: 'asc' }],
  });

  res.json(contacts);
});

// =============================================================================
// GET SINGLE CONTACT
// =============================================================================

vendorContactsRouter.get('/:id', async (req: Request, res: Response) => {
  const contact = await prisma.vendorContact.findUnique({
    where: { id: req.params.id },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  if (!contact) {
    return res.status(404).json({ error: 'Contact not found' });
  }

  res.json(contact);
});

// =============================================================================
// CREATE CONTACT
// =============================================================================

vendorContactsRouter.post('/', async (req: Request, res: Response) => {
  const {
    vendorId,
    name,
    title,
    email,
    phone,
    mobile,
    role = 'GENERAL',
    isPrimary = false,
    notes,
  } = req.body;

  if (!vendorId || !name) {
    return res.status(400).json({ error: 'vendorId and name are required' });
  }

  // Verify vendor exists
  const vendor = await prisma.vendor.findUnique({ where: { id: vendorId } });
  if (!vendor) {
    return res.status(400).json({ error: 'Vendor not found' });
  }

  // If setting as primary, unset other primary contacts for this vendor
  if (isPrimary) {
    await prisma.vendorContact.updateMany({
      where: { vendorId, isPrimary: true },
      data: { isPrimary: false },
    });
  }

  const contact = await prisma.vendorContact.create({
    data: {
      vendorId,
      name,
      title,
      email,
      phone,
      mobile,
      role,
      isPrimary,
      notes,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  res.status(201).json(contact);
});

// =============================================================================
// UPDATE CONTACT
// =============================================================================

vendorContactsRouter.patch('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;
  const {
    name,
    title,
    email,
    phone,
    mobile,
    role,
    isPrimary,
    notes,
    isActive,
  } = req.body;

  const existing = await prisma.vendorContact.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Contact not found' });
  }

  // If setting as primary, unset other primary contacts
  if (isPrimary === true) {
    await prisma.vendorContact.updateMany({
      where: { vendorId: existing.vendorId, isPrimary: true, id: { not: id } },
      data: { isPrimary: false },
    });
  }

  const contact = await prisma.vendorContact.update({
    where: { id },
    data: {
      name,
      title,
      email,
      phone,
      mobile,
      role,
      isPrimary,
      notes,
      isActive,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  res.json(contact);
});

// =============================================================================
// DELETE CONTACT
// =============================================================================

vendorContactsRouter.delete('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;

  const existing = await prisma.vendorContact.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Contact not found' });
  }

  await prisma.vendorContact.delete({ where: { id } });
  res.status(204).send();
});

// =============================================================================
// SET PRIMARY CONTACT
// =============================================================================

vendorContactsRouter.post('/:id/set-primary', async (req: Request, res: Response) => {
  const { id } = req.params;

  const existing = await prisma.vendorContact.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Contact not found' });
  }

  // Unset all primary for this vendor, then set this one
  await prisma.vendorContact.updateMany({
    where: { vendorId: existing.vendorId },
    data: { isPrimary: false },
  });

  const contact = await prisma.vendorContact.update({
    where: { id },
    data: { isPrimary: true },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  res.json(contact);
});
