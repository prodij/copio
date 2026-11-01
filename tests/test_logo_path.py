import pathlib
import shutil
import subprocess

import pytest
import yaml
from copier import run_copy, run_update

from conftest import ANSWERS, ROOT

CUSTOM = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4"><circle cx="2" cy="2" r="2"/></svg>'


def git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def test_logo_path_replaces_the_template_logo(tmp_path: pathlib.Path) -> None:
    logo = tmp_path / "mine.svg"
    logo.write_text(CUSTOM)
    dest = tmp_path / "product"
    run_copy(str(ROOT), str(dest), data={**ANSWERS, "logo_path": str(logo)}, defaults=True,
             unsafe=True, vcs_ref="HEAD", quiet=True)
    assert (dest / "brand" / "logo.svg").read_text() == CUSTOM
    assert yaml.safe_load((dest / "brand" / "brand.yaml").read_text())["logo"] == "logo.svg"


def tagged_template(tmp_path: pathlib.Path) -> pathlib.Path:
    # Copier only updates from a tagged template, so use a throwaway tagged copy of this one.
    template = tmp_path / "template-repo"
    shutil.copytree(ROOT / "template", template / "template")
    shutil.copy(ROOT / "copier.yml", template / "copier.yml")
    git(template, "init", "-q")
    git(template, "add", "-A")
    git(template, "commit", "-q", "-m", "v1")
    git(template, "tag", "v1.0.0")
    return template


def release_v2(template: pathlib.Path) -> None:
    (template / "template" / "brand" / "NOTE.txt").write_text("v2")
    git(template, "add", "-A")
    git(template, "commit", "-q", "-m", "v2")
    git(template, "tag", "v1.1.0")


def generate_and_commit(template: pathlib.Path, logo: pathlib.Path, dest: pathlib.Path) -> None:
    run_copy(str(template), str(dest), data={**ANSWERS, "logo_path": str(logo)}, defaults=True,
             unsafe=True, quiet=True)
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")


def test_update_keeps_a_logo_edited_in_the_product(tmp_path: pathlib.Path) -> None:
    template = tagged_template(tmp_path)
    logo = tmp_path / "mine.svg"
    logo.write_text(CUSTOM)
    dest = tmp_path / "product"
    generate_and_commit(template, logo, dest)
    edited = CUSTOM.replace("r=\"2\"", "r=\"1\"")
    (dest / "brand" / "logo.svg").write_text(edited)
    git(dest, "commit", "-q", "-am", "edit logo")
    release_v2(template)
    run_update(str(dest), defaults=True, unsafe=True, overwrite=True, quiet=True)
    assert (dest / "brand" / "NOTE.txt").read_text() == "v2"
    assert (dest / "brand" / "logo.svg").read_text() == edited


def test_update_works_when_the_logo_source_is_gone(tmp_path: pathlib.Path) -> None:
    template = tagged_template(tmp_path)
    logo = tmp_path / "mine.svg"
    logo.write_text(CUSTOM)
    dest = tmp_path / "product"
    generate_and_commit(template, logo, dest)
    logo.unlink()
    release_v2(template)
    run_update(str(dest), defaults=True, unsafe=True, overwrite=True, quiet=True)
    assert (dest / "brand" / "NOTE.txt").read_text() == "v2"
    assert (dest / "brand" / "logo.svg").read_text() == CUSTOM


@pytest.mark.parametrize("content", ["not a logo", None])
def test_bad_logo_path_fails_clearly(tmp_path: pathlib.Path, content: str | None) -> None:
    logo = tmp_path / "mine.svg"
    if content is not None:
        logo.write_text(content)
    with pytest.raises(Exception, match="logo_path"):
        run_copy(str(ROOT), str(tmp_path / "product"), data={**ANSWERS, "logo_path": str(logo)},
                 defaults=True, unsafe=True, vcs_ref="HEAD", quiet=True)
