import base64
import json
import pathlib
import re
import sys
import types
from typing import Any

import httpx
import pytest
import respx

import brand
from brand import (
    BrandError,
    apply_lago,
    apply_zitadel,
    css_tokens,
    load_brand,
    zitadel_label_policy,
)

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="8" height="8" fill="currentColor"/></svg>'
BASE = "http://auth.test"
LABEL = f"{BASE}/admin/v1/policies/label"
ASSETS = f"{BASE}/assets/v1/instance/policy/label"
YAML = "name: Acme\nfont: Inter\nlogo: logo.svg\nlight: {primary: '#3355ff', accent: '#ff7a33'}\n"


def write(tmp_path: pathlib.Path, text: str = YAML) -> pathlib.Path:
    (tmp_path / "logo.svg").write_text(SVG)
    p = tmp_path / "brand.yaml"
    p.write_text(text)
    return p


def test_css_has_light_and_dark(tmp_path: pathlib.Path) -> None:
    css = css_tokens(load_brand(write(tmp_path)))
    assert "--brand-primary: #3355ff;" in css
    assert ".dark {" in css
    assert '--brand-font: "Inter", system-ui, sans-serif;' in css


def test_css_emits_exactly_the_tokens_the_frontend_derives_from(tmp_path: pathlib.Path) -> None:
    css = css_tokens(load_brand(write(tmp_path)))
    root, dark = re.findall(r"(?::root|\.dark) \{(.*?)\n\}", css, re.S)
    assert re.findall(r"--(brand-[a-z]+):", root) == [
        "brand-primary",
        "brand-accent",
        "brand-background",
        "brand-foreground",
        "brand-font",
    ]
    assert re.findall(r"--(brand-[a-z]+):", dark) == [
        "brand-primary",
        "brand-accent",
        "brand-background",
        "brand-foreground",
    ]


def test_dark_palette_is_computed_when_not_given(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path))
    assert b.dark.primary == "#6680ff"  # 25% of the way to white
    assert b.dark.accent == "#ff9b66"
    assert (b.dark.background, b.dark.foreground) == ("#0b0b0c", "#ececee")


def test_dark_palette_can_be_given(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path, YAML + "dark: {primary: '#112233', background: '#000000'}\n"))
    assert b.dark.primary == "#112233"
    assert b.dark.background == "#000000"
    assert b.dark.accent == "#ff9b66"


def test_zitadel_policy_maps_colours(tmp_path: pathlib.Path) -> None:
    policy = zitadel_label_policy(load_brand(write(tmp_path)))
    assert policy["primaryColor"] == "#3355ff"
    assert policy["backgroundColorDark"] == "#0b0b0c"
    assert policy["hideLoginNameSuffix"] is True


@pytest.mark.parametrize("bad", ["'#33f'", "'blue'", "'#3355ffaa'"])
def test_bad_colours_rejected(tmp_path: pathlib.Path, bad: str) -> None:
    text = (
        f"name: Acme\nfont: Inter\nlogo: logo.svg\nlight: {{primary: {bad}, accent: '#ff7a33'}}\n"
    )
    with pytest.raises(BrandError, match="colour"):
        load_brand(write(tmp_path, text))


def test_missing_logo_rejected(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "brand.yaml"
    p.write_text(YAML.replace("logo.svg", "nope.svg"))
    with pytest.raises(BrandError, match="logo"):
        load_brand(p)


def test_missing_field_is_a_brand_error(tmp_path: pathlib.Path) -> None:
    text = "name: Acme\nlogo: logo.svg\nlight: {primary: '#3355ff', accent: '#ff7a33'}\n"
    with pytest.raises(BrandError, match="font"):
        load_brand(write(tmp_path, text))


def test_missing_font_file_rejected(tmp_path: pathlib.Path) -> None:
    with pytest.raises(BrandError, match="font_file"):
        load_brand(write(tmp_path, YAML + "font_file: nope.woff2\n"))


def posted(mock: respx.MockRouter) -> list[tuple[str, bytes]]:
    return [
        (c.request.url.path, c.request.content) for c in mock.calls if c.request.method == "POST"
    ]


def test_apply_zitadel_updates_policy_uploads_logos_then_activates(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path))
    with respx.mock(assert_all_called=True) as mock:
        mock.put(LABEL).respond(200, json={})
        mock.post(f"{ASSETS}/logo").respond(200, json={})
        mock.post(f"{ASSETS}/logo/dark").respond(200, json={})
        mock.post(f"{LABEL}/_activate").respond(200, json={})
        apply_zitadel(b, BASE, "tok")
        order = [(c.request.method, c.request.url.path) for c in mock.calls]
        assert order == [
            ("PUT", "/admin/v1/policies/label"),
            ("POST", "/assets/v1/instance/policy/label/logo"),
            ("POST", "/assets/v1/instance/policy/label/logo/dark"),
            ("POST", "/admin/v1/policies/label/_activate"),
        ]
        put = mock.calls[0].request
        assert put.headers["authorization"] == "Bearer tok"
        assert json.loads(put.content) == zitadel_label_policy(b)
        light, dark = (body for _, body in posted(mock)[:2])
        assert b'fill="#3355ff"' in light
        assert b"currentColor" not in light
        assert b'fill="#6680ff"' in dark


def test_apply_zitadel_uploads_font_only_when_given(tmp_path: pathlib.Path) -> None:
    (tmp_path / "Inter.woff2").write_bytes(b"wOF2-font")
    b = load_brand(write(tmp_path, YAML + "font_file: Inter.woff2\n"))
    with respx.mock() as mock:
        mock.put(LABEL).respond(200, json={})
        mock.post(url__regex=rf"{re.escape(ASSETS)}/.*").respond(200, json={})
        mock.post(f"{LABEL}/_activate").respond(200, json={})
        apply_zitadel(b, BASE, "tok")
        font = [body for path, body in posted(mock) if path.endswith("/font")]
        assert len(font) == 1
        assert b"wOF2-font" in font[0]
        assert b"Content-Type: font/woff2" in font[0]


def test_apply_zitadel_treats_unchanged_policy_as_done(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path))
    with respx.mock(assert_all_called=True) as mock:
        mock.put(LABEL).respond(400, json={"code": 9, "message": "No changes (INSTANCE-28fHe)"})
        mock.post(url__regex=rf"{re.escape(ASSETS)}/.*").respond(200, json={})
        activate = mock.post(f"{LABEL}/_activate").respond(200, json={})
        apply_zitadel(b, BASE, "tok")
        assert activate.called


def test_apply_zitadel_reports_other_failures(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path))
    with respx.mock() as mock:
        mock.put(LABEL).respond(403, json={"message": "permission denied"})
        with pytest.raises(BrandError, match=r"403.*permission denied"):
            apply_zitadel(b, BASE, "tok")


def test_apply_lago_sends_legal_name_and_png_logo_through_graphql(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path))

    def graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        reply = httpx.post(
            "http://lago.test/graphql", json={"query": query, "variables": variables}
        )
        data: dict[str, Any] = reply.json()["data"]
        return data

    with respx.mock() as mock:
        route = mock.post("http://lago.test/graphql").respond(
            200, json={"data": {"updateOrganization": {"id": "o1"}}}
        )
        apply_lago(b, graphql)
        sent = json.loads(route.calls[0].request.content)
    assert "updateOrganization" in sent["query"]
    organization = sent["variables"]["i"]
    assert set(organization) == {"legalName", "logo"}
    assert organization["legalName"] == "Acme"
    prefix, _, data = organization["logo"].partition(",")
    assert prefix == "data:image/png;base64"
    assert base64.b64decode(data).startswith(b"\x89PNG\r\n\x1a\n")


def test_cli_css_only_writes_frontend_tokens(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "brand").mkdir()
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    write(tmp_path / "brand")
    monkeypatch.setattr(brand, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["brand.py", "--css-only"])
    brand.main()
    css = (tmp_path / "frontend" / "src" / "brand.css").read_text()
    assert css == css_tokens(load_brand(tmp_path / "brand" / "brand.yaml"))


@pytest.mark.parametrize(
    "section", ["light: [1, 2]", "light: {primary: '#3355ff', accent: '#ff7a33'}\ndark: red"]
)
def test_non_mapping_palettes_rejected(tmp_path: pathlib.Path, section: str) -> None:
    with pytest.raises(BrandError, match="mappings"):
        load_brand(write(tmp_path, f"name: Acme\nfont: Inter\nlogo: logo.svg\n{section}\n"))


def test_cli_reports_unreachable_service_without_traceback(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "brand").mkdir()
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    write(tmp_path / "brand")
    monkeypatch.setattr(brand, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["brand.py"])
    fake = types.SimpleNamespace(
        zitadel_endpoint=lambda: (BASE, {"Host": "auth.acme.localhost:8085"}),
        zitadel_admin_token=lambda: "tok",
        lago_graphql=None,
    )
    monkeypatch.setitem(sys.modules, "bootstrap", fake)
    with respx.mock() as mock:
        mock.put(LABEL).mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(SystemExit, match=r"request failed.*refused"):
            brand.main()
