import pathlib

import pytest
from copier import run_copy

ROOT = pathlib.Path(__file__).resolve().parents[1]

ANSWERS = {
    "product_name": "Acme Reports",
    "product_slug": "acme-reports",
    "domain": "acme-reports.localhost",
    "brand_primary": "#3355ff",
    "brand_accent": "#ff7a33",
    "brand_font": "Inter",
    "starter_plan_price_usd": 49,
    "starter_plan_interval": "month",
}


@pytest.fixture(scope="session")
def product_dir(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    dest = tmp_path_factory.mktemp("product") / "acme-reports"
    run_copy(str(ROOT), str(dest), data=ANSWERS, defaults=True, unsafe=True, vcs_ref="HEAD", quiet=True)
    return dest
