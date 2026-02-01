/**
 * Test helpers for authentication
 * 
 * Creates test tenants, users, and JWT tokens for use in tests.
 */

import * as jose from 'jose';
import { prisma } from '@copio/core';
import { randomUUID } from 'crypto';

const JWT_SECRET = process.env.JWT_SECRET || 'CHANGE-ME-IN-PRODUCTION';
const secret = new TextEncoder().encode(JWT_SECRET);

export interface TestUser {
  id: string;
  email: string;
  tenantId: string;
  role: 'admin' | 'member';
  token: string;
}

export interface TestTenant {
  id: string;
  name: string;
  slug: string;
}

/**
 * Create a test tenant with an admin user.
 * Returns both tenant info and a valid JWT token.
 */
export async function createTestTenant(
  options: { slug?: string; name?: string } = {}
): Promise<{ tenant: TestTenant; admin: TestUser }> {
  const slug = options.slug || `test-${randomUUID().slice(0, 8)}`;
  const name = options.name || `Test Tenant ${slug}`;
  
  // Create tenant
  const tenant = await prisma.tenants.create({
    data: {
      id: randomUUID(),
      name,
      slug,
    },
  });
  
  // Create admin user
  const userId = randomUUID();
  const email = `admin-${slug}@test.com`;
  
  await prisma.users.create({
    data: {
      id: userId,
      email,
      hashed_password: 'test-password-hash', // Not used in tests
      tenant_id: tenant.id,
      role: 'admin',
      is_active: true,
      is_verified: true,
    },
  });
  
  // Generate JWT token
  const token = await generateToken(userId);
  
  return {
    tenant: {
      id: tenant.id,
      name: tenant.name,
      slug: tenant.slug,
    },
    admin: {
      id: userId,
      email,
      tenantId: tenant.id,
      role: 'admin',
      token,
    },
  };
}

/**
 * Create a member user in an existing tenant.
 */
export async function createTestUser(
  tenantId: string,
  options: { role?: 'admin' | 'member'; email?: string } = {}
): Promise<TestUser> {
  const userId = randomUUID();
  const email = options.email || `user-${randomUUID().slice(0, 8)}@test.com`;
  const role = options.role || 'member';
  
  await prisma.users.create({
    data: {
      id: userId,
      email,
      hashed_password: 'test-password-hash',
      tenant_id: tenantId,
      role,
      is_active: true,
      is_verified: true,
    },
  });
  
  const token = await generateToken(userId);
  
  return {
    id: userId,
    email,
    tenantId,
    role,
    token,
  };
}

/**
 * Generate a valid JWT token for a user.
 */
export async function generateToken(userId: string): Promise<string> {
  const token = await new jose.SignJWT({ sub: userId })
    .setProtectedHeader({ alg: 'HS256' })
    .setAudience('fastapi-users:auth')
    .setIssuedAt()
    .setExpirationTime('24h')
    .sign(secret);
  
  return token;
}

/**
 * Clean up all test data from the database.
 * Call this in afterEach or afterAll hooks.
 */
export async function cleanupTestData(): Promise<void> {
  // Delete in correct order due to foreign key constraints
  await prisma.pOLine.deleteMany();
  await prisma.orderLine.deleteMany();
  await prisma.stockMovement.deleteMany();
  await prisma.stockItem.deleteMany();
  await prisma.channelListing.deleteMany();
  await prisma.vendorProduct.deleteMany();
  await prisma.vendorDocument.deleteMany();
  await prisma.vendorContact.deleteMany();
  await prisma.vendorAddress.deleteMany();
  await prisma.purchaseOrder.deleteMany();
  await prisma.productCategory.deleteMany();
  await prisma.productAttribute.deleteMany();
  await prisma.productImage.deleteMany();
  await prisma.product.deleteMany();
  await prisma.vendor.deleteMany();
  await prisma.category.deleteMany();
  await prisma.location.deleteMany();
  await prisma.users.deleteMany();
  await prisma.tenants.deleteMany();
}

/**
 * Get auth header for a test user.
 */
export function authHeader(user: TestUser): { Authorization: string } {
  return { Authorization: `Bearer ${user.token}` };
}
