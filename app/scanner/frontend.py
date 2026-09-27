"""
Frontend scanner — uses regex to extract fetch() calls and their JSON body fields
from JavaScript source files.

No JS engine required.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from app.analyzer.contracts import FrontendCall

# Matches: fetch("/some/path", { method: "POST", ..., body: JSON.stringify({...}) })
# We capture the path and the stringified object in two separate passes.

_FETCH_CALL_RE = re.compile(
    r"""fetch\s*\(\s*["'`](?P<path>/[^"'`]*?)["'`]""",
    re.MULTILINE,
)

_METHOD_RE = re.compile(
    r"""method\s*:\s*["'`](?P<method>[A-Z]+)["'`]""",
    re.IGNORECASE,
)

_STRINGIFY_BODY_RE = re.compile(
    r"""JSON\.stringify\s*\(\s*\{(?P<body>[^}]*)\}""",
    re.DOTALL,
)

_OBJECT_KEY_RE = re.compile(
    r"""(?:^|,)\s*["'`]?(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)["'`]?\s*:""",
    re.MULTILINE,
)


def _extract_fields_from_object_literal(body: str) -> List[str]:
    """Extract property keys from a JS object literal body string."""
    fields = []
    for m in _OBJECT_KEY_RE.finditer(body):
        key = m.group("key")
        if key and not key.startswith("//"):
            fields.append(key)
    return fields


def _find_fetch_blocks(source: str) -> List[dict]:
    """
    Find all fetch() call-sites in `source`.
    Returns list of dicts with keys: path, method, fields.
    """
    results = []
    for match in _FETCH_CALL_RE.finditer(source):
        path = match.group("path")
        # Grab a window of ~400 chars after the path to find method + body
        window_start = match.start()
        window_end = min(len(source), match.start() + 600)
        window = source[window_start:window_end]

        # Determine HTTP method (default POST when body is present, else GET)
        method_match = _METHOD_RE.search(window)
        method = method_match.group("method").upper() if method_match else "GET"

        # Extract fields from JSON.stringify({...})
        fields: List[str] = []
        stringify_match = _STRINGIFY_BODY_RE.search(window)
        if stringify_match:
            fields = _extract_fields_from_object_literal(stringify_match.group("body"))
            if not method_match:
                method = "POST"  # presence of a body implies POST

        results.append({"path": path, "method": method, "fields": fields})
    return results


def scan_frontend(directory: Path) -> List[FrontendCall]:
    """
    Scan all .js files under `directory` for fetch() API calls.

    Returns a list of FrontendCall objects.
    """
    directory = Path(directory)
    calls: List[FrontendCall] = []

    for js_file in sorted(directory.rglob("*.js")):
        try:
            source = js_file.read_text(encoding="utf-8")
        except OSError:
            continue

        rel_file = str(js_file.relative_to(directory))
        for block in _find_fetch_blocks(source):
            calls.append(
                FrontendCall(
                    method=block["method"],
                    path=block["path"],
                    file=rel_file,
                    fields=block["fields"],
                )
            )
    return calls


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("demo_project/frontend")
    results = scan_frontend(target)
    for r in results:
        print(r)
