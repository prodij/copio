# Copio

Multi-marketplace seller ERP with real-time inventory sync.

## Architecture

```
Browser → Next.js (3000) → /api/* proxy → Python FastAPI (8000) → PostgreSQL
```

### Packages

| Package | Description | Tech Stack |
|---------|-------------|------------|
| `packages/api` | REST API backend | Python, FastAPI, SQLAlchemy, Celery |
| `packages/web` | Web frontend | Next.js 16, React 19, Tailwind CSS |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+
- pnpm 9+

### Development

```bash
# Start infrastructure (Postgres, Redis, MinIO)
docker compose -f docker-compose.dev.yml up -d

# Install Node dependencies
pnpm install

# Run database migrations
pnpm db:migrate

# Start all services
pnpm dev
```

Services will be available at:
- **Web UI**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001

### Docker (Full Stack)

```bash
docker compose -f docker-compose.dev.yml up
```

## Project Structure

```
copio/
├── packages/
│   ├── api/           # Python FastAPI backend
│   │   ├── src/
│   │   │   ├── api/v1/      # REST endpoints
│   │   │   ├── db/models/   # SQLAlchemy models
│   │   │   ├── schemas/     # Pydantic validation
│   │   │   ├── services/    # Business logic
│   │   │   └── workers/     # Celery tasks
│   │   └── alembic/         # DB migrations
│   └── web/           # Next.js frontend
│       └── src/
│           ├── app/         # Pages (App Router)
│           ├── components/  # React components
│           ├── hooks/       # Custom hooks
│           └── lib/         # Utilities
├── docs/              # Documentation
└── .deprecated/       # Legacy TS code (reference only)
```

## Data Model

### Three Product Perspectives

```
┌─────────────────────────────────────────────────────────────────┐
│                          PRODUCT                                 │
│  Master product data + customer-facing defaults                 │
└─────────────────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────┐    ┌─────────────────────────────────────┐
│   VENDOR PRODUCT    │    │        CHANNEL LISTING              │
│   (Procurement)     │    │        (Marketplace)                │
│ - vendorSku, cost   │    │ - channelSku (ASIN, etc.)          │
│ - MOQ, case pack    │    │ - price, fulfillment settings      │
│ - lead time         │    │ - title/description overrides      │
└─────────────────────┘    └─────────────────────────────────────┘
```

## Commands

```bash
# Development
pnpm dev              # Start all services
pnpm build            # Build all packages
pnpm lint             # Lint code
pnpm typecheck        # TypeScript checking

# Database
pnpm db:migrate       # Run Alembic migrations

# Individual packages
pnpm --filter @copio/api dev
pnpm --filter @copio/web dev
```

## Integrations

- **Amazon SP-API** - Product catalog, orders, inventory
- **Shopify** - Orders and inventory sync
- **Walmart** (planned)

## License

Proprietary
