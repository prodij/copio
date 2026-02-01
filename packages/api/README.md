# Copio API

Python FastAPI backend for the Copio multi-marketplace ERP.

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL + SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Auth**: fastapi-users + JWT
- **Background Jobs**: Celery + Redis
- **Validation**: Pydantic v2

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 16+
- Redis 7+

### Installation

```bash
cd packages/api

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env with your settings
```

### Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Generate migration from model changes
alembic revision --autogenerate -m "description"

# Rollback one migration
alembic downgrade -1
```

### Running

```bash
# Development server (with hot reload)
uvicorn src.main:app --reload --port 8000

# Production
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Celery worker (background jobs)
celery -A src.workers.celery_app worker --loglevel=info

# Celery beat (scheduled tasks)
celery -A src.workers.celery_app beat --loglevel=info
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Type checking
mypy src
```

## API Documentation

Once running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
src/
├── main.py              # FastAPI app entry point
├── config.py            # Pydantic settings
├── api/
│   ├── deps.py          # Dependency injection
│   └── v1/              # API v1 endpoints
│       ├── router.py    # Route aggregator
│       ├── products.py
│       ├── categories.py
│       ├── locations.py
│       ├── stock_items.py
│       ├── stock_movements.py
│       ├── vendors.py
│       ├── vendor_*.py  # Vendor sub-resources
│       ├── channel_listings.py
│       ├── purchase_orders.py
│       ├── velocity.py
│       └── sync.py
├── auth/                # Authentication
│   ├── routes.py
│   ├── manager.py
│   └── backend.py
├── db/
│   ├── base.py          # SQLAlchemy declarative base
│   ├── session.py       # Database session management
│   └── models/          # SQLAlchemy models
│       ├── product.py
│       ├── category.py
│       ├── vendor.py
│       ├── inventory.py
│       ├── purchase_order.py
│       ├── channel_listing.py
│       ├── order.py
│       ├── user.py
│       ├── tenant.py
│       └── enums.py
├── schemas/             # Pydantic request/response models
├── services/            # Business logic
│   ├── velocity.py      # Sales velocity calculations
│   ├── amazon.py        # Amazon SP-API integration
│   ├── shopify.py       # Shopify API integration
│   └── email.py         # Email notifications
├── workers/             # Celery background tasks
│   ├── celery_app.py
│   └── tasks.py
└── templates/           # Email templates
```

## API Endpoints

### Core Resources

| Endpoint | Description |
|----------|-------------|
| `GET/POST /api/v1/products` | Product catalog |
| `GET/POST /api/v1/categories` | Category taxonomy |
| `GET/POST /api/v1/locations` | Warehouse locations |
| `GET/POST /api/v1/stock-items` | Inventory per location |
| `GET/POST /api/v1/stock-movements` | Inventory audit trail |

### Vendor Management

| Endpoint | Description |
|----------|-------------|
| `GET/POST /api/v1/vendors` | Vendor records |
| `GET/POST /api/v1/vendor-contacts` | Vendor contacts |
| `GET/POST /api/v1/vendor-addresses` | Vendor addresses |
| `GET/POST /api/v1/vendor-documents` | Vendor documents |
| `GET/POST /api/v1/vendor-products` | Vendor product mappings |

### Marketplace

| Endpoint | Description |
|----------|-------------|
| `GET/POST /api/v1/channel-listings` | Marketplace listings |
| `GET/POST /api/v1/purchase-orders` | Purchase orders |

### Analytics & Sync

| Endpoint | Description |
|----------|-------------|
| `/api/v1/velocity/*` | Sales velocity metrics |
| `/api/v1/sync/*` | Marketplace sync operations |

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/copio

# Redis (Celery)
REDIS_URL=redis://localhost:6379

# Auth
SECRET_KEY=your-secret-key

# MinIO/S3
MINIO_ENDPOINT=localhost
MINIO_PORT=9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Debug
DEBUG=true
```
