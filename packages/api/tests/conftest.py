import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Force the test process to use a deterministic in-memory env so the
# `Settings` cache doesn't read a real .env that might leak credentials.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5435/copio_test")
os.environ.setdefault("FOUNDER_TENANT_ID", "test-tenant")
os.environ.setdefault("FOUNDER_DISPLAY_NAME", "Test")
