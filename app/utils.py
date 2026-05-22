from __future__ import annotations

import html
import re
from typing import Any

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def strip_html(value: str | None) -> str | None:
    if not value:
        return value
    text = TAG_RE.sub(" ", value)
    return compact(html.unescape(text))


def compact(value: str | None) -> str | None:
    if value is None:
        return None
    return SPACE_RE.sub(" ", str(value)).strip()


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def join_values(values: list[Any] | tuple[Any, ...] | None, sep: str = ", ") -> str | None:
    if not values:
        return None
    cleaned = [compact(str(v)) for v in values if compact(str(v))]
    return sep.join(cleaned) if cleaned else None


def safe_get(mapping: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current
