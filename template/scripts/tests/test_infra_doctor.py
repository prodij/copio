from urllib.parse import urlsplit

import pytest

import infra_doctor


def good() -> dict[str, object]:
    return {
        "dns": {"auth.x.test": "1.2.3.4", "api.x.test": "1.2.3.4"},
        "server_ip": "1.2.3.4",
        "http": {"https://auth.x.test/debug/ready": 200, "https://api.x.test/health": 200,
                 "https://app.x.test/": 200, "https://lago-api.x.test/api/v1/plans": 403,
                 "https://lago.x.test/": 403},
        "partman": "1",
        "running": list(infra_doctor.EXPECTED_SERVICES),
    }


def test_healthy_product_has_no_problems() -> None:
    assert infra_doctor.problems(good()) == []


def test_dns_pointing_elsewhere_is_named() -> None:
    results = good()
    results["dns"] = {"auth.x.test": "9.9.9.9", "api.x.test": "1.2.3.4"}
    assert any("auth.x.test" in p and "9.9.9.9" in p for p in infra_doctor.problems(results))


def test_certificate_failure_points_at_dns() -> None:
    results = good()
    results["http"]["https://api.x.test/health"] = 0  # type: ignore[index]
    assert any("api.x.test" in p and "DNS" in p for p in infra_doctor.problems(results))


def test_missing_partman_is_a_problem() -> None:
    results = good()
    results["partman"] = "0"
    assert any("pg_partman" in p for p in infra_doctor.problems(results))


def test_lago_being_public_is_a_problem() -> None:
    results = good()
    results["http"]["https://lago-api.x.test/api/v1/plans"] = 200  # type: ignore[index]
    assert any("lago-api" in p and "public" in p for p in infra_doctor.problems(results))


def test_admin_on_the_allow_list_may_see_lago() -> None:
    results = good()
    results["http"]["https://lago.x.test/"] = 200  # type: ignore[index]
    assert any("lago" in p for p in infra_doctor.problems(results))
    results["admin_cidrs_set"] = True
    assert infra_doctor.problems(results) == []
    results["http"]["https://lago-api.x.test/api/v1/plans"] = 401  # type: ignore[index]
    assert infra_doctor.problems(results) == []


def test_admin_list_still_flags_a_failing_lago() -> None:
    for url, status in [("https://lago.x.test/", 502), ("https://lago-api.x.test/api/v1/plans", 200),
                        ("https://lago-api.x.test/api/v1/plans", 502)]:
        results = good()
        results["admin_cidrs_set"] = True
        results["http"][url] = status  # type: ignore[index]
        assert any(urlsplit(url).netloc in p for p in infra_doctor.problems(results)), (url, status)


def test_no_answer_from_lago_names_dns_and_certificate() -> None:
    for admin in (False, True):
        results = good()
        results["admin_cidrs_set"] = admin
        results["http"]["https://lago.x.test/"] = 0  # type: ignore[index]
        assert any("lago.x.test" in p and "certificate" in p for p in infra_doctor.problems(results))


def test_lago_must_be_403_without_an_admin_list() -> None:
    results = good()
    results["http"]["https://lago.x.test/"] = 502  # type: ignore[index]
    assert any("lago.x.test" in p for p in infra_doctor.problems(results))


def test_a_stopped_service_is_named() -> None:
    results = good()
    results["running"] = [s for s in infra_doctor.EXPECTED_SERVICES if s not in {"lago-worker", "jobs"}]
    [problem] = infra_doctor.problems(results)
    assert "lago-worker" in problem and "jobs" in problem and "caddy" not in problem


def test_expected_services_are_pinned() -> None:
    assert infra_doctor.EXPECTED_SERVICES == [
        "caddy", "redis", "zitadel-api", "zitadel-login", "lago-api", "lago-worker",
        "lago-clock", "lago-front", "lago-pdf", "backend", "jobs"]


def test_server_output_is_parsed() -> None:
    running, partman = infra_doctor.parse_server_output("RUNNING:caddy redis \nPARTMAN:1\n")
    assert running == ["caddy", "redis"] and partman == "1"
    assert infra_doctor.parse_server_output("garbage") == ([], "0")


def test_server_command_is_pinned() -> None:
    command = infra_doctor.SERVER_CHECK
    assert command.startswith('export HOME="${HOME:-/root}" PATH="$PATH:/usr/local/bin"; ')
    assert "docker compose ps --status running --services" in command
    assert "COMPOSE_FILE=docker-compose.aws.yml" in command and "pg_partman" in command


@pytest.mark.parametrize(("text", "expected"), [
    ("admin_cidrs = []\n", False),
    ("admin_cidrs=[ ]\n", False),
    ("slug = \"x\"\n", False),
    ('# admin_cidrs = ["1.2.3.4/32"]\n', False),
    ('admin_cidrs = ["1.2.3.4/32"]\n', True),
    ('admin_cidrs=[ "1.2.3.4/32", "5.6.7.8/32" ]\n', True),
])
def test_admin_cidrs_only_counts_when_non_empty(text: str, expected: bool) -> None:
    assert infra_doctor.admin_cidrs_set(text) is expected
