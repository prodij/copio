import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import { prisma } from '@copio/core';

describe('StockMovements API', () => {
  let testProduct: { id: string };
  let testLocation: { id: string };
  let testLocation2: { id: string };
  let testStockItem: { id: string };
  let testStockItem2: { id: string };

  beforeAll(async () => {
    await prisma.$connect();
  });

  afterAll(async () => {
    await prisma.$disconnect();
  });

  beforeEach(async () => {
    // Clean up in order due to foreign keys
    await prisma.stockMovement.deleteMany();
    await prisma.stockItem.deleteMany();
    await prisma.channelListing.deleteMany();
    await prisma.product.deleteMany();
    await prisma.location.deleteMany();

    // Create test fixtures
    testProduct = await prisma.product.create({
      data: { sku: 'TEST-SKU-001', name: 'Test Product' },
    });
    testLocation = await prisma.location.create({
      data: { name: 'Warehouse A', type: 'WAREHOUSE' },
    });
    testLocation2 = await prisma.location.create({
      data: { name: 'Warehouse B', type: 'WAREHOUSE' },
    });
    testStockItem = await prisma.stockItem.create({
      data: {
        productId: testProduct.id,
        locationId: testLocation.id,
        quantityAvailable: 100,
      },
    });
    testStockItem2 = await prisma.stockItem.create({
      data: {
        productId: testProduct.id,
        locationId: testLocation2.id,
        quantityAvailable: 50,
      },
    });
  });

  describe('POST /stock-movements', () => {
    describe('RECEIVE movements', () => {
      it('creates a RECEIVE movement and adds to stock quantity', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'RECEIVE',
            quantity: 25,
            notes: 'PO-123 received',
          });

        expect(response.status).toBe(201);
        expect(response.body.type).toBe('RECEIVE');
        expect(response.body.quantity).toBe(25);
        expect(response.body.notes).toBe('PO-123 received');

        // Verify stock was updated
        const stockItem = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(stockItem?.quantityAvailable).toBe(125); // 100 + 25
      });
    });

    describe('SHIP movements', () => {
      it('creates a SHIP movement and subtracts from stock quantity', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'SHIP',
            quantity: 30,
            reference: 'ORDER-456',
          });

        expect(response.status).toBe(201);
        expect(response.body.type).toBe('SHIP');
        expect(response.body.quantity).toBe(30);

        // Verify stock was updated
        const stockItem = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(stockItem?.quantityAvailable).toBe(70); // 100 - 30
      });

      it('fails SHIP when insufficient stock', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'SHIP',
            quantity: 150, // More than available (100)
          });

        expect(response.status).toBe(400);
        expect(response.body.error).toContain('Insufficient stock');

        // Verify stock was NOT updated
        const stockItem = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(stockItem?.quantityAvailable).toBe(100);
      });

      it('allows SHIP of exact available quantity', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'SHIP',
            quantity: 100,
          });

        expect(response.status).toBe(201);

        const stockItem = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(stockItem?.quantityAvailable).toBe(0);
      });
    });

    describe('ADJUST movements', () => {
      it('creates an ADJUST movement and sets stock to exact quantity', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'ADJUST',
            quantity: 75, // New total
            notes: 'Cycle count correction',
          });

        expect(response.status).toBe(201);
        expect(response.body.type).toBe('ADJUST');
        // The movement quantity is the delta
        expect(response.body.quantity).toBe(-25); // 75 - 100 = -25

        // Verify stock was set to exact value
        const stockItem = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(stockItem?.quantityAvailable).toBe(75);
      });

      it('handles ADJUST to increase stock', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'ADJUST',
            quantity: 150,
          });

        expect(response.status).toBe(201);
        expect(response.body.quantity).toBe(50); // 150 - 100 = +50

        const stockItem = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(stockItem?.quantityAvailable).toBe(150);
      });

      it('handles ADJUST to zero', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'ADJUST',
            quantity: 0,
          });

        expect(response.status).toBe(201);

        const stockItem = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(stockItem?.quantityAvailable).toBe(0);
      });
    });

    describe('TRANSFER movements', () => {
      it('creates paired movements for TRANSFER', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'TRANSFER',
            quantity: 20,
            destinationStockItemId: testStockItem2.id,
            notes: 'Rebalancing inventory',
          });

        expect(response.status).toBe(201);
        // Response includes both movements
        expect(response.body.sourceMovement).toBeDefined();
        expect(response.body.destinationMovement).toBeDefined();
        expect(response.body.sourceMovement.quantity).toBe(-20);
        expect(response.body.destinationMovement.quantity).toBe(20);

        // Verify source stock decreased
        const sourceStock = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(sourceStock?.quantityAvailable).toBe(80); // 100 - 20

        // Verify destination stock increased
        const destStock = await prisma.stockItem.findUnique({
          where: { id: testStockItem2.id },
        });
        expect(destStock?.quantityAvailable).toBe(70); // 50 + 20
      });

      it('fails TRANSFER when insufficient stock at source', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'TRANSFER',
            quantity: 150,
            destinationStockItemId: testStockItem2.id,
          });

        expect(response.status).toBe(400);
        expect(response.body.error).toContain('Insufficient stock');

        // Verify neither stock was changed
        const sourceStock = await prisma.stockItem.findUnique({
          where: { id: testStockItem.id },
        });
        expect(sourceStock?.quantityAvailable).toBe(100);

        const destStock = await prisma.stockItem.findUnique({
          where: { id: testStockItem2.id },
        });
        expect(destStock?.quantityAvailable).toBe(50);
      });

      it('requires destinationStockItemId for TRANSFER', async () => {
        const response = await request(app)
          .post('/stock-movements')
          .send({
            stockItemId: testStockItem.id,
            type: 'TRANSFER',
            quantity: 20,
          });

        expect(response.status).toBe(400);
        expect(response.body.error).toBeDefined();
      });
    });

    it('rejects invalid stockItemId', async () => {
      const response = await request(app)
        .post('/stock-movements')
        .send({
          stockItemId: 'nonexistent-id',
          type: 'RECEIVE',
          quantity: 10,
        });

      expect(response.status).toBe(404);
      expect(response.body.error).toContain('Stock item not found');
    });

    it('rejects invalid movement type', async () => {
      const response = await request(app)
        .post('/stock-movements')
        .send({
          stockItemId: testStockItem.id,
          type: 'INVALID',
          quantity: 10,
        });

      expect(response.status).toBe(400);
    });

    it('rejects negative quantity for non-ADJUST types', async () => {
      const response = await request(app)
        .post('/stock-movements')
        .send({
          stockItemId: testStockItem.id,
          type: 'RECEIVE',
          quantity: -10,
        });

      expect(response.status).toBe(400);
    });
  });

  describe('GET /stock-movements', () => {
    beforeEach(async () => {
      // Create some movements
      await prisma.stockMovement.createMany({
        data: [
          { stockItemId: testStockItem.id, type: 'RECEIVE', quantity: 50 },
          { stockItemId: testStockItem.id, type: 'SHIP', quantity: 10 },
          { stockItemId: testStockItem2.id, type: 'RECEIVE', quantity: 25 },
        ],
      });
    });

    it('returns all movements', async () => {
      const response = await request(app).get('/stock-movements');
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(3);
    });

    it('filters by stockItemId', async () => {
      const response = await request(app)
        .get('/stock-movements')
        .query({ stockItemId: testStockItem.id });

      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(2);
      expect(response.body.every((m: { stockItemId: string }) => m.stockItemId === testStockItem.id)).toBe(true);
    });

    it('returns empty array when no movements exist', async () => {
      await prisma.stockMovement.deleteMany();
      const response = await request(app).get('/stock-movements');
      expect(response.status).toBe(200);
      expect(response.body).toEqual([]);
    });

    it('includes stockItem relation', async () => {
      const response = await request(app).get('/stock-movements');
      expect(response.status).toBe(200);
      expect(response.body[0].stockItem).toBeDefined();
    });
  });

  describe('GET /stock-movements/:id', () => {
    it('returns movement by id', async () => {
      const movement = await prisma.stockMovement.create({
        data: {
          stockItemId: testStockItem.id,
          type: 'RECEIVE',
          quantity: 100,
          notes: 'Test movement',
        },
      });

      const response = await request(app).get(`/stock-movements/${movement.id}`);
      expect(response.status).toBe(200);
      expect(response.body.id).toBe(movement.id);
      expect(response.body.quantity).toBe(100);
      expect(response.body.notes).toBe('Test movement');
      expect(response.body.stockItem).toBeDefined();
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app).get('/stock-movements/unknown-id');
      expect(response.status).toBe(404);
    });
  });
});
