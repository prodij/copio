"""Bootstrap's AWS side: the values the frontend build needs, and saving Zitadel's tokens.

Zitadel writes its tokens only on its first start against an empty database, so a replaced server
gets them back from Secrets Manager (deploy/start.sh). Passed boto3 clients, so tests need no AWS.
"""

import json
from pathlib import Path
from typing import Any


def frontend_values(domain: str, client_id: str, project_id: str) -> dict[str, str]:
    return {
        "VITE_API_BASE_URL": f"https://api.{domain}",
        "ZITADEL_ISSUER": f"https://auth.{domain}",
        "ZITADEL_CLIENT_ID": client_id,
        "ZITADEL_PROJECT_ID": project_id,
    }


def publish_frontend(ssm: Any, slug: str, values: dict[str, str]) -> None:
    ssm.put_parameter(Name=f"/{slug}/frontend", Value=json.dumps(values), Type="String", Overwrite=True)


def save_tokens(secrets: Any, slug: str, state_dir: Path) -> None:
    files = {
        "admin_pat": state_dir / "zitadel" / "admin.pat",
        "login_client_pat": state_dir / "zitadel" / "login-client.pat",
        "backend_pat": state_dir / "backend" / "backend.pat",
        "ids_env": state_dir / "ids.env",
    }
    missing = [str(p) for p in files.values() if not p.is_file()]
    if missing:
        raise SystemExit(f"bootstrap: can't save tokens, missing {', '.join(missing)}")
    values = {k: (p.read_text() if k == "ids_env" else p.read_text().strip()) for k, p in files.items()}
    secrets.put_secret_value(SecretId=f"{slug}/bootstrap", SecretString=json.dumps(values))
