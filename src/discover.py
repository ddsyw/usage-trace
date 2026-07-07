"""Phase 1: discover keyword usage sites across the project."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import classify_layer, grep, load_profile

_CONTROL = {"if", "for", "while", "switch", "catch", "return", "new", "super", "this"}


def keyword_variants(keyword: str, extra_variants: list[str] | None = None) -> list[str]:
    """Expand a keyword into common naming variants (longest first)."""
    parts = [p for p in re.split(r"[_\-]+|(?<=[a-z0-9])(?=[A-Z])", keyword) if p] or [keyword]
    lower = "_".join(p.lower() for p in parts)
    variants = {
        keyword,
        lower,                                  # store_no
        lower.upper(),                          # STORE_NO
        "".join(p.lower() for p in parts),      # storeno
        "-".join(p.lower() for p in parts),     # store-no
        "".join(p.capitalize() for p in parts), # StoreNo
        lower + "s",                            # store_nos
        lower + "_list",
    }
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


def discover(keyword: str, root: Path, profile: dict,
             extra_variants: list[str] | None = None) -> list[dict]:
    variants = keyword_variants(keyword, extra_variants)
    pattern = "|".join(re.escape(v) for v in variants)
    exclude = profile.get("exclude", {}).get("dirs", [])
    layers = profile.get("layers", [])
    sites: list[dict] = []
    file_text_cache: dict[str, str] = {}
    for h in grep(pattern, Path(root), "*", exclude):
        code = _code_portion(h["text"])
        m = re.search(pattern, code)
        if not m:
            continue
        if h["file"] not in file_text_cache:
            try:
                file_text_cache[h["file"]] = Path(h["file"]).read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                file_text_cache[h["file"]] = ""
        otype = _occurrence_type(h["text"], m) if m else "identifier"
        sites.append({
            "file": h["file"],
            "line": h["line"],
            "col": m.start() + 1,
            "occurrence_type": otype,
            "layer": layer_of(h["file"], layers, file_text_cache[h["file"]]),
            "snippet": h["text"].strip(),
        })
    return sites


def main() -> None:
    ap = argparse.ArgumentParser(description="codex-find Phase 1: discover usage sites.")
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--variants", default="",
                    help="comma-separated extra variants (optional; auto-expanded if empty)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    extra_variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    sites = discover(args.keyword, Path(args.root), profile, extra_variants)
    json.dump(sites, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
