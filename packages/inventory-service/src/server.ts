import express, { Request, Response, NextFunction } from 'express';
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

const app = express();

// Middleware
app.use(express.json());

// Health check endpoint
app.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    service: 'inventory-service',
    timestamp: new Date().toISOString(),
  });
});

// Mount routes
app.use('/categories', categoriesRouter);
app.use('/locations', locationsRouter);
app.use('/products', productsRouter);
app.use('/stock-items', stockItemsRouter);
app.use('/stock-movements', stockMovementsRouter);
app.use('/vendors', vendorsRouter);
app.use('/vendor-products', vendorProductsRouter);
app.use('/purchase-orders', purchaseOrdersRouter);
app.use('/channel-listings', channelListingsRouter);
app.use('/vendor-contacts', vendorContactsRouter);
app.use('/vendor-addresses', vendorAddressesRouter);
app.use('/vendor-documents', vendorDocumentsRouter);

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
