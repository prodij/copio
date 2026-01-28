import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import request from 'supertest';
import { app } from './server.js';
import { prisma } from '@copio/core';

describe('Inventory Service', () => {
  describe('GET /health', () => {
    it('returns healthy status', async () => {
      const response = await request(app).get('/health');
      expect(response.status).toBe(200);
      expect(response.body.status).toBe('healthy');
    });
  });
});

describe('Locations API', () => {
  beforeAll(async () => {
    await prisma.$connect();
  });

  afterAll(async () => {
    await prisma.$disconnect();
  });

  beforeEach(async () => {
    await prisma.location.deleteMany();
  });

  describe('POST /locations', () => {
    it('creates a new location', async () => {
      const response = await request(app)
        .post('/locations')
        .send({ name: 'Main Warehouse', type: 'WAREHOUSE' });

      expect(response.status).toBe(201);
      expect(response.body.name).toBe('Main Warehouse');
      expect(response.body.type).toBe('WAREHOUSE');
      expect(response.body.id).toBeDefined();
    });

    it('rejects invalid location type', async () => {
      const response = await request(app)
        .post('/locations')
        .send({ name: 'Bad Location', type: 'INVALID' });

      expect(response.status).toBe(400);
    });
  });

  describe('GET /locations', () => {
    it('returns all locations', async () => {
      await prisma.location.create({ data: { name: 'Warehouse A', type: 'WAREHOUSE' } });
      await prisma.location.create({ data: { name: 'FBA East', type: 'FBA', channel: 'AMAZON' } });

      const response = await request(app).get('/locations');
      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(2);
    });
  });

  describe('GET /locations/:id', () => {
    it('returns location by id', async () => {
      const loc = await prisma.location.create({ data: { name: 'Test', type: 'WAREHOUSE' } });
      const response = await request(app).get(`/locations/${loc.id}`);
      expect(response.status).toBe(200);
      expect(response.body.name).toBe('Test');
    });

    it('returns 404 for unknown id', async () => {
      const response = await request(app).get('/locations/unknown-id');
      expect(response.status).toBe(404);
    });
  });
});
