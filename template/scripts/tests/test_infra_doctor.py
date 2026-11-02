import infra_doctor


def good() -> dict[str, object]:
    return {
        "dns": {"auth.x.test": "1.2.3.4", "api.x.test": "1.2.3.4"},
        "server_ip": "1.2.3.4",
        "http": {"https://auth.x.test/debug/ready": 200, "https://api.x.test/health": 200,
                 "https://app.x.test/": 200, "https://lago-api.x.test/api/v1/plans": 403,
                 "https://lago.x.test/": 403},
        "partman": "1",
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


def test_admin_cidrs_detection_ignores_spacing() -> None:
    assert not infra_doctor.admin_cidrs_set("admin_cidrs=[ ]\n")
    assert not infra_doctor.admin_cidrs_set("admin_cidrs        = []\n")
    assert infra_doctor.admin_cidrs_set('admin_cidrs = ["1.2.3.4/32"]\n')
