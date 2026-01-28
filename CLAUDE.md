# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Copio is a multi-marketplace seller ERP with real-time inventory sync. It's a pnpm monorepo with three packages:
- **@copio/core** - Shared Prisma database models and TypeScript types
- **@copio/inventory-service** - Express.js REST API (port 3001)
- **@copio/web** - Next.js 16 frontend (port 3000)

## Development Commands

```bash
# Start everything (requires Docker for Postgres/Redis)
docker compose up -d
pnpm install
pnpm db:push        # Push schema to database
pnpm dev            # Run all services in dev mode

# Testing (inventory-service only)
pnpm test                                    # Run all tests
pnpm --filter @copio/inventory-service test  # Run inventory tests
pnpm --filter @copio/inventory-service test:watch  # Watch mode

# Database
pnpm db:generate    # Generate Prisma client after schema changes
pnpm db:migrate     # Create and run migrations
pnpm db:studio      # Open Prisma Studio GUI

# Other
pnpm build          # Build all packages
pnpm lint           # Lint (web package)
pnpm typecheck      # TypeScript checking
```

## Architecture

### Data Flow
```
Browser → Next.js (3000) → /api/* proxy → Express API (3001) → PostgreSQL
```

The web package proxies `/api/*` requests to the inventory-service (configured in `next.config.ts`).

### Database (Prisma)
Schema is in `packages/core/prisma/schema.prisma`. Key models:
- **Product** → **ChannelListing** (Amazon, Shopify, Walmart)
- **Location** (WAREHOUSE, FBA, THREEPEL) → **StockItem** (inventory per location)
- **StockMovement** (RECEIVE, SHIP, ADJUST, TRANSFER) - audit trail with automatic quantity updates

### API Routes (inventory-service)
All routes use Zod for request validation. Pattern: `packages/inventory-service/src/routes/*.ts`
- `/products`, `/locations`, `/stock-items`, `/stock-movements`, `/health`

Stock movements handle transactions: TRANSFER creates paired movements in a Prisma transaction.

### Frontend (web)
- Uses React Query for data fetching (`src/hooks/use-*.ts`)
- API client in `src/lib/api.ts`
- UI components use Radix UI primitives + Tailwind CSS
- Pages: Dashboard (`/`), Products, Locations, Inventory

## Testing Notes

Tests run sequentially (`fileParallelism: false`) to avoid database conflicts. Each test file should clean up its data in `beforeEach`.
