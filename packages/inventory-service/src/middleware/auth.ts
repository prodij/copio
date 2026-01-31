/**
 * JWT Authentication Middleware
 * 
 * Validates JWT tokens from the Python auth service and extracts user/tenant info.
 * Compatible with fastapi-users token format.
 */

import { Request, Response, NextFunction } from 'express';
import * as jose from 'jose';

// User roles
export type UserRole = 'admin' | 'member';

// Extend Express Request to include auth info
declare global {
  namespace Express {
    interface Request {
      user?: {
        id: string;
        tenantId: string;
        role: UserRole;
      };
      tenantId?: string;
    }
  }
}

// Get secret from environment (must match Python API secret_key)
const JWT_SECRET = process.env.JWT_SECRET || 'CHANGE-ME-IN-PRODUCTION';
const secret = new TextEncoder().encode(JWT_SECRET);

/**
 * Middleware that requires authentication.
 * Returns 401 if no valid token is provided.
 */
export async function requireAuth(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const authHeader = req.headers.authorization;
  
  if (!authHeader?.startsWith('Bearer ')) {
    res.status(401).json({ error: 'Missing authorization header' });
    return;
  }

  const token = authHeader.substring(7);
  
  try {
    const { payload } = await jose.jwtVerify(token, secret, {
      audience: 'fastapi-users:auth',
    });
    
    // fastapi-users puts user_id in 'sub' claim
    const userId = payload.sub as string;
    
    if (!userId) {
      res.status(401).json({ error: 'Invalid token: missing user ID' });
      return;
    }

    // Look up the user to get tenant_id and role
    // In a future optimization, we could include these in the JWT claims
    const { prisma } = await import('@copio/core');
    const user = await prisma.users.findUnique({
      where: { id: userId },
      select: { id: true, tenant_id: true, role: true, is_active: true },
    });

    if (!user) {
      res.status(401).json({ error: 'User not found' });
      return;
    }

    if (!user.is_active) {
      res.status(401).json({ error: 'Account is inactive' });
      return;
    }

    // Attach user info to request
    req.user = {
      id: user.id,
      tenantId: user.tenant_id,
      role: user.role as UserRole,
    };
    req.tenantId = user.tenant_id;
    
    next();
  } catch (err) {
    if (err instanceof jose.errors.JWTExpired) {
      res.status(401).json({ error: 'Token expired' });
      return;
    }
    if (err instanceof jose.errors.JWSSignatureVerificationFailed) {
      res.status(401).json({ error: 'Invalid token signature' });
      return;
    }
    console.error('Auth error:', err);
    res.status(401).json({ error: 'Invalid token' });
  }
}

/**
 * Optional auth middleware.
 * Attaches user info if valid token is provided, but doesn't require it.
 * Useful for endpoints that work differently for authenticated vs anonymous users.
 */
export async function optionalAuth(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const authHeader = req.headers.authorization;
  
  if (!authHeader?.startsWith('Bearer ')) {
    next();
    return;
  }

  // Try to validate, but don't fail if invalid
  try {
    const token = authHeader.substring(7);
    const { payload } = await jose.jwtVerify(token, secret, {
      audience: 'fastapi-users:auth',
    });
    
    const userId = payload.sub as string;
    if (userId) {
      const { prisma } = await import('@copio/core');
      const user = await prisma.users.findUnique({
        where: { id: userId },
        select: { id: true, tenant_id: true, role: true, is_active: true },
      });
      
      if (user && user.is_active) {
        req.user = {
          id: user.id,
          tenantId: user.tenant_id,
          role: user.role as UserRole,
        };
        req.tenantId = user.tenant_id;
      }
    }
  } catch {
    // Ignore auth errors for optional auth
  }
  
  next();
}

/**
 * Middleware factory that requires specific roles.
 * Must be used after requireAuth.
 * 
 * Usage:
 *   router.post('/admin-only', requireAuth, requireRole(['admin']), handler);
 */
export function requireRole(allowedRoles: UserRole[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    if (!req.user) {
      res.status(401).json({ error: 'Authentication required' });
      return;
    }

    if (!allowedRoles.includes(req.user.role)) {
      res.status(403).json({ error: 'Insufficient permissions' });
      return;
    }

    next();
  };
}
