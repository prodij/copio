import json
import sys
from pathlib import Path

from app.main import create_app

OPENAPI = Path(__file__).resolve().parents[1] / "openapi.json"


def main(check: bool = False, path: Path = OPENAPI) -> None:
    """Write the API contract to backend/openapi.json (the frontend generates its types from it).

    With --check, change nothing and fail if the file doesn't match the routes.
    """
    contract = json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"
    if not check:
        path.write_text(contract)
    elif not path.is_file() or path.read_text() != contract:
        sys.exit("out of date with the routes: backend/openapi.json. Run `make regen`.")


if __name__ == "__main__":
    main(check="--check" in sys.argv)
