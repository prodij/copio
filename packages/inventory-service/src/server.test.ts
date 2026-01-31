import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import request from 'supertest';
import { app } from './server.js';
import { prisma } from '@copio/core';
import { createTestTenant, cleanupTestData, authHeader, type TestUser } from './test-helpers/auth.js';

describe('Inventory Service', () => {
  describe('GET /health', () => {
    it('returns healthy status without auth', async () => {
      const response = await request(app).get('/health');
      expect(response.status).toBe(200);
      expect(response.body.status).toBe('healthy');
    });
  });

  describe('GET /me', () => {
    let testUser: TestUser;

    beforeAll(async () => {
      await prisma.$connect();
      const { admin } = await createTestTenant({ slug: 'me-test' });
      testUser = admin;
    });

    afterAll(async () => {
      await cleanupTestData();
      await prisma.$disconnect();
    });

    it('returns user info with valid token', async () => {
      const response = await request(app)
        .get('/me')
        .set(authHeader(testUser));
      expect(response.status).toBe(200);
      expect(response.body.userId).toBe(testUser.id);
      expect(response.body.tenantId).toBe(testUser.tenantId);
    });

    it('returns 401 without token', async () => {
      const response = await request(app).get('/me');
      expect(response.status).toBe(401);
    });

    it('returns 401 with invalid token', async () => {
      const response = await request(app)
        .get('/me')
        .set('Authorization', 'Bearer invalid-token');
      expect(response.status).toBe(401);
    });
  });
});

describe('Locations API', () => {
  let testUser: TestUser;

  beforeAll(async () => {
    await prisma.$connect();
    const { admin } = await createTestTenant({ slug: 'locations-test' });
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
    await prisma.stockMovement.deleteMany();
    await prisma.stockItem.deleteMany();
    await prisma.location.deleteMany();
  });

  describe('POST /locations', () => {
    it('creates a new location', async () => {
      const response = await request(app)
        .post('/locations')
        .set(authHeader(testUser))
        .send({ name: 'Main Warehouse', type: 'WAREHOUSE', tenantId: testUser.tenantId });

      expect(response.status).toBe(201);
      expect(response.body.name).toBe('Main Warehouse');
      expect(response.body.type).toBe('WAREHOUSE');
      expect(response.body.id).toBeDefined();
    });

    it('rejects invalid location type', async () => {
      const response = await request(app)
        .post('/locations')
        .set(authHeader(testUser))
        .send({ name: 'Bad Location', type: 'INVALID' });

      expect(response.status).toBe(400);
    });

    it('requires authentication', async () => {
      const response = await request(app)
        .post('/locations')
        .send({ name: 'Test', type: 'WAREHOUSE' });

      expect(response.status).toBe(401);
    });
  });

  describe('GET /locations', () => {
    it('returns all locations', async () => {
      await prisma.location.create({ 
        data: { name: 'Warehouse A', type: 'WAREHOUSE', tenantId: testUser.tenantId } 
      });
      await prisma.location.create({ 
        data: { name: 'FBA East', type: 'FBA', channel: 'AMAZON', tenantId: testUser.tenantId } 
      });

      const response = await request(app)
        .get('/locations')
        .set(authHeader(testUser));
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(2);
    });
  });

  describe('GET /locations/:id', () => {
    it('returns location by id', async () => {
      const loc = await prisma.location.create({ 
        data: { name: 'Test', type: 'WAREHOUSE', tenantId: testUser.tenantId } 
      });
      const response = await request(app)
        .get(`/locations/${loc.id}`)
        .set(authHeader(testUser));
      expect(response.status).toBe(200);
      expect(response.body.name).toBe('Test');
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app)
        .get('/locations/unknown-id')
        .set(authHeader(testUser));
      expect(response.status).toBe(404);
    });
  });
});
