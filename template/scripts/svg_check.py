"""Is this logo safe to serve? /logo.svg shares an origin with the app, whose tokens are in localStorage,
and opening an SVG directly runs its scripts. Standard library only: Copier's task imports it before any
virtual environment exists, under whatever python3 is on PATH (macOS's own is 3.9, so keep it 3.9-safe)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

URL_NOISE = re.compile(r"[\s\x00-\x1f]+")  # browsers ignore these inside a URL's scheme


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()


def svg_problem(text: str) -> str | None:
    """What is wrong with this SVG, in a few words to follow "logo x.svg", or None when it is fine."""
    upper = text.upper()
    if "<!ENTITY" in upper or "<?XML-STYLESHEET" in upper:
        return ("uses XML entities or a stylesheet instruction, as some design tools export. Re-export it as plain "
                "SVG (in Illustrator, File > Export As > SVG, not Save As) or remove them")
    try:
        root = ET.fromstring(text)  # noqa: S314
    except ET.ParseError as exc:
        return f"is not well-formed XML ({exc})"
    if _local(str(root.tag)) != "svg":
        return "is not an SVG"
    for element in root.iter():
        tag = _local(str(element.tag))
        if tag == "script":
            return "contains a <script>; remove it"
        if tag == "foreignobject":
            return "contains a <foreignObject>; remove it"
        for name, value in element.attrib.items():
            if _local(name).startswith("on"):
                return f"has an event attribute ({_local(name)}); remove it"
            if "javascript:" in URL_NOISE.sub("", value).lower():
                return "links to javascript:; remove it"
    return None
