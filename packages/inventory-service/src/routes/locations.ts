import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { prisma, LocationType, Channel } from '@copio/core';

const router = Router();

const CreateLocationSchema = z.object({
  name: z.string().min(1),
  type: z.nativeEnum(LocationType),
  channel: z.nativeEnum(Channel).optional(),
  address: z.record(z.unknown()).optional(),
});

router.post('/', async (req: Request, res: Response) => {
  const parsed = CreateLocationSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }
  const location = await prisma.location.create({ data: parsed.data });
  res.status(201).json(location);
});

router.get('/', async (_req: Request, res: Response) => {
  const locations = await prisma.location.findMany();
  res.json(locations);
});

router.get('/:id', async (req: Request, res: Response) => {
  const location = await prisma.location.findUnique({ where: { id: req.params.id } });
  if (!location) {
    return res.status(404).json({ error: 'Location not found' });
  }
  res.json(location);
});

export { router as locationsRouter };
