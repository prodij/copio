import express, { Request, Response, NextFunction } from 'express';
import { locationsRouter } from './routes/locations.js';
import { productsRouter } from './routes/products.js';
import { stockItemsRouter } from './routes/stock-items.js';

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
app.use('/locations', locationsRouter);
app.use('/products', productsRouter);
app.use('/stock-items', stockItemsRouter);

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
