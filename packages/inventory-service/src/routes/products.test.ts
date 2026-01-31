import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import { prisma } from '@copio/core';
import { createTestTenant, cleanupTestData, authHeader, type TestUser } from '../test-helpers/auth.js';

describe('Products API', () => {
  let testUser: TestUser;

  beforeAll(async () => {
    await prisma.$connect();
    const { admin } = await createTestTenant({ slug: 'products-test' });
    testUser = admin;
  });

  afterAll(async () => {
    await cleanupTestData();
    await prisma.$disconnect();
  });

  beforeEach(async () => {
    // Clean up products in order due to foreign keys
    await prisma.pOLine.deleteMany();
    await prisma.orderLine.deleteMany();
    await prisma.stockMovement.deleteMany();
    await prisma.stockItem.deleteMany();
    await prisma.channelListing.deleteMany();
    await prisma.vendorProduct.deleteMany();
    await prisma.productCategory.deleteMany();
    await prisma.productAttribute.deleteMany();
    await prisma.productImage.deleteMany();
    await prisma.product.deleteMany();
  });

  describe('POST /products', () => {
    it('creates a new product', async () => {
      const response = await request(app)
        .post('/products')
        .set(authHeader(testUser))
        .send({ name: 'Test Widget', sku: 'TEST-001', tenantId: testUser.tenantId });

      expect(response.status).toBe(201);
      expect(response.body.name).toBe('Test Widget');
      expect(response.body.sku).toBe('TEST-001');
      expect(response.body.id).toBeDefined();
    });

    it('creates product with optional fields', async () => {
      const response = await request(app)
        .post('/products')
        .set(authHeader(testUser))
        .send({
          name: 'Fancy Widget',
          sku: 'FANCY-001',
          brand: 'Acme',
          manufacturer: 'Widgets Inc',
          tenantId: testUser.tenantId,
        });

      expect(response.status).toBe(201);
      expect(response.body.brand).toBe('Acme');
      expect(response.body.manufacturer).toBe('Widgets Inc');
    });

    it('creates product with channel listings', async () => {
      const response = await request(app)
        .post('/products')
        .set(authHeader(testUser))
        .send({
          name: 'Listed Widget',
          sku: 'LIST-001',
          tenantId: testUser.tenantId,
          channelListings: [
            { channel: 'AMAZON', channelSku: 'AMZ-001' },
            { channel: 'SHOPIFY', channelSku: 'SHOP-001' },
          ],
        });

      expect(response.status).toBe(201);
      expect(response.body.listings).toHaveLength(2);
      expect(response.body.listings[0].channel).toBe('AMAZON');
    });

    it('rejects missing required fields', async () => {
      const response = await request(app)
        .post('/products')
        .set(authHeader(testUser))
        .send({ name: 'No SKU' });

      expect(response.status).toBe(400);
    });

    it('rejects duplicate SKU', async () => {
      await request(app)
        .post('/products')
        .set(authHeader(testUser))
        .send({ name: 'First', sku: 'DUP-001', tenantId: testUser.tenantId });

      const response = await request(app)
        .post('/products')
        .set(authHeader(testUser))
        .send({ name: 'Second', sku: 'DUP-001', tenantId: testUser.tenantId });

      expect(response.status).toBe(409);
    });

    it('requires authentication', async () => {
      const response = await request(app)
        .post('/products')
        .send({ name: 'Test', sku: 'AUTH-001' });

      expect(response.status).toBe(401);
    });
  });

  describe('GET /products', () => {
    it('returns all products with listings', async () => {
      await prisma.product.create({
        data: {
          name: 'Product A',
          sku: 'A-001',
          tenantId: testUser.tenantId,
          listings: { create: { channel: 'AMAZON', channelSku: 'AMZ-A' } },
        },
      });
      await prisma.product.create({ 
        data: { name: 'Product B', sku: 'B-001', tenantId: testUser.tenantId } 
      });

      const response = await request(app)
        .get('/products')
        .set(authHeader(testUser));

      expect(response.status).toBe(200);
      expect(response.body.data).toHaveLength(2);
      expect(response.body.data[0].listings).toBeDefined();
      expect(response.body.pagination).toBeDefined();
    });

    it('returns empty array when no products', async () => {
      const response = await request(app)
        .get('/products')
        .set(authHeader(testUser));

      expect(response.status).toBe(200);
      expect(response.body.data).toEqual([]);
      expect(response.body.pagination.total).toBe(0);
    });
  });

  describe('GET /products/:id', () => {
    it('returns product by id with listings', async () => {
      const product = await prisma.product.create({
        data: {
          name: 'Specific Product',
          sku: 'SPEC-001',
          tenantId: testUser.tenantId,
          listings: { create: { channel: 'WALMART', channelSku: 'WMT-001' } },
        },
      });

      const response = await request(app)
        .get(`/products/${product.id}`)
        .set(authHeader(testUser));

      expect(response.status).toBe(200);
      expect(response.body.name).toBe('Specific Product');
      expect(response.body.listings).toHaveLength(1);
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app)
        .get('/products/unknown-id')
        .set(authHeader(testUser));

      expect(response.status).toBe(404);
      expect(response.body.error).toBe('Product not found');
    });
  });

  describe('PATCH /products/:id', () => {
    it('updates product fields', async () => {
      const product = await prisma.product.create({
        data: { name: 'Old Name', sku: 'UPD-001', tenantId: testUser.tenantId },
      });

      const response = await request(app)
        .patch(`/products/${product.id}`)
        .set(authHeader(testUser))
        .send({ name: 'New Name', brand: 'New Brand' });

      expect(response.status).toBe(200);
      expect(response.body.name).toBe('New Name');
      expect(response.body.brand).toBe('New Brand');
      expect(response.body.sku).toBe('UPD-001'); // unchanged
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app)
        .patch('/products/unknown-id')
        .set(authHeader(testUser))
        .send({ name: 'New Name' });

      expect(response.status).toBe(404);
    });

    it('rejects invalid update data', async () => {
      const product = await prisma.product.create({
        data: { name: 'Test', sku: 'VAL-001', tenantId: testUser.tenantId },
      });

      const response = await request(app)
        .patch(`/products/${product.id}`)
        .set(authHeader(testUser))
        .send({ name: '' }); // empty name invalid

      expect(response.status).toBe(400);
    });
  });
});
