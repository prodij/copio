import pathlib
import re
import subprocess

SECRET_PATTERNS = [
    re.compile(r"sk_(live|test)_[0-9A-Za-z]{10,}"),
    re.compile(r"whsec_[0-9A-Za-z]{10,}"),
    re.compile(r"-----BEGIN (RSA )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def test_product_has_top_level_layout(product_dir: pathlib.Path) -> None:
    for name in ["backend", "frontend", "jobs", "infra", "brand", "README.md", ".gitignore"]:
        assert (product_dir / name).exists(), name


def test_answers_are_rendered(product_dir: pathlib.Path) -> None:
    readme = (product_dir / "README.md").read_text()
    assert "# Acme Reports" in readme
    assert "{{" not in readme


def test_env_is_ignored(product_dir: pathlib.Path) -> None:
    assert ".env" in (product_dir / ".gitignore").read_text().splitlines()


def test_no_secret_values_anywhere() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    offenders = []
    for rel in listing:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if any(p.search(text) for p in SECRET_PATTERNS):
            offenders.append(rel)
    assert offenders == []


def test_default_logo_is_the_template_logo(product_dir: pathlib.Path) -> None:
    assert "<svg" in (product_dir / "brand" / "logo.svg").read_text()
    assert (product_dir / "brand" / "brand.yaml").read_text().count("Acme Reports") == 1


def test_env_example_lists_names_only(product_dir: pathlib.Path) -> None:
    keys = [line for line in (product_dir / ".env.example").read_text().splitlines()
            if line and not line.startswith("#")]
    assert keys and all(re.fullmatch(r"[A-Z][A-Z0-9_]*=", line) for line in keys), keys


def test_local_state_is_ignored(product_dir: pathlib.Path) -> None:
    ignored = (product_dir / ".gitignore").read_text().splitlines()
    assert ".env" in ignored and ".bootstrap/" in ignored


def test_make_keeps_container_secrets_out_of_host_tools(product_dir: pathlib.Path, tmp_path: pathlib.Path) -> None:
    (tmp_path / "Makefile").write_text((product_dir / "Makefile").read_text())
    (tmp_path / ".env").write_text("ZITADEL_MASTERKEY=m\nLAGO_RSA_PRIVATE_KEY=r\nLAGO_API_KEY=k\n")
    env = subprocess.run(["make", "-s", "--eval", "show-env: ; @env", "show-env"],
                         cwd=tmp_path, capture_output=True, text=True, check=True).stdout.splitlines()
    assert "LAGO_API_KEY=k" in env  # bootstrap needs it
    assert not any(line.startswith(("ZITADEL_MASTERKEY=", "LAGO_RSA_PRIVATE_KEY=")) for line in env)
