import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import request from 'supertest';
import { app } from '../server.js';
import { prisma } from '@copio/core';

describe('Products API', () => {
  beforeAll(async () => {
    await prisma.$connect();
  });

  afterAll(async () => {
    await prisma.$disconnect();
  });

  beforeEach(async () => {
    await prisma.stockItem.deleteMany();
    await prisma.channelListing.deleteMany();
    await prisma.product.deleteMany();
  });

  describe('POST /products', () => {
    it('creates a new product', async () => {
      const response = await request(app)
        .post('/products')
        .send({ name: 'Test Widget', sku: 'TEST-001' });

      expect(response.status).toBe(201);
      expect(response.body.name).toBe('Test Widget');
      expect(response.body.sku).toBe('TEST-001');
      expect(response.body.id).toBeDefined();
    });

    it('creates product with optional fields', async () => {
      const response = await request(app)
        .post('/products')
        .send({
          name: 'Fancy Widget',
          sku: 'FANCY-001',
          brand: 'Acme',
          category: 'Widgets',
        });

      expect(response.status).toBe(201);
      expect(response.body.brand).toBe('Acme');
      expect(response.body.category).toBe('Widgets');
    });

    it('creates product with channel listings', async () => {
      const response = await request(app)
        .post('/products')
        .send({
          name: 'Listed Widget',
          sku: 'LIST-001',
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
        .send({ name: 'No SKU' });

      expect(response.status).toBe(400);
    });

    it('rejects duplicate SKU', async () => {
      await request(app)
        .post('/products')
        .send({ name: 'First', sku: 'DUP-001' });

      const response = await request(app)
        .post('/products')
        .send({ name: 'Second', sku: 'DUP-001' });

      expect(response.status).toBe(409);
    });
  });

  describe('GET /products', () => {
    it('returns all products with listings', async () => {
      await prisma.product.create({
        data: {
          name: 'Product A',
          sku: 'A-001',
          listings: { create: { channel: 'AMAZON', channelSku: 'AMZ-A' } },
        },
      });
      await prisma.product.create({ data: { name: 'Product B', sku: 'B-001' } });

      const response = await request(app).get('/products');

      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(2);
      expect(response.body[0].listings).toBeDefined();
    });

    it('returns empty array when no products', async () => {
      const response = await request(app).get('/products');

      expect(response.status).toBe(200);
      expect(response.body).toEqual([]);
    });
  });

  describe('GET /products/:id', () => {
    it('returns product by id with listings', async () => {
      const product = await prisma.product.create({
        data: {
          name: 'Specific Product',
          sku: 'SPEC-001',
          listings: { create: { channel: 'WALMART', channelSku: 'WMT-001' } },
        },
      });

      const response = await request(app).get(`/products/${product.id}`);

      expect(response.status).toBe(200);
      expect(response.body.name).toBe('Specific Product');
      expect(response.body.listings).toHaveLength(1);
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app).get('/products/unknown-id');

      expect(response.status).toBe(404);
      expect(response.body.error).toBe('Product not found');
    });
  });

  describe('PATCH /products/:id', () => {
    it('updates product fields', async () => {
      const product = await prisma.product.create({
        data: { name: 'Old Name', sku: 'UPD-001' },
      });

      const response = await request(app)
        .patch(`/products/${product.id}`)
        .send({ name: 'New Name', brand: 'New Brand' });

      expect(response.status).toBe(200);
      expect(response.body.name).toBe('New Name');
      expect(response.body.brand).toBe('New Brand');
      expect(response.body.sku).toBe('UPD-001'); // unchanged
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app)
        .patch('/products/unknown-id')
        .send({ name: 'New Name' });

      expect(response.status).toBe(404);
    });

    it('rejects invalid update data', async () => {
      const product = await prisma.product.create({
        data: { name: 'Test', sku: 'VAL-001' },
      });

      const response = await request(app)
        .patch(`/products/${product.id}`)
        .send({ name: '' }); // empty name invalid

      expect(response.status).toBe(400);
    });
  });
});
