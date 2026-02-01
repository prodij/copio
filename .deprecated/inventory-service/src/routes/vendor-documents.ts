import { Router, Request, Response } from 'express';
import { prisma, getPresignedUploadUrl, getPresignedDownloadUrl, deleteObject, BUCKETS, initializeBuckets } from '@copio/core';
import crypto from 'crypto';

export const vendorDocumentsRouter = Router();

// Initialize buckets on first request
let bucketsInitialized = false;

async function ensureBuckets() {
  if (!bucketsInitialized) {
    try {
      await initializeBuckets();
      bucketsInitialized = true;
    } catch (err) {
      console.error('Failed to initialize MinIO buckets:', err);
    }
  }
}

// =============================================================================
// LIST DOCUMENTS FOR A VENDOR
// =============================================================================

vendorDocumentsRouter.get('/', async (req: Request, res: Response) => {
  const { vendorId, type, expiringSoon } = req.query;
  
  const where: Record<string, unknown> = { isActive: true };
  if (vendorId) where.vendorId = vendorId;
  if (type) where.type = type;
  
  // Find documents expiring in next 30 days
  if (expiringSoon === 'true') {
    const thirtyDaysFromNow = new Date();
    thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30);
    where.expiresAt = {
      lte: thirtyDaysFromNow,
      gte: new Date(),
    };
  }

  const documents = await prisma.vendorDocument.findMany({
    where,
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
    orderBy: [{ type: 'asc' }, { uploadedAt: 'desc' }],
  });

  res.json(documents);
});

// =============================================================================
// GET SINGLE DOCUMENT
// =============================================================================

vendorDocumentsRouter.get('/:id', async (req: Request, res: Response) => {
  const doc = await prisma.vendorDocument.findUnique({
    where: { id: req.params.id },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  if (!doc) {
    return res.status(404).json({ error: 'Document not found' });
  }

  res.json(doc);
});

// =============================================================================
// GET PRESIGNED UPLOAD URL
// =============================================================================

vendorDocumentsRouter.post('/upload-url', async (req: Request, res: Response) => {
  await ensureBuckets();
  
  const { vendorId, filename, mimeType, type } = req.body;

  if (!vendorId || !filename || !mimeType || !type) {
    return res.status(400).json({ error: 'vendorId, filename, mimeType, and type are required' });
  }

  // Verify vendor exists
  const vendor = await prisma.vendor.findUnique({ where: { id: vendorId } });
  if (!vendor) {
    return res.status(400).json({ error: 'Vendor not found' });
  }

  // Generate unique object key
  const timestamp = Date.now();
  const hash = crypto.randomBytes(8).toString('hex');
  const ext = filename.split('.').pop() || '';
  const objectKey = `vendors/${vendorId}/${type}/${timestamp}-${hash}.${ext}`;

  try {
    const uploadUrl = await getPresignedUploadUrl(
      BUCKETS.VENDOR_DOCUMENTS,
      objectKey,
      3600 // 1 hour expiry
    );

    res.json({
      uploadUrl,
      objectKey,
      bucket: BUCKETS.VENDOR_DOCUMENTS,
    });
  } catch (err) {
    console.error('Failed to generate upload URL:', err);
    res.status(500).json({ error: 'Failed to generate upload URL' });
  }
});

// =============================================================================
// CREATE DOCUMENT RECORD (after upload completes)
// =============================================================================

vendorDocumentsRouter.post('/', async (req: Request, res: Response) => {
  const {
    vendorId,
    type,
    name,
    description,
    objectKey,
    mimeType,
    sizeBytes,
    expiresAt,
    version,
    uploadedBy,
  } = req.body;

  if (!vendorId || !type || !name || !objectKey || !mimeType || !sizeBytes) {
    return res.status(400).json({ 
      error: 'vendorId, type, name, objectKey, mimeType, and sizeBytes are required' 
    });
  }

  // Verify vendor exists
  const vendor = await prisma.vendor.findUnique({ where: { id: vendorId } });
  if (!vendor) {
    return res.status(400).json({ error: 'Vendor not found' });
  }

  const doc = await prisma.vendorDocument.create({
    data: {
      vendorId,
      type,
      name,
      description,
      bucket: BUCKETS.VENDOR_DOCUMENTS,
      objectKey,
      mimeType,
      sizeBytes,
      expiresAt: expiresAt ? new Date(expiresAt) : undefined,
      version,
      uploadedBy,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  res.status(201).json(doc);
});

// =============================================================================
// GET DOWNLOAD URL
// =============================================================================

vendorDocumentsRouter.get('/:id/download-url', async (req: Request, res: Response) => {
  const doc = await prisma.vendorDocument.findUnique({
    where: { id: req.params.id },
  });

  if (!doc) {
    return res.status(404).json({ error: 'Document not found' });
  }

  try {
    const downloadUrl = await getPresignedDownloadUrl(
      doc.bucket,
      doc.objectKey,
      3600 // 1 hour expiry
    );

    res.json({ downloadUrl, filename: doc.name });
  } catch (err) {
    console.error('Failed to generate download URL:', err);
    res.status(500).json({ error: 'Failed to generate download URL' });
  }
});

// =============================================================================
// UPDATE DOCUMENT METADATA
// =============================================================================

vendorDocumentsRouter.patch('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;
  const { name, description, expiresAt, version, isActive } = req.body;

  const existing = await prisma.vendorDocument.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Document not found' });
  }

  const doc = await prisma.vendorDocument.update({
    where: { id },
    data: {
      name,
      description,
      expiresAt: expiresAt ? new Date(expiresAt) : undefined,
      version,
      isActive,
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
  });

  res.json(doc);
});

// =============================================================================
// DELETE DOCUMENT
// =============================================================================

vendorDocumentsRouter.delete('/:id', async (req: Request, res: Response) => {
  const { id } = req.params;

  const existing = await prisma.vendorDocument.findUnique({ where: { id } });
  if (!existing) {
    return res.status(404).json({ error: 'Document not found' });
  }

  // Delete from MinIO
  try {
    await deleteObject(existing.bucket, existing.objectKey);
  } catch (err) {
    console.error('Failed to delete from MinIO (continuing):', err);
  }

  // Delete from database
  await prisma.vendorDocument.delete({ where: { id } });
  res.status(204).send();
});

// =============================================================================
// GET EXPIRING DOCUMENTS
// =============================================================================

vendorDocumentsRouter.get('/alerts/expiring', async (req: Request, res: Response) => {
  const days = parseInt(req.query.days as string) || 30;
  const futureDate = new Date();
  futureDate.setDate(futureDate.getDate() + days);

  const documents = await prisma.vendorDocument.findMany({
    where: {
      isActive: true,
      expiresAt: {
        lte: futureDate,
        gte: new Date(),
      },
    },
    include: {
      vendor: { select: { id: true, name: true, code: true } },
    },
    orderBy: { expiresAt: 'asc' },
  });

  res.json(documents);
});

// =============================================================================
// GET MISSING REQUIRED DOCUMENTS
// =============================================================================

vendorDocumentsRouter.get('/alerts/missing', async (req: Request, res: Response) => {
  // Find active vendors missing W9 or COI
  const vendors = await prisma.vendor.findMany({
    where: { isActive: true },
    include: {
      documents: {
        where: { isActive: true, type: { in: ['W9', 'COI'] } },
        select: { type: true },
      },
    },
  });

  const missing = vendors
    .map(v => {
      const hasW9 = v.documents.some(d => d.type === 'W9');
      const hasCOI = v.documents.some(d => d.type === 'COI');
      const missingDocs = [];
      if (!hasW9) missingDocs.push('W9');
      if (!hasCOI) missingDocs.push('COI');
      
      if (missingDocs.length > 0) {
        return { vendorId: v.id, vendorName: v.name, vendorCode: v.code, missing: missingDocs };
      }
      return null;
    })
    .filter(Boolean);

  res.json(missing);
});
