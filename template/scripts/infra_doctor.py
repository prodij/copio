"""`make infra-doctor`: checks a deployed product from outside, then from the server. Exit 1 on any problem."""

import re
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

PARTMAN_CHECK = (
    "cd /opt/app && COMPOSE_FILE=docker-compose.aws.yml docker compose exec -T lago-api bin/rails runner "
    "\"puts ActiveRecord::Base.connection.select_value(\\\"select count(*) from pg_extension where extname='pg_partman'\\\")\""
)


def problems(results: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for host, ip in results["dns"].items():
        if ip != results["server_ip"]:
            found.append(f"DNS: {host} points at {ip}, not the server at {results['server_ip']}")
    admin_set = results.get("admin_cidrs_set", False)
    for url, status in results["http"].items():
        host = urlsplit(url).netloc
        if host.startswith("lago"):
            if status != 403 and not admin_set:
                found.append(f"{host} looks public (HTTP {status}); only its webhooks should be")
        elif status == 0:
            found.append(f"{host}: no HTTPS answer. Usually the certificate isn't issued yet because DNS isn't pointing at the server")
        elif status != 200:
            found.append(f"{url} answered HTTP {status}")
    if results["partman"] != "1":
        found.append("pg_partman isn't installed in Lago's database, and Lago skips its setup silently. Re-run make infra-bootstrap")
    return found


def admin_cidrs_set(tfvars_text: str) -> bool:
    return not re.search(r"^\s*admin_cidrs\s*=\s*\[\s*\]", tfvars_text, re.M)


def status_of(url: str) -> int:
    try:
        return httpx.get(url, timeout=15.0, follow_redirects=True).status_code
    except httpx.HTTPError:
        return 0


def resolve(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except OSError:
        return "nothing"


def main() -> None:
    import infra

    tfvars, aws = infra.read_tfvars(), infra.session()
    domain, server_ip = tfvars["domain"], infra.terraform_output("server_ip")
    admin_set = admin_cidrs_set(infra.TFVARS.read_text())
    output = infra.run_on_server(aws, infra.terraform_output("server_instance_id"), PARTMAN_CHECK, timeout_s=120)
    results = {
        "dns": {h: resolve(h) for h in [f"{s}.{domain}" for s in ["auth", "api", "lago", "lago-api"]]},
        "server_ip": server_ip,
        "admin_cidrs_set": admin_set,
        "http": {u: status_of(u) for u in [
            f"https://auth.{domain}/debug/ready", f"https://api.{domain}/health", f"https://app.{domain}/",
            f"https://lago-api.{domain}/api/v1/plans", f"https://lago.{domain}/"]},
        "partman": output.strip().splitlines()[-1] if output.strip() else "0",
    }
    found = problems(results)
    for problem in found:
        print(f"PROBLEM: {problem}")
    if found:
        raise SystemExit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
