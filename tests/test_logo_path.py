import ast
import os
import pathlib
import shutil
import subprocess
import time

import pexpect
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


def test_logo_path_is_not_kept_in_the_answers_and_update_still_works(tmp_path: pathlib.Path) -> None:
    template = tagged_template(tmp_path)
    logo = tmp_path / "mine.svg"
    logo.write_text(CUSTOM)
    dest = tmp_path / "product"
    generate_and_commit(template, logo, dest)
    assert "logo_path:" not in (dest / ".copier-answers.yml").read_text()
    release_v2(template)
    run_update(str(dest), defaults=True, unsafe=True, overwrite=True, quiet=True)
    assert "logo_path:" not in (dest / ".copier-answers.yml").read_text()
    assert (dest / "brand" / "NOTE.txt").read_text() == "v2"
    assert (dest / "brand" / "logo.svg").read_text() == CUSTOM


def answer_every_prompt(*args: str, cwd: pathlib.Path) -> str:
    """Runs Copier in a terminal, pressing Enter whenever it goes quiet. Returns everything it printed."""
    copier = pexpect.spawn("uv", ["run", "--project", str(ROOT), "copier", *args], cwd=cwd, timeout=2,
                           encoding="utf8", dimensions=(50, 200))
    out = ""
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            out += copier.read_nonblocking(65536, timeout=2)
        except pexpect.TIMEOUT:
            copier.send("Pty Co\r" if "Human name" in out and "Pty Co" not in out else "\r")
        except pexpect.EOF:
            break
    copier.close()
    assert copier.exitstatus == 0, out[-2000:]
    return out


@pytest.mark.slow
def test_logo_path_is_asked_on_copy_and_not_on_update(tmp_path: pathlib.Path) -> None:
    # An interactive update would otherwise ask for it again, with hidden input.
    template = tagged_template(tmp_path)
    copied = answer_every_prompt("copy", str(template), "product", "--trust", cwd=tmp_path)
    assert "absolute path to an SVG" in copied
    dest = tmp_path / "product"
    assert "logo_path:" not in (dest / ".copier-answers.yml").read_text()
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "init")
    release_v2(template)
    updated = answer_every_prompt("update", "--trust", cwd=dest)
    assert "Human name" in updated, "the other questions are asked"
    assert "absolute path to an SVG" not in updated
    assert (dest / "brand" / "NOTE.txt").read_text() == "v2"


def copy_task_body() -> str:
    return yaml.safe_load((ROOT / "copier.yml").read_text())["_tasks"][0]["command"][2]


def test_copy_task_and_its_import_parse_as_python_3_9() -> None:
    # The first task runs under whatever python3 is on PATH, and macOS's own is 3.9.
    source = (ROOT / "template" / "scripts" / "svg_check.py").read_text()
    tree = ast.parse(source, feature_version=(3, 9))
    ast.parse(copy_task_body(), feature_version=(3, 9))
    future = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "__future__"]
    assert any(a.name == "annotations" for n in future for a in n.names), "`str | None` fails at import on 3.9"


def old_python() -> str | None:
    """The oldest python3 here, if it is older than 3.10; CI may have none, and the AST test covers that."""
    for candidate in ("/usr/bin/python3", "python3.9"):
        path = shutil.which(candidate)
        if path:
            probe = subprocess.run([path, "-c", "import sys; print(sys.version_info < (3, 10))"],
                                   capture_output=True, text=True, check=False)
            if probe.stdout.strip() == "True":
                return path
    return None


def test_copy_task_runs_under_the_oldest_python_here(tmp_path: pathlib.Path) -> None:
    python = old_python()
    if python is None:
        pytest.skip("no python3 older than 3.10 on this machine")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "brand").mkdir()
    shutil.copy(ROOT / "template" / "scripts" / "svg_check.py", tmp_path / "scripts")
    logo = tmp_path / "mine.svg"
    logo.write_text(CUSTOM)
    done = subprocess.run([python, "-c", copy_task_body(), str(logo)], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert (tmp_path / "brand" / "logo.svg").read_text() == CUSTOM


def broken_python3(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "bin" / "python3"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\necho 'the first task ran' >&2\nexit 1\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake.parent}:{os.environ['PATH']}")


def test_without_a_logo_path_the_first_task_is_a_true_no_op(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    broken_python3(tmp_path, monkeypatch)
    run_copy(str(ROOT), str(tmp_path / "p"), data=ANSWERS, defaults=True, unsafe=True, vcs_ref="HEAD", quiet=True)
    assert "<svg" in (tmp_path / "p" / "brand" / "logo.svg").read_text()


def test_update_runs_neither_task(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    template = tagged_template(tmp_path)
    logo = tmp_path / "mine.svg"
    logo.write_text(CUSTOM)
    dest = tmp_path / "product"
    generate_and_commit(template, logo, dest)
    (dest / "frontend" / "src" / "brand.css").write_text("/* the product's */\n")
    git(dest, "commit", "-q", "-am", "edit")
    release_v2(template)
    broken_python3(tmp_path, monkeypatch)
    run_update(str(dest), defaults=True, unsafe=True, overwrite=True, quiet=True)
    assert (dest / "brand" / "NOTE.txt").read_text() == "v2"
    assert (dest / "frontend" / "src" / "brand.css").read_text() == "/* the product's */\n"


@pytest.mark.parametrize("body", ["<script>alert(1)</script>", "<rect onload='alert(1)'/>", "<foreignObject/>"])
def test_an_unsafe_logo_path_is_refused_on_copy(tmp_path: pathlib.Path, body: str) -> None:
    logo = tmp_path / "mine.svg"
    logo.write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>')
    with pytest.raises(Exception, match="logo_path"):
        run_copy(str(ROOT), str(tmp_path / "p"), data={**ANSWERS, "logo_path": str(logo)},
                 defaults=True, unsafe=True, vcs_ref="HEAD", quiet=True)


def test_a_logo_path_that_isnt_svg_is_refused_on_copy(tmp_path: pathlib.Path) -> None:
    logo = tmp_path / "mine.png"
    logo.write_text(CUSTOM)
    with pytest.raises(Exception, match="logo_path"):
        run_copy(str(ROOT), str(tmp_path / "p"), data={**ANSWERS, "logo_path": str(logo)},
                 defaults=True, unsafe=True, vcs_ref="HEAD", quiet=True)


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


GENERATED = ["frontend/src/brand.css", "frontend/public/logo.svg", "frontend/public/favicon.svg",
             "frontend/src/api/schema.d.ts", "backend/openapi.json", "brand/logo.svg"]


def test_update_leaves_generated_files_alone_and_merges_the_rest(tmp_path: pathlib.Path) -> None:
    template = tagged_template(tmp_path)
    logo = tmp_path / "mine.svg"
    logo.write_text(CUSTOM)
    dest = tmp_path / "product"
    generate_and_commit(template, logo, dest)
    for name in GENERATED:
        (dest / name).write_text(f"product's {name}\n")
    (dest / "frontend" / "src" / "pages" / "Plans.tsx").write_text(
        (dest / "frontend" / "src" / "pages" / "Plans.tsx").read_text() + "// product edit\n")
    (dest / "backend" / "app" / "notes.py").write_text("# the product's own file\n")
    (dest / "backend" / "app" / "billing" / "plans.yaml").write_text("plans: []\n")
    (dest / ".env").write_text("KEEP=1\n")
    git(dest, "add", "-A")  # .env stays ignored
    git(dest, "commit", "-q", "-m", "product")

    for name in GENERATED:
        (template / "template" / name).write_text(f"template's {name}\n")
    (template / "template" / "frontend" / "src" / "lib" / "added.ts").write_text("export const added = 1;\n")
    plans = template / "template" / "backend" / "app" / "billing" / "plans.yaml.jinja"
    plans.write_text(plans.read_text().replace("seats: 5", "seats: 6"))
    git(template, "add", "-A")
    git(template, "commit", "-q", "-m", "v2")
    git(template, "tag", "v1.1.0")
    run_update(str(dest), defaults=True, unsafe=True, overwrite=True, quiet=True)

    for name in GENERATED:
        assert (dest / name).read_text() == f"product's {name}\n", name
    assert (dest / "frontend" / "src" / "pages" / "Plans.tsx").read_text().endswith("// product edit\n")
    assert (dest / "backend" / "app" / "notes.py").exists()
    assert (dest / "frontend" / "src" / "lib" / "added.ts").exists()
    assert (dest / ".env").read_text() == "KEEP=1\n"
    # Both changed the plan file: a conflict the product sees, not a silent loss on either side.
    merged = (dest / "backend" / "app" / "billing" / "plans.yaml").read_text()
    assert "<<<<<<<" in merged and "plans: []" in merged and "seats: 6" in merged


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
