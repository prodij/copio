"""`make infra-doctor`: checks a deployed product from outside, then from the server. Exit 1 on any problem."""

import re
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

SERVER_PREFIX = 'export HOME="${HOME:-/root}" PATH="$PATH:/usr/local/bin"; '
SERVER_CHECK = (
    SERVER_PREFIX  # noqa: S608
    + "cd /opt/app && export COMPOSE_FILE=docker-compose.aws.yml; "
    + "echo \"RUNNING:$(docker compose ps --status running --services | tr '\\n' ' ')\"; "
    + "echo \"PARTMAN:$(docker compose exec -T lago-api bin/rails runner "
    + "\"puts ActiveRecord::Base.connection.select_value(\\\"select count(*) from partman.part_config where parent_table='public.enriched_events'\\\")\" "
    + "2>/dev/null | tail -n 1)\""
)
EXPECTED_SERVICES = ["caddy", "redis", "zitadel-api", "zitadel-login", "lago-api", "lago-worker",
                     "lago-clock", "lago-front", "lago-pdf", "backend", "jobs"]
CERT_HINT = "no HTTPS answer. Usually the certificate isn't issued yet because DNS isn't pointing at the server"


def problems(results: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for host, ip in results["dns"].items():
        if ip != results["server_ip"]:
            found.append(f"DNS: {host} points at {ip}, not the server at {results['server_ip']}")
    admin_set = results.get("admin_cidrs_set", False)
    for url, status in results["http"].items():
        host = urlsplit(url).netloc
        if status == 0:
            found.append(f"{host}: {CERT_HINT}")
        elif host.startswith("lago-api."):
            if status not in ({401, 403} if admin_set else {403}):
                found.append(f"{host} looks public or is failing (HTTP {status}); only its webhooks should be public")
        elif host.startswith("lago."):
            if status not in ({200, 403} if admin_set else {403}):
                found.append(f"{host} looks public or is failing (HTTP {status}); only its webhooks should be public")
        elif status != 200:
            found.append(f"{url} answered HTTP {status}")
    running = results.get("running")
    if running is not None:
        missing = [s for s in EXPECTED_SERVICES if s not in running]
        if missing:
            found.append(f"not running on the server: {', '.join(missing)}. Caddy answers 403 for Lago even when it is down")
    partman = results.get("partman")
    if partman is not None and partman != "1":
        found.append("pg_partman isn't set up in Lago's database: partman.part_config has no row for enriched_events, "
                     "or lago-api couldn't answer. Lago's first migration adds that row: see `docker compose logs lago-migrate`")
    return found


def admin_cidrs_set(tfvars_text: str) -> bool:
    """True only when admin_cidrs lists at least one address (empty, missing or commented out is False)."""
    return bool(re.search(r'^\s*admin_cidrs\s*=\s*\[\s*"', tfvars_text, re.M))


def parse_server_output(output: str) -> tuple[list[str], str]:
    running: list[str] = []
    partman = "0"
    for line in output.splitlines():
        if line.startswith("RUNNING:"):
            running = line.removeprefix("RUNNING:").split()
        elif line.startswith("PARTMAN:"):
            partman = line.removeprefix("PARTMAN:").strip() or "0"
    return running, partman


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
    results: dict[str, Any] = {
        "dns": {h: resolve(h) for h in [f"{s}.{domain}" for s in ["auth", "api", "lago", "lago-api"]]},
        "server_ip": server_ip,
        "admin_cidrs_set": admin_cidrs_set(infra.TFVARS.read_text()),
        "http": {u: status_of(u) for u in [
            f"https://auth.{domain}/debug/ready", f"https://api.{domain}/health", f"https://app.{domain}/",
            f"https://lago-api.{domain}/api/v1/plans", f"https://lago.{domain}/"]},
    }
    found = problems(results)
    try:
        output = infra.run_on_server(aws, infra.terraform_output("server_instance_id"), SERVER_CHECK, timeout_s=120)
        results["running"], results["partman"] = parse_server_output(output)
        found = problems(results)
    except SystemExit as exc:
        found.append(f"could not check the server: {exc}")
    for problem in found:
        print(f"PROBLEM: {problem}")
    if found:
        raise SystemExit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
