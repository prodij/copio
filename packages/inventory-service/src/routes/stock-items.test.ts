import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import { prisma } from '@copio/core';
import { createTestTenant, cleanupTestData, authHeader, type TestUser } from '../test-helpers/auth.js';

describe('StockItems API', () => {
  let testUser: TestUser;
  let testProduct: { id: string };
  let testLocation: { id: string };
  let testLocation2: { id: string };

  beforeAll(async () => {
    await prisma.$connect();
    const { admin } = await createTestTenant({ slug: 'stock-items-test' });
    testUser = admin;
  });

  afterAll(async () => {
    await cleanupTestData();
    await prisma.$disconnect();
  });

  beforeEach(async () => {
    // Clean up in order due to foreign keys
    await prisma.pOLine.deleteMany();
    await prisma.purchaseOrder.deleteMany();
    await prisma.orderLine.deleteMany();
    await prisma.stockMovement.deleteMany();
    await prisma.stockItem.deleteMany();
    await prisma.channelListing.deleteMany();
    await prisma.vendorProduct.deleteMany();
    await prisma.productCategory.deleteMany();
    await prisma.productAttribute.deleteMany();
    await prisma.productImage.deleteMany();
    await prisma.product.deleteMany();
    await prisma.location.deleteMany();

    // Create test fixtures
    testProduct = await prisma.product.create({
      data: { sku: 'TEST-SKU-001', name: 'Test Product', tenantId: testUser.tenantId },
    });
    testLocation = await prisma.location.create({
      data: { name: 'Warehouse A', type: 'WAREHOUSE', tenantId: testUser.tenantId },
    });
    testLocation2 = await prisma.location.create({
      data: { name: 'Warehouse B', type: 'WAREHOUSE', tenantId: testUser.tenantId },
    });
  });

  describe('POST /stock-items', () => {
    it('creates a new stock item', async () => {
      const response = await request(app)
        .post('/stock-items')
        .set(authHeader(testUser))
        .send({
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
          tenantId: testUser.tenantId,
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
        .set(authHeader(testUser))
        .send({
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 50,
          quantityReserved: 10,
          quantityInbound: 25,
          costBasis: 19.99,
          tenantId: testUser.tenantId,
        });

      expect(response.status).toBe(201);
      expect(response.body.quantityReserved).toBe(10);
      expect(response.body.quantityInbound).toBe(25);
      expect(response.body.costBasis).toBe('19.99');
    });

    it('rejects missing required fields', async () => {
      const response = await request(app)
        .post('/stock-items')
        .set(authHeader(testUser))
        .send({ productId: testProduct.id });

      expect(response.status).toBe(400);
    });

    it('rejects invalid productId', async () => {
      const response = await request(app)
        .post('/stock-items')
        .set(authHeader(testUser))
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
          tenantId: testUser.tenantId,
        },
      });

      const response = await request(app)
        .post('/stock-items')
        .set(authHeader(testUser))
        .send({
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
          tenantId: testUser.tenantId,
        });

      expect(response.status).toBe(409);
    });

    it('requires authentication', async () => {
      const response = await request(app)
        .post('/stock-items')
        .send({
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
        });

      expect(response.status).toBe(401);
    });
  });

  describe('GET /stock-items', () => {
    it('returns all stock items with product and location', async () => {
      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
          tenantId: testUser.tenantId,
        },
      });

      const response = await request(app)
        .get('/stock-items')
        .set(authHeader(testUser));
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(1);
      expect(response.body[0].product).toBeDefined();
      expect(response.body[0].product.sku).toBe('TEST-SKU-001');
      expect(response.body[0].location).toBeDefined();
      expect(response.body[0].location.name).toBe('Warehouse A');
    });

    it('returns empty array when no stock items exist', async () => {
      const response = await request(app)
        .get('/stock-items')
        .set(authHeader(testUser));
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
          tenantId: testUser.tenantId,
        },
      });

      const response = await request(app)
        .get(`/stock-items/${stockItem.id}`)
        .set(authHeader(testUser));
      expect(response.status).toBe(200);
      expect(response.body.quantityAvailable).toBe(75);
      expect(response.body.product).toBeDefined();
      expect(response.body.location).toBeDefined();
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app)
        .get('/stock-items/unknown-id')
        .set(authHeader(testUser));
      expect(response.status).toBe(404);
    });
  });

  describe('GET /stock-items/by-location/:locationId', () => {
    it('returns all stock at a location', async () => {
      const product2 = await prisma.product.create({
        data: { sku: 'TEST-SKU-002', name: 'Product 2', tenantId: testUser.tenantId },
      });

      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation.id,
          quantityAvailable: 100,
          tenantId: testUser.tenantId,
        },
      });
      await prisma.stockItem.create({
        data: {
          productId: product2.id,
          locationId: testLocation.id,
          quantityAvailable: 50,
          tenantId: testUser.tenantId,
        },
      });
      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation2.id,
          quantityAvailable: 25,
          tenantId: testUser.tenantId,
        },
      });

      const response = await request(app)
        .get(`/stock-items/by-location/${testLocation.id}`)
        .set(authHeader(testUser));
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(2);
      expect(response.body[0].product).toBeDefined();
    });

    it('returns empty array for location with no stock', async () => {
      const response = await request(app)
        .get(`/stock-items/by-location/${testLocation.id}`)
        .set(authHeader(testUser));
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
          tenantId: testUser.tenantId,
        },
      });
      await prisma.stockItem.create({
        data: {
          productId: testProduct.id,
          locationId: testLocation2.id,
          quantityAvailable: 50,
          tenantId: testUser.tenantId,
        },
      });

      const response = await request(app)
        .get(`/stock-items/by-product/${testProduct.id}`)
        .set(authHeader(testUser));
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(2);
      expect(response.body[0].location).toBeDefined();
    });

    it('returns empty array for product with no stock', async () => {
      const response = await request(app)
        .get(`/stock-items/by-product/${testProduct.id}`)
        .set(authHeader(testUser));
      expect(response.status).toBe(200);
      expect(response.body).toEqual([]);
    });
  });
});
