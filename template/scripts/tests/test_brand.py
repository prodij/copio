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
TEXT = f"{BASE}/v2/settings/hosted_login_translation"
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
    assert '--brand-font: "Inter", "Inter Variable", system-ui, sans-serif;' in css
    assert "@font-face" not in css


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
        text = mock.put(TEXT).respond(200, json={})
        apply_zitadel(b, BASE, "tok")
        assert json.loads(text.calls[0].request.content)["translations"]["register"]["description"] == (
            "Create your Acme account."
        )
        order = [(c.request.method, c.request.url.path) for c in mock.calls]
        assert order == [
            ("PUT", "/admin/v1/policies/label"),
            ("POST", "/assets/v1/instance/policy/label/logo"),
            ("POST", "/assets/v1/instance/policy/label/logo/dark"),
            ("POST", "/admin/v1/policies/label/_activate"),
            ("PUT", "/v2/settings/hosted_login_translation"),
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
        mock.put(TEXT).respond(200, json={})
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
        mock.put(TEXT).respond(200, json={})
        apply_zitadel(b, BASE, "tok")
        assert activate.called


def test_apply_zitadel_reports_other_failures(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path))
    with respx.mock() as mock:
        mock.put(LABEL).respond(403, json={"message": "permission denied"})
        with pytest.raises(BrandError, match=r"403.*permission denied"):
            apply_zitadel(b, BASE, "tok")


def test_apply_lago_brands_the_organization_and_then_each_billing_entity(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path))
    sent: list[tuple[str, dict[str, Any]]] = []

    def graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        sent.append((query, variables))
        return {"billingEntities": {"collection": [{"id": "e1"}, {"id": "e2"}]}} if "collection" in query else {}

    apply_lago(b, graphql)
    assert ["updateOrganization" in sent[0][0], "billingEntities" in sent[1][0]] == [True, True]
    organization = sent[0][1]["i"]
    assert set(organization) == {"legalName", "logo"}
    assert organization["legalName"] == "Acme"
    prefix, _, data = organization["logo"].partition(",")
    assert prefix == "data:image/png;base64"
    assert base64.b64decode(data).startswith(b"\x89PNG\r\n\x1a\n")
    # Last, or invoice PDFs fail: updating the organization leaves the entity's logo with no file.
    assert all("updateBillingEntity" in query for query, _ in sent[2:])
    assert [variables["i"] for _, variables in sent[2:]] == [{"id": e, **organization} for e in ("e1", "e2")]


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


def frontend_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "index.html").write_text("<head>\n  <title>Old name</title>\n</head>\n")
    return frontend


def test_frontend_gets_the_coloured_logo_favicon_and_title(tmp_path: pathlib.Path) -> None:
    frontend = frontend_dir(tmp_path)
    (tmp_path / "brand").mkdir()
    b = load_brand(write(tmp_path / "brand", YAML.replace("name: Acme", "name: A & B")))
    brand.write_frontend(b, frontend)
    logo = (frontend / "public" / "logo.svg").read_text()
    assert 'fill="#3355ff"' in logo and "currentColor" not in logo
    assert (frontend / "public" / "favicon.svg").read_text() == logo
    assert (frontend / "index.html").read_text() == "<head>\n  <title>A &amp; B</title>\n</head>\n"
    assert (frontend / "src" / "brand.css").read_text() == css_tokens(b)


def test_font_file_is_served_to_the_app(tmp_path: pathlib.Path) -> None:
    frontend = frontend_dir(tmp_path)
    (tmp_path / "brand").mkdir()
    (tmp_path / "brand" / "Mine.WOFF2").write_bytes(b"wOF2-font")
    b = load_brand(write(tmp_path / "brand", YAML.replace("font: Inter", "font: Mine") + "font_file: Mine.WOFF2\n"))
    brand.write_frontend(b, frontend)
    assert (frontend / "public" / "brand-font.woff2").read_bytes() == b"wOF2-font"
    css = (frontend / "src" / "brand.css").read_text()
    assert 'font-family: "Mine";' in css
    assert 'src: url("/brand-font.woff2");' in css


def test_stale_files_names_what_differs_and_touches_nothing(tmp_path: pathlib.Path) -> None:
    frontend = frontend_dir(tmp_path)
    (tmp_path / "brand").mkdir()
    b = load_brand(write(tmp_path / "brand"))
    assert sorted(brand.stale_files(b, frontend)) == [
        "frontend/index.html", "frontend/public/favicon.svg", "frontend/public/logo.svg", "frontend/src/brand.css"]
    assert not (frontend / "public").exists()
    assert "Old name" in (frontend / "index.html").read_text()
    brand.write_frontend(b, frontend)
    assert brand.stale_files(b, frontend) == []
    (frontend / "src" / "brand.css").write_text("/* older tokens */")
    assert brand.stale_files(b, frontend) == ["frontend/src/brand.css"]


def test_cli_check_fails_naming_make_regen_and_leaves_the_tree_alone(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "brand").mkdir()
    write(tmp_path / "brand")
    frontend = frontend_dir(tmp_path)
    brand.write_frontend(load_brand(tmp_path / "brand" / "brand.yaml"), frontend)
    monkeypatch.setattr(brand, "ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["brand.py", "--check"])
    brand.main()  # in step: says nothing, changes nothing
    assert capsys.readouterr().out == ""
    (frontend / "src" / "brand.css").write_text("/* older tokens */")
    with pytest.raises(SystemExit, match=r"frontend/src/brand\.css.*make regen"):
        brand.main()
    assert (frontend / "src" / "brand.css").read_text() == "/* older tokens */"


@pytest.mark.parametrize(
    ("line", "field"),
    [
        ("logo: ../x.svg", "logo"),
        ("logo: /tmp/x.svg", "logo"),
        ("font_file: ../x.woff2", "font_file"),
        ("font_file: /tmp/x.woff2", "font_file"),
    ],
)
def test_asset_paths_must_stay_inside_brand(tmp_path: pathlib.Path, line: str, field: str) -> None:
    (tmp_path / "x.svg").write_text(SVG)
    (tmp_path / "x.woff2").write_bytes(b"wOF2")
    (tmp_path / "brand").mkdir()
    text = YAML if field != "logo" else YAML.replace("logo: logo.svg", "")
    with pytest.raises(BrandError, match=rf"{field} must be a file inside brand/"):
        load_brand(write(tmp_path / "brand", f"{text}{line}\n"))


def test_a_symlink_out_of_brand_is_refused(tmp_path: pathlib.Path) -> None:
    (tmp_path / "secret.svg").write_text(SVG)
    (tmp_path / "brand").mkdir()
    (tmp_path / "brand" / "link.svg").symlink_to(tmp_path / "secret.svg")
    with pytest.raises(BrandError, match="logo must be a file inside brand/"):
        load_brand(write(tmp_path / "brand", YAML.replace("logo.svg", "link.svg")))


def test_logo_must_be_an_svg(tmp_path: pathlib.Path) -> None:
    (tmp_path / "logo.png").write_bytes(b"png")
    with pytest.raises(BrandError, match=r"logo must be an \.svg"):
        load_brand(write(tmp_path, YAML.replace("logo.svg", "logo.png")))


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ("<script>alert(1)</script>", "script"),
        ("<SCRIPT>alert(1)</SCRIPT>", "script"),
        ("<svg:script xmlns:svg='http://www.w3.org/2000/svg'>alert(1)</svg:script>", "script"),
        ("<rect onload='alert(1)'/>", "onload"),
        ("<rect ONCLICK='alert(1)'/>", "onclick"),
        ("<foreignObject/>", "foreignObject"),
        ("<a href='javascript:alert(1)'/>", "javascript:"),
        ("<a href=' JaVa&#10;Script:alert(1)'/>", "javascript:"),
    ],
)
def test_unsafe_logos_are_refused(tmp_path: pathlib.Path, body: str, said: str) -> None:
    (tmp_path / "logo.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>')
    p = tmp_path / "brand.yaml"
    p.write_text(YAML)
    with pytest.raises(BrandError, match=said):
        load_brand(p)


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ('<!DOCTYPE svg [<!ENTITY x "y">]><svg xmlns="http://www.w3.org/2000/svg"/>', "entities"),
        ("<svg><rect></svg>", "well-formed"),
        ('<html xmlns="http://www.w3.org/1999/xhtml"/>', "not an SVG"),
    ],
)
def test_logos_that_cant_be_read_are_refused(tmp_path: pathlib.Path, text: str, said: str) -> None:
    (tmp_path / "logo.svg").write_text(text)
    p = tmp_path / "brand.yaml"
    p.write_text(YAML)
    with pytest.raises(BrandError, match=said):
        load_brand(p)


def test_an_ordinary_logo_with_namespaces_and_styles_is_fine(tmp_path: pathlib.Path) -> None:
    (tmp_path / "logo.svg").write_text(
        '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        '<style>.a{fill:red}</style><g id="once"><use xlink:href="#a"/></g></svg>')
    p = tmp_path / "brand.yaml"
    p.write_text(YAML)
    load_brand(p)


@pytest.mark.parametrize("font", ['Bad"Font', "Back\\\\slash", "Semi;colon", "Curly{"])
def test_fonts_that_would_break_the_css_are_refused(tmp_path: pathlib.Path, font: str) -> None:
    with pytest.raises(BrandError, match="font"):
        load_brand(write(tmp_path, YAML.replace("font: Inter", f"font: {json.dumps(font)}")))


def test_ordinary_font_names_are_kept(tmp_path: pathlib.Path) -> None:
    b = load_brand(write(tmp_path, YAML.replace("font: Inter", 'font: "Bob\'s & Sans 2"')))
    assert '--brand-font: "Bob\'s & Sans 2",' in css_tokens(b)


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


def test_on_aws_the_bundle_has_no_frontend_to_write(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "brand").mkdir()  # no frontend/ here, as in the server's bundle
    write(tmp_path / "brand")
    monkeypatch.setattr(brand, "ROOT", tmp_path)
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    monkeypatch.setattr("sys.argv", ["brand.py", "--css-only"])
    brand.main()
    assert not (tmp_path / "frontend").exists()
