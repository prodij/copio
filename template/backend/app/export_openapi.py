import json
from pathlib import Path

from app.main import create_app


def main() -> None:
    """Write the API contract to backend/openapi.json (the frontend generates its types from it)."""
    path = Path(__file__).resolve().parents[1] / "openapi.json"
    path.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
