import express, { Request, Response, NextFunction, Router } from 'express';
import cors from 'cors';
import { categoriesRouter } from './routes/categories.js';
import { locationsRouter } from './routes/locations.js';
import { productsRouter } from './routes/products.js';
import { stockItemsRouter } from './routes/stock-items.js';
import { stockMovementsRouter } from './routes/stock-movements.js';
import { vendorsRouter } from './routes/vendors.js';
import { vendorProductsRouter } from './routes/vendor-products.js';
import { purchaseOrdersRouter } from './routes/purchase-orders.js';
import { channelListingsRouter } from './routes/channel-listings.js';
import { vendorContactsRouter } from './routes/vendor-contacts.js';
import { vendorAddressesRouter } from './routes/vendor-addresses.js';
import { vendorDocumentsRouter } from './routes/vendor-documents.js';
import { requireAuth } from './middleware/auth.js';

const app = express();
const apiRouter = Router();

// Middleware
app.use(cors({
  origin: ['http://localhost:3000', 'http://localhost:3001', 'http://127.0.0.1:3000', 'http://127.0.0.1:3001'],
  credentials: true,
}));
app.use(express.json());

// Health check endpoint - no auth required
app.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    service: 'inventory-service',
    timestamp: new Date().toISOString(),
  });
});

// Auth check endpoint (requires valid JWT)
apiRouter.get('/me', requireAuth, (req: Request, res: Response) => {
  res.json({
    userId: req.user?.id,
    tenantId: req.user?.tenantId,
  });
});

// All protected routes require authentication
apiRouter.use('/categories', requireAuth, categoriesRouter);
apiRouter.use('/locations', requireAuth, locationsRouter);
apiRouter.use('/products', requireAuth, productsRouter);
apiRouter.use('/stock-items', requireAuth, stockItemsRouter);
apiRouter.use('/stock-movements', requireAuth, stockMovementsRouter);
apiRouter.use('/vendors', requireAuth, vendorsRouter);
apiRouter.use('/vendor-products', requireAuth, vendorProductsRouter);
apiRouter.use('/purchase-orders', requireAuth, purchaseOrdersRouter);
apiRouter.use('/channel-listings', requireAuth, channelListingsRouter);
apiRouter.use('/vendor-contacts', requireAuth, vendorContactsRouter);
apiRouter.use('/vendor-addresses', requireAuth, vendorAddressesRouter);
apiRouter.use('/vendor-documents', requireAuth, vendorDocumentsRouter);

// Mount API router at /api/v1
app.use('/api/v1', apiRouter);

// Error handler
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('Error:', err.message);
  res.status(500).json({
    error: 'Internal Server Error',
    message: process.env.NODE_ENV === 'development' ? err.message : undefined,
  });
});

// 404 handler
app.use((_req: Request, res: Response) => {
  res.status(404).json({ error: 'Not Found' });
});

export { app };
