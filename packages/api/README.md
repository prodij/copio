# Copio API

Python/FastAPI service for velocity tracking, channel sync, and authentication.

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL (shared with inventory-service)
- Redis (for Celery)

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
# Generate migration from model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Running

```bash
# Development server
uvicorn src.main:app --reload --port 8000

# Production
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Celery worker
celery -A src.workers.celery_app worker --loglevel=info

# Celery beat (scheduler)
celery -A src.workers.celery_app beat --loglevel=info
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=src --cov-report=html
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
src/
├── main.py              # FastAPI app
├── config.py            # Settings
├── db/
│   ├── base.py          # SQLAlchemy Base
│   ├── session.py       # DB session
│   └── models/          # SQLAlchemy models
├── api/
│   ├── deps.py          # Dependencies
│   └── v1/              # API endpoints
├── services/            # Business logic
├── schemas/             # Pydantic models
└── workers/             # Celery tasks
```

## Related Documentation

- [Sales Velocity Design](../../docs/plans/2025-01-27-sales-velocity-design.md)
- [Decision Record](../../docs/plans/2025-01-27-velocity-decisions.md)
- [Task Breakdown](../../docs/plans/2025-01-27-velocity-tasks.md)
