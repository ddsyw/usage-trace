"""Phase 1: discover keyword usage sites across the project."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import classify_layer, load_profile

_CONTROL = {"if", "for", "while", "switch", "catch", "return", "new", "super", "this"}


def keyword_variants(keyword: str, extra_variants: list[str] | None = None) -> list[str]:
    """Expand a keyword into common naming variants (longest first)."""
    parts = [p for p in re.split(r"[_\-]+|(?<=[a-z0-9])(?=[A-Z])", keyword) if p] or [keyword]
    lower = "_".join(p.lower() for p in parts)
    pascal = "".join(p.capitalize() for p in parts)  # StoreNo
    camel = (
        parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
        if parts else keyword
    )
    variants = {
        keyword,
        lower,                                  # store_no
        lower.upper(),                          # STORE_NO
        "".join(p.lower() for p in parts),      # storeno
        "-".join(p.lower() for p in parts),     # store-no
        pascal,                                 # StoreNo
        camel,                                  # storeNo (normalized)
        lower + "s",                            # store_nos
        lower + "_list",
    }
    # camelCase / PascalCase plurals: storeNos / StoreNos (not only store_nos)
    if not keyword.lower().endswith("s"):
        variants.add(camel + "s")
        variants.add(pascal + "s")
    variants.update(v.strip() for v in (extra_variants or []) if v.strip())
    return sorted(variants, key=len, reverse=True)


def layer_of(file: str, layers: list[dict], text: str | None = None) -> str:
    """Classify a file by path and optional profile annotation/content matches."""
    return classify_layer(file, layers, text)


def _occurrence_type(text: str, match: re.Match) -> str:
    before = text[: match.start()].rstrip()
    if before.endswith("@"):
        return "annotation"
    seg = text[match.start(): match.end() + 1]
    if ('"' in seg) or ("'" in seg):
        return "string"
    if re.search(r"\b(public|private|protected|void|int|long|String|var|boolean)\b", before) \
            and "(" in text[match.start():]:
        return "definition"
    return "identifier"


def _line_comment_start(text: str) -> int | None:
    quote = ""
    escaped = False
    for i, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in {"'", '"'}:
            quote = ch
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            return i
    return None


def _code_portion(text: str) -> str:
    stripped = text.lstrip()
    if stripped.startswith(("/*", "*")):
        return ""
    comment_at = _line_comment_start(text)
    return text if comment_at is None else text[:comment_at]


def _variant_pattern(variants: list[str], *, compound: bool = False) -> re.Pattern[str]:
    """Build an alternation regex with identifier-aware boundaries.

    - Always reject matches glued inside longer alnum tokens (``id`` ∉ ``void`` /
      ``identity``).
    - For *compound* camelCase keywords (``storeNo``), also allow the PascalCase
      form to match at a camelCase boundary so ``getStoreNo`` and
      ``queryListByEntryNameAndStoreNo`` hit ``StoreNo``.
    """
    if not variants:
        return re.compile(r"(?!)")  # never matches
    alts: list[str] = []
    for v in variants:
        esc = re.escape(v)
        if compound and v[:1].isupper():
            # start of identifier OR after a lower/digit (camelCase segment)
            alts.append(rf"(?:(?<![A-Za-z0-9$])|(?<=[a-z0-9])){esc}(?![A-Za-z0-9$])")
        else:
            alts.append(rf"(?<![A-Za-z0-9$]){esc}(?![A-Za-z0-9$])")
    return re.compile("|".join(alts))


def discover(keyword: str, profile: dict, extra_variants: list[str] | None = None,
             index=None) -> list[dict]:
    variants = keyword_variants(keyword, extra_variants)
    parts = [p for p in re.split(r"[_\-]+|(?<=[a-z0-9])(?=[A-Z])", keyword) if p]
    compound = len(parts) > 1
    rx = _variant_pattern(variants, compound=compound)
    layers = profile.get("layers", [])
    sites: list[dict] = []
    paths = list(index.files.keys()) if index is not None else []
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        layer = index.layers.get(path) if index is not None else None
        for i, line in enumerate(text.splitlines(), 1):
            code = _code_portion(line)
            for m in rx.finditer(code):
                sites.append({
                    "file": path,
                    "line": i,
                    "col": m.start() + 1,
                    "occurrence_type": _occurrence_type(line, m),
                    "layer": layer or classify_layer(path, layers, text),
                    "snippet": line.strip(),
                })
    return sites


def main() -> None:
    ap = argparse.ArgumentParser(description="usage-trace Phase 1: discover usage sites.")
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--variants", default="")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    from index import ProjectIndex
    index = ProjectIndex.load_or_build(Path(args.root), profile)
    extra_variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    sites = discover(args.keyword, profile, extra_variants, index)
    json.dump(sites, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
