import pathlib

import pytest

from app.export_openapi import OPENAPI, main


def test_check_fails_naming_make_regen_and_changes_nothing(tmp_path: pathlib.Path) -> None:
    stale = tmp_path / "openapi.json"
    stale.write_text("{}\n")
    with pytest.raises(SystemExit, match="make regen"):
        main(check=True, path=stale)
    assert stale.read_text() == "{}\n"


def test_check_passes_once_written(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "openapi.json"
    main(path=path)
    main(check=True, path=path)


def test_the_contract_in_the_repo_matches_the_routes() -> None:
    main(check=True, path=OPENAPI)
