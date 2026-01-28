import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { prisma, MovementType } from '@copio/core';

const router = Router();

const BaseMovementSchema = z.object({
  stockItemId: z.string().min(1),
  type: z.nativeEnum(MovementType),
  quantity: z.number().int(),
  notes: z.string().optional(),
  reference: z.string().optional(),
});

const TransferMovementSchema = BaseMovementSchema.extend({
  type: z.literal(MovementType.TRANSFER),
  quantity: z.number().int().positive(),
  destinationStockItemId: z.string().min(1),
});

const NonTransferMovementSchema = BaseMovementSchema.extend({
  type: z.enum([MovementType.RECEIVE, MovementType.SHIP, MovementType.ADJUST]),
}).refine(
  (data) => {
    // ADJUST can have any quantity (it's the target, not a delta in input)
    if (data.type === MovementType.ADJUST) {
      return data.quantity >= 0;
    }
    // RECEIVE and SHIP must have positive quantity
    return data.quantity > 0;
  },
  { message: 'Quantity must be positive for RECEIVE/SHIP movements' }
);

const CreateMovementSchema = z.union([TransferMovementSchema, NonTransferMovementSchema]);

router.post('/', async (req: Request, res: Response) => {
  const parsed = CreateMovementSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const data = parsed.data;

  // Verify stock item exists
  const stockItem = await prisma.stockItem.findUnique({
    where: { id: data.stockItemId },
  });

  if (!stockItem) {
    return res.status(404).json({ error: 'Stock item not found' });
  }

  try {
    if (data.type === MovementType.TRANSFER) {
      // TRANSFER: create paired movements in a transaction
      const transferData = data as z.infer<typeof TransferMovementSchema>;

      const destinationStockItem = await prisma.stockItem.findUnique({
        where: { id: transferData.destinationStockItemId },
      });

      if (!destinationStockItem) {
        return res.status(404).json({ error: 'Destination stock item not found' });
      }

      // Check sufficient stock at source
      if (stockItem.quantityAvailable < transferData.quantity) {
        return res.status(400).json({
          error: `Insufficient stock. Available: ${stockItem.quantityAvailable}, Requested: ${transferData.quantity}`,
        });
      }

      const result = await prisma.$transaction(async (tx) => {
        // Create outbound movement (negative)
        const sourceMovement = await tx.stockMovement.create({
          data: {
            stockItemId: data.stockItemId,
            type: MovementType.TRANSFER,
            quantity: -transferData.quantity,
            notes: transferData.notes,
            reference: transferData.reference,
          },
        });

        // Create inbound movement (positive)
        const destinationMovement = await tx.stockMovement.create({
          data: {
            stockItemId: transferData.destinationStockItemId,
            type: MovementType.TRANSFER,
            quantity: transferData.quantity,
            notes: transferData.notes,
            reference: transferData.reference,
          },
        });

        // Update source stock
        await tx.stockItem.update({
          where: { id: data.stockItemId },
          data: { quantityAvailable: { decrement: transferData.quantity } },
        });

        // Update destination stock
        await tx.stockItem.update({
          where: { id: transferData.destinationStockItemId },
          data: { quantityAvailable: { increment: transferData.quantity } },
        });

        return { sourceMovement, destinationMovement };
      });

      return res.status(201).json(result);
    }

    // Non-transfer movements
    if (data.type === MovementType.RECEIVE) {
      // RECEIVE: add quantity
      const result = await prisma.$transaction(async (tx) => {
        const movement = await tx.stockMovement.create({
          data: {
            stockItemId: data.stockItemId,
            type: data.type,
            quantity: data.quantity,
            notes: data.notes,
            reference: data.reference,
          },
        });

        await tx.stockItem.update({
          where: { id: data.stockItemId },
          data: { quantityAvailable: { increment: data.quantity } },
        });

        return movement;
      });

      return res.status(201).json(result);
    }

    if (data.type === MovementType.SHIP) {
      // SHIP: subtract quantity, fail if insufficient
      if (stockItem.quantityAvailable < data.quantity) {
        return res.status(400).json({
          error: `Insufficient stock. Available: ${stockItem.quantityAvailable}, Requested: ${data.quantity}`,
        });
      }

      const result = await prisma.$transaction(async (tx) => {
        const movement = await tx.stockMovement.create({
          data: {
            stockItemId: data.stockItemId,
            type: data.type,
            quantity: data.quantity,
            notes: data.notes,
            reference: data.reference,
          },
        });

        await tx.stockItem.update({
          where: { id: data.stockItemId },
          data: { quantityAvailable: { decrement: data.quantity } },
        });

        return movement;
      });

      return res.status(201).json(result);
    }

    if (data.type === MovementType.ADJUST) {
      // ADJUST: set to exact quantity, record delta
      const delta = data.quantity - stockItem.quantityAvailable;

      const result = await prisma.$transaction(async (tx) => {
        const movement = await tx.stockMovement.create({
          data: {
            stockItemId: data.stockItemId,
            type: data.type,
            quantity: delta, // Store the delta, not the target
            notes: data.notes,
            reference: data.reference,
          },
        });

        await tx.stockItem.update({
          where: { id: data.stockItemId },
          data: { quantityAvailable: data.quantity }, // Set to exact value
        });

        return movement;
      });

      return res.status(201).json(result);
    }
  } catch (error) {
    throw error;
  }
});

router.get('/', async (req: Request, res: Response) => {
  const { stockItemId } = req.query;

  const movements = await prisma.stockMovement.findMany({
    where: stockItemId ? { stockItemId: stockItemId as string } : undefined,
    include: {
      stockItem: {
        include: {
          product: true,
          location: true,
        },
      },
    },
    orderBy: { createdAt: 'desc' },
  });

  res.json(movements);
});

router.get('/:id', async (req: Request, res: Response) => {
  const movement = await prisma.stockMovement.findUnique({
    where: { id: req.params.id },
    include: {
      stockItem: {
        include: {
          product: true,
          location: true,
        },
      },
    },
  });

  if (!movement) {
    return res.status(404).json({ error: 'Movement not found' });
  }

  res.json(movement);
});

export { router as stockMovementsRouter };
