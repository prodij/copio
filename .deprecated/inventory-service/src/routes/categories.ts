import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { prisma } from '@copio/core';

const router = Router();

// =============================================================================
// SCHEMAS
// =============================================================================

const CreateCategorySchema = z.object({
  name: z.string().min(1),
  slug: z.string().min(1).regex(/^[a-z0-9-]+$/, 'Slug must be lowercase alphanumeric with hyphens'),
  parentId: z.string().uuid().optional(),
  description: z.string().optional(),
  amazonBrowseNode: z.string().optional(),
  shopifyProductType: z.string().optional(),
  walmartCategoryId: z.string().optional(),
  googleCategoryId: z.string().optional(),
});

const UpdateCategorySchema = CreateCategorySchema.partial().refine(
  data => Object.keys(data).length > 0,
  { message: 'At least one field must be provided' }
);

// =============================================================================
// ROUTES
// =============================================================================

// Create category
router.post('/', async (req: Request, res: Response) => {
  const parsed = CreateCategorySchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  try {
    const category = await prisma.category.create({
      data: parsed.data,
      include: { parent: { select: { id: true, name: true, slug: true } } },
    });
    res.status(201).json(category);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'Category slug already exists' });
    }
    throw error;
  }
});

// List categories (tree structure)
router.get('/', async (req: Request, res: Response) => {
  const { flat } = req.query;
  
  if (flat === 'true') {
    // Flat list
    const categories = await prisma.category.findMany({
      include: {
        parent: { select: { id: true, name: true } },
        _count: { select: { children: true, products: true } },
      },
      orderBy: { name: 'asc' },
    });
    return res.json(categories);
  }

  // Tree structure - get root categories with nested children
  const categories = await prisma.category.findMany({
    where: { parentId: null },
    include: {
      children: {
        include: {
          children: {
            include: {
              children: true, // 3 levels deep
            },
          },
        },
      },
      _count: { select: { products: true } },
    },
    orderBy: { name: 'asc' },
  });
  res.json(categories);
});

// Get single category
router.get('/:id', async (req: Request, res: Response) => {
  const category = await prisma.category.findUnique({
    where: { id: req.params.id },
    include: {
      parent: { select: { id: true, name: true, slug: true } },
      children: { select: { id: true, name: true, slug: true } },
      products: {
        include: {
          product: { select: { id: true, sku: true, name: true } },
        },
      },
    },
  });
  if (!category) {
    return res.status(404).json({ error: 'Category not found' });
  }
  res.json(category);
});

// Update category
router.patch('/:id', async (req: Request, res: Response) => {
  const parsed = UpdateCategorySchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({ error: parsed.error.errors });
  }

  const existing = await prisma.category.findUnique({ where: { id: req.params.id } });
  if (!existing) {
    return res.status(404).json({ error: 'Category not found' });
  }

  try {
    const category = await prisma.category.update({
      where: { id: req.params.id },
      data: parsed.data,
      include: { parent: { select: { id: true, name: true, slug: true } } },
    });
    res.json(category);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'Category slug already exists' });
    }
    throw error;
  }
});

// Delete category
router.delete('/:id', async (req: Request, res: Response) => {
  const existing = await prisma.category.findUnique({
    where: { id: req.params.id },
    include: { _count: { select: { children: true, products: true } } },
  });
  if (!existing) {
    return res.status(404).json({ error: 'Category not found' });
  }
  if (existing._count.children > 0) {
    return res.status(400).json({ error: 'Cannot delete category with children' });
  }
  if (existing._count.products > 0) {
    return res.status(400).json({ error: 'Cannot delete category with products' });
  }

  await prisma.category.delete({ where: { id: req.params.id } });
  res.status(204).send();
});

// =============================================================================
// PRODUCT-CATEGORY ASSOCIATIONS
// =============================================================================

// Add product to category
router.post('/:id/products', async (req: Request, res: Response) => {
  const { productId, isPrimary } = req.body;
  
  if (!productId) {
    return res.status(400).json({ error: 'productId is required' });
  }

  const [category, product] = await Promise.all([
    prisma.category.findUnique({ where: { id: req.params.id } }),
    prisma.product.findUnique({ where: { id: productId } }),
  ]);

  if (!category) return res.status(404).json({ error: 'Category not found' });
  if (!product) return res.status(404).json({ error: 'Product not found' });

  // If setting as primary, unset other primaries first
  if (isPrimary) {
    await prisma.productCategory.updateMany({
      where: { productId, isPrimary: true },
      data: { isPrimary: false },
    });
  }

  try {
    const association = await prisma.productCategory.create({
      data: {
        categoryId: req.params.id,
        productId,
        isPrimary: isPrimary ?? false,
      },
      include: {
        category: { select: { id: true, name: true, slug: true } },
        product: { select: { id: true, sku: true, name: true } },
      },
    });
    res.status(201).json(association);
  } catch (error: unknown) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'P2002') {
      return res.status(409).json({ error: 'Product already in this category' });
    }
    throw error;
  }
});

// Remove product from category
router.delete('/:id/products/:productId', async (req: Request, res: Response) => {
  const association = await prisma.productCategory.findFirst({
    where: { categoryId: req.params.id, productId: req.params.productId },
  });
  if (!association) {
    return res.status(404).json({ error: 'Product not in this category' });
  }

  await prisma.productCategory.delete({ where: { id: association.id } });
  res.status(204).send();
});

export { router as categoriesRouter };
