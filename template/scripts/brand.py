"""One file (brand/brand.yaml) drives the app's tokens, title, logo and font, Zitadel's login page and
Lago's invoices.

Zitadel v4.20.0: instance label policy via the admin API (PUT /admin/v1/policies/label, then
_activate) and logo/font uploads via the assets API (POST /assets/v1/instance/policy/label/...).
Lago v1.55.0: the REST organization update has no logo field, so name and logo go through the
GraphQL UpdateOrganization mutation. Lago accepts only PNG or JPEG logos (max 800 KB), so the SVG
is rendered to PNG first.
"""

import argparse
import base64
import html
import importlib
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import resvg_py
import yaml

from svg_check import svg_problem

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
ROOT = Path(__file__).resolve().parents[1]
FONT_MIME = {".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2"}
FONT_SUFFIXES = set(FONT_MIME)
FONT_NAME_BAD = re.compile(r'["\\;{}<>\n\r]')  # the name goes inside a CSS string
LOGO_PNG_WIDTH = 512
# Zitadel answers 400 "No changes" (INSTANCE-28fHe) when the policy already has these values.
ZITADEL_NOT_CHANGED = "INSTANCE-28fHe"

GraphQL = Callable[[str, dict[str, Any]], dict[str, Any]]


class BrandError(ValueError):
    pass


@dataclass(frozen=True)
class Palette:
    primary: str
    accent: str
    background: str
    foreground: str
    warn: str = "#d93025"


@dataclass(frozen=True)
class Brand:
    name: str
    logo_path: Path
    font: str
    light: Palette
    dark: Palette
    font_file: Path | None = None


def _colour(value: Any, field: str) -> str:
    if not isinstance(value, str) or not HEX.match(value):
        raise BrandError(f"{field}: colour must be like #3355ff")
    return value.lower()


def _lighten(hex_colour: str, amount: float = 0.25) -> str:
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _required(raw: dict[str, Any], key: str, where: str = "brand.yaml") -> Any:
    if raw.get(key) in (None, ""):
        raise BrandError(f"{where}: missing '{key}'")
    return raw[key]


def _inside_brand(folder: Path, raw: Any, field: str) -> Path:
    """Assets are copied into public/, so a path out of brand/ could publish any file on the machine."""
    resolved = (folder / str(raw)).resolve()
    if not resolved.is_relative_to(folder.resolve()):
        raise BrandError(f"{field} must be a file inside brand/, not {raw!r}")
    return resolved


def load_brand(path: Path) -> Brand:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise BrandError("brand.yaml must be a mapping")
    logo = _inside_brand(path.parent, _required(raw, "logo"), "logo")
    if logo.suffix.lower() != ".svg":
        raise BrandError(f"logo must be an .svg file, not {logo.name}")
    if not logo.is_file():
        raise BrandError(f"logo file {logo.name} not found")
    problem = svg_problem(logo.read_text(errors="replace"))
    if problem:
        raise BrandError(f"logo {logo.name} {problem}")
    font_file = None
    if raw.get("font_file"):
        font_file = _inside_brand(path.parent, raw["font_file"], "font_file")
        if not font_file.is_file() or font_file.suffix.lower() not in FONT_SUFFIXES:
            raise BrandError(
                f"font_file {font_file.name} must exist and be one of {sorted(FONT_SUFFIXES)}"
            )
    light_raw = _required(raw, "light")
    if not isinstance(light_raw, dict) or not isinstance(raw.get("dark") or {}, dict):
        raise BrandError(
            "'light' and 'dark' must be mappings like {primary: '#3355ff', accent: '#ff7a33'}"
        )
    light = Palette(
        _colour(_required(light_raw, "primary", "light"), "light.primary"),
        _colour(_required(light_raw, "accent", "light"), "light.accent"),
        _colour(light_raw.get("background", "#ffffff"), "light.background"),
        _colour(light_raw.get("foreground", "#111114"), "light.foreground"),
    )
    dark_raw = raw.get("dark") or {}
    dark = Palette(
        _colour(dark_raw.get("primary", _lighten(light.primary)), "dark.primary"),
        _colour(dark_raw.get("accent", _lighten(light.accent)), "dark.accent"),
        _colour(dark_raw.get("background", "#0b0b0c"), "dark.background"),
        _colour(dark_raw.get("foreground", "#ececee"), "dark.foreground"),
    )
    font = str(_required(raw, "font"))
    if FONT_NAME_BAD.search(font):
        raise BrandError(f'font {font!r} cannot contain " \\ ; {{ }} < > or a line break')
    return Brand(str(_required(raw, "name")), logo, font, light, dark, font_file)


def font_asset_name(font_file: Path) -> str:
    return f"brand-font{font_file.suffix.lower()}"


def css_tokens(brand: Brand) -> str:
    def block(selector: str, p: Palette, extra: str = "") -> str:
        return (
            f"{selector} {{\n  --brand-primary: {p.primary};\n  --brand-accent: {p.accent};\n"
            f"  --brand-background: {p.background};\n  --brand-foreground: {p.foreground};\n{extra}}}\n"
        )

    # A font name alone loads nothing: the browser needs it installed, or a font_file to download.
    # After it comes the Inter the app bundles (index.css imports it), so system-ui can't win first.
    font = f'  --brand-font: "{brand.font}", "Inter Variable", system-ui, sans-serif;\n'
    face = ""
    if brand.font_file:
        face = (
            f'@font-face {{\n  font-family: "{brand.font}";\n'
            f'  src: url("/{font_asset_name(brand.font_file)}");\n  font-display: swap;\n}}\n'
        )
    return (
        "/* Generated by `make brand` from brand/brand.yaml. Do not edit by hand. */\n"
        + face
        + block(":root", brand.light, font)
        + block(".dark", brand.dark)
    )


def zitadel_label_policy(brand: Brand) -> dict[str, Any]:
    return {
        "primaryColor": brand.light.primary,
        "backgroundColor": brand.light.background,
        "warnColor": brand.light.warn,
        "fontColor": brand.light.foreground,
        "primaryColorDark": brand.dark.primary,
        "backgroundColorDark": brand.dark.background,
        "warnColorDark": brand.dark.warn,
        "fontColorDark": brand.dark.foreground,
        "hideLoginNameSuffix": True,
        "disableWatermark": True,
    }


def zitadel_login_text(brand: Brand) -> dict[str, Any]:
    """The English login texts that would otherwise name Zitadel on the product's sign-in pages."""
    return {
        "instance": True,
        "locale": "en",
        "translations": {
            "common": {"title": f"Login with {brand.name}"},
            "register": {"description": f"Create your {brand.name} account."},
        },
    }


def logo_svg(brand: Brand, colour: str) -> str:
    """The logo with `currentColor` replaced, since an <img> or a PNG has no text colour to inherit."""
    return re.sub("currentColor", colour, brand.logo_path.read_text(), flags=re.IGNORECASE)


def logo_png(brand: Brand) -> bytes:
    try:
        return resvg_py.svg_to_bytes(
            svg_string=logo_svg(brand, brand.light.primary), width=LOGO_PNG_WIDTH
        )
    except ValueError as exc:
        raise BrandError(f"logo {brand.logo_path.name} cannot be rendered: {exc}") from exc


def frontend_files(brand: Brand, frontend: Path) -> dict[str, bytes]:
    """Every file `make brand` writes under frontend/, by path relative to it, with its content."""
    logo = logo_svg(brand, brand.light.primary).encode()  # an <img> has no text colour for currentColor
    files = {
        "src/brand.css": css_tokens(brand).encode(),
        "public/logo.svg": logo,
        "public/favicon.svg": logo,
    }
    if brand.font_file:
        files[f"public/{font_asset_name(brand.font_file)}"] = brand.font_file.read_bytes()
    index = frontend / "index.html"
    if index.is_file():
        title = f"<title>{html.escape(brand.name, quote=False)}</title>"
        text = re.sub(r"<title>.*?</title>", lambda _: title, index.read_text(), count=1, flags=re.S)
        files["index.html"] = text.encode()
    return files


def write_frontend(brand: Brand, frontend: Path) -> None:
    for name, content in frontend_files(brand, frontend).items():
        (frontend / name).parent.mkdir(exist_ok=True)
        (frontend / name).write_bytes(content)


def stale_files(brand: Brand, frontend: Path) -> list[str]:
    """Generated files that differ from what brand.yaml says. Reads only, so `make check` changes nothing."""
    stale = []
    for name, content in frontend_files(brand, frontend).items():
        current = frontend / name
        if not current.is_file() or current.read_bytes() != content:
            stale.append(f"frontend/{name}")
    return stale


def _check(response: httpx.Response, what: str) -> None:
    if response.is_error:
        raise BrandError(f"{what} failed: HTTP {response.status_code} {response.text[:300]}")


def apply_zitadel(
    brand: Brand, api_url: str, token: str, extra_headers: dict[str, str] | None = None
) -> None:
    headers = {"Authorization": f"Bearer {token}", **(extra_headers or {})}
    uploads = [
        ("logo", "logo.svg", logo_svg(brand, brand.light.primary).encode(), "image/svg+xml"),
        (
            "logo/dark",
            "logo-dark.svg",
            logo_svg(brand, brand.dark.primary).encode(),
            "image/svg+xml",
        ),
    ]
    if brand.font_file:
        uploads.append(
            (
                "font",
                brand.font_file.name,
                brand.font_file.read_bytes(),
                FONT_MIME[brand.font_file.suffix.lower()],
            )
        )
    with httpx.Client(base_url=api_url, headers=headers, timeout=15.0) as http:
        put = http.put("/admin/v1/policies/label", json=zitadel_label_policy(brand))
        if not (put.status_code == 400 and ZITADEL_NOT_CHANGED in put.text):
            _check(put, "Zitadel label policy update")
        for target, filename, content, mime in uploads:
            reply = http.post(
                f"/assets/v1/instance/policy/label/{target}",
                files={"file": (filename, content, mime)},
            )
            _check(reply, f"Zitadel {target} upload")
        _check(
            http.post("/admin/v1/policies/label/_activate", json={}),
            "Zitadel label policy activation",
        )
        _check(
            http.put("/v2/settings/hosted_login_translation", json=zitadel_login_text(brand)),
            "Zitadel login text update",
        )


def apply_lago(brand: Brand, graphql: GraphQL) -> None:
    """The organization, then its billing entities, because invoices use the billing entity's logo.

    Updating the organization also gives the default billing entity a logo row with no file behind it
    (lago-api v1.55.0), and every invoice PDF then fails with ActiveStorage::FileNotFoundError.
    """
    logo = "data:image/png;base64," + base64.b64encode(logo_png(brand)).decode()
    branded = {"legalName": brand.name, "logo": logo}
    graphql("mutation($i: UpdateOrganizationInput!){updateOrganization(input:$i){id}}", {"i": branded})
    entities = graphql("query{billingEntities{collection{id}}}", {})["billingEntities"]["collection"]
    for entity in entities:
        graphql(
            "mutation($i: UpdateBillingEntityInput!){updateBillingEntity(input:$i){id}}",
            {"i": {"id": entity["id"], **branded}},
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--css-only", action="store_true", help="only the files under frontend/")
    parser.add_argument("--check", action="store_true", help="fail if those files are out of date; change nothing")
    args = parser.parse_args()
    try:
        brand = load_brand(ROOT / "brand" / "brand.yaml")
        if args.check:
            stale = stale_files(brand, ROOT / "frontend")
            if stale:
                sys.exit(f"out of date with brand/ and scripts/brand.py: {', '.join(stale)}. Run `make regen`.")
            return
        write_frontend(brand, ROOT / "frontend")
        print("wrote frontend/src/brand.css, the page title, logo and favicon")
        if args.css_only:
            return
        bootstrap = importlib.import_module("bootstrap")
        api_url, host = bootstrap.zitadel_endpoint()  # 127.0.0.1 plus the instance's Host header
        apply_zitadel(brand, api_url, bootstrap.zitadel_admin_token(), host)
        apply_lago(brand, bootstrap.lago_graphql)
        bootstrap.compose("restart", "zitadel-login")  # it caches login texts until restarted
        print("applied brand to Zitadel and Lago")
    except BrandError as exc:
        sys.exit(f"brand: {exc}")
    except httpx.HTTPError as exc:
        # Every step is idempotent, so fix the cause and re-run `make brand`.
        sys.exit(f"brand: request failed ({type(exc).__name__}): {exc}")


if __name__ == "__main__":
    main()
