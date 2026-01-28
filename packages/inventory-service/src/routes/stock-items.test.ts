import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import { prisma } from '@copio/core';

describe('StockItems API', () => {
  let testProduct: { id: string };
  let testLocation: { id: string };
  let testLocation2: { id: string };

  beforeAll(async () => {
    await prisma.$connect();
  });

  afterAll(async () => {
    await prisma.$disconnect();
  });

  beforeEach(async () => {
    // Clean up in order due to foreign keys
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
  });

  describe('POST /stock-items', () => {
    it('creates a new stock item', async () => {
      const response = await request(app)
        .post('/stock-items')
        .send({
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
        });

      expect(response.status).toBe(201);
      expect(response.body.productId).toBe(testProduct.id);
      expect(response.body.locationId).toBe(testLocation.id);
      expect(response.body.quantityAvailable).toBe(100);
      expect(response.body.id).toBeDefined();
    });

    it('creates stock item with optional fields', async () => {
      const response = await request(app)
        .post('/stock-items')
        .send({
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 50,
          quantityReserved: 10,
          quantityInbound: 25,
          costBasis: 19.99,
        });

      expect(response.status).toBe(201);
      expect(response.body.quantityReserved).toBe(10);
      expect(response.body.quantityInbound).toBe(25);
      expect(response.body.costBasis).toBe('19.99');
    });

    it('rejects missing required fields', async () => {
      const response = await request(app)
        .post('/stock-items')
        .send({ productId: testProduct.id });

      expect(response.status).toBe(400);
    });

    it('rejects invalid productId', async () => {
      const response = await request(app)
        .post('/stock-items')
        .send({
          productId: 'nonexistent-id',
          locationId: testLocation.id,
          quantityAvailable: 10,
        });

      expect(response.status).toBe(400);
    });

    it('rejects duplicate product-location combination', async () => {
      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 50,
        },
      });

      const response = await request(app)
        .post('/stock-items')
        .send({
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
        });

      expect(response.status).toBe(409);
    });
  });

  describe('GET /stock-items', () => {
    it('returns all stock items with product and location', async () => {
      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
        },
      });

      const response = await request(app).get('/stock-items');
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(1);
      expect(response.body[0].product).toBeDefined();
      expect(response.body[0].product.sku).toBe('TEST-SKU-001');
      expect(response.body[0].location).toBeDefined();
      expect(response.body[0].location.name).toBe('Warehouse A');
    });

    it('returns empty array when no stock items exist', async () => {
      const response = await request(app).get('/stock-items');
      expect(response.status).toBe(200);
      expect(response.body).toEqual([]);
    });
  });

  describe('GET /stock-items/:id', () => {
    it('returns stock item by id', async () => {
      const stockItem = await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 75,
        },
      });

      const response = await request(app).get(`/stock-items/${stockItem.id}`);
      expect(response.status).toBe(200);
      expect(response.body.quantityAvailable).toBe(75);
      expect(response.body.product).toBeDefined();
      expect(response.body.location).toBeDefined();
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app).get('/stock-items/unknown-id');
      expect(response.status).toBe(404);
    });
  });

  describe('GET /stock-items/by-location/:locationId', () => {
    it('returns all stock at a location', async () => {
      const product2 = await prisma.product.create({
        data: { sku: 'TEST-SKU-002', name: 'Product 2' },
      });

      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
        },
      });
      await prisma.stockItem.create({
        data: {
          productId: product2.id,
          locationId: testLocation.id,
          quantityAvailable: 50,
        },
      });
      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation2.id,
          quantityAvailable: 25,
        },
      });

      const response = await request(app).get(`/stock-items/by-location/${testLocation.id}`);
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(2);
      expect(response.body[0].product).toBeDefined();
    });

    it('returns empty array for location with no stock', async () => {
      const response = await request(app).get(`/stock-items/by-location/${testLocation.id}`);
      expect(response.status).toBe(200);
      expect(response.body).toEqual([]);
    });
  });

  describe('GET /stock-items/by-product/:productId', () => {
    it('returns all stock of a product across locations', async () => {
      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
        },
      });
      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation2.id,
          quantityAvailable: 50,
        },
      });

      const response = await request(app).get(`/stock-items/by-product/${testProduct.id}`);
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(2);
      expect(response.body[0].location).toBeDefined();
    });

    it('returns empty array for product with no stock', async () => {
      const response = await request(app).get(`/stock-items/by-product/${testProduct.id}`);
      expect(response.status).toBe(200);
      expect(response.body).toEqual([]);
    });
  });
});
