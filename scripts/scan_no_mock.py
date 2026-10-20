"""Reject mock-like values in the active, served application surface.

The Stitch HTML design templates are served through the page routes and hydrated
by the runtime. Direct static template URLs are blocked. The scan covers active
backend, frontend, and page-template sources.
"""

from __future__ import annotations

import ast
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
STITCH = APP / "static" / "stitch"
ACTIVE_FRONTEND = (
    APP / "static" / "index.html",
    APP / "static" / "app.js",
    APP / "static" / "api.js",
    APP / "static" / "state.js",
    APP / "static" / "render.js",
    APP / "static" / "audio-worklet.js",
    APP / "static" / "styles.css",
    APP / "static" / "account-menu.js",
    APP / "static" / "account-menu.css",
    APP / "static" / "auth-page.js",
    APP / "static" / "auth.html",
)
FORBIDDEN = re.compile(r"Math\.random|faker|lorem", re.IGNORECASE)
FAKE_TIMER = re.compile(r"setTimeout\s*\([^)]*(?:progress|loading|result|analysis)", re.IGNORECASE | re.DOTALL)
NUMERIC_CHART_ARRAY = re.compile(
    r"(?:new\s+Chart|Chart\s*\()\s*[\s\S]{0,800}?(?:data|datasets)\s*:\s*\[\s*[\d\s.,+-]+\]",
    re.IGNORECASE,
)


class BindingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.bound: list[dict[str, object]] = []
        self.current: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if "data-bind" in attributes:
            self.current = {"tag": tag, "binding": attributes["data-bind"], "text": ""}
            self.bound.append(self.current)

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current["text"] = str(self.current["text"]) + data.strip()

    def handle_endtag(self, tag: str) -> None:
        if self.current is not None and self.current["tag"] == tag:
            self.current = None


def backend_metric_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    metric_keys = {"accuracy", "precision", "recall", "f1", "fpr", "fnr", "eer", "roc_auc", "total", "flagged"}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        route_paths = [
            decorator.args[0].value
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Call)
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
            and isinstance(decorator.args[0].value, str)
            and decorator.args[0].value.startswith("/api/")
        ]
        if not route_paths:
            continue
        for statement in ast.walk(node):
            if not isinstance(statement, ast.Return) or not isinstance(statement.value, ast.Dict):
                continue
            keys = {
                item.value
                for item in statement.value.keys
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }
            if keys & metric_keys and any(path_name in {"/api/model/metrics", "/api/dashboard/summary"} for path_name in route_paths):
                errors.append(f"{path}:{statement.lineno}: literal metric response")
    return errors


def main() -> int:
    paths = [path for path in ACTIVE_FRONTEND if path.exists()]
    paths += sorted((APP / "core").glob("*.py"))
    paths += sorted((APP / "db").glob("*.py"))
    paths.append(APP / "main.py")
    paths += sorted(STITCH.glob("*.html"))
    paths.append(APP / "static" / "stitch-runtime.js")
    errors: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN.search(text):
            errors.append(f"{path}: forbidden mock marker")
        if FAKE_TIMER.search(text):
            errors.append(f"{path}: fake progress timer pattern")
        if NUMERIC_CHART_ARRAY.search(text):
            errors.append(f"{path}: hard-coded numeric chart data")
        if path.suffix == ".html":
            parser = BindingParser()
            parser.feed(text)
            for binding in parser.bound:
                if binding["text"] not in ("", "—"):
                    errors.append(f"{path}: data-bind={binding['binding']!r} has non-neutral source text")
    errors.extend(backend_metric_literals(APP / "main.py"))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"No mock data patterns found in {len(paths)} active application files.")
    print("Stitch design templates are served on page routes; direct static template URLs remain blocked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
