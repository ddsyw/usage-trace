"""Phase 1: discover keyword usage sites across the project."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import grep, load_profile

_CONTROL = {"if", "for", "while", "switch", "catch", "return", "new", "super", "this"}


def keyword_variants(keyword: str) -> list[str]:
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
    return sorted(variants, key=len, reverse=True)


def layer_of(file: str, layers: list[dict]) -> str:
    """Classify a file by its path (package) against layer path_hints."""
    fpath = str(file).replace("\\", "/")
    for L in layers:
        hint = L.get("path_hint")
        if hint and re.search(hint, fpath, re.IGNORECASE):
            return L["name"]
    return "Unknown"


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


def discover(keyword: str, root: Path, profile: dict) -> list[dict]:
    variants = keyword_variants(keyword)
    pattern = "|".join(re.escape(v) for v in variants)
    exclude = profile.get("exclude", {}).get("dirs", [])
    layers = profile.get("layers", [])
    sites: list[dict] = []
    for h in grep(pattern, Path(root), "*", exclude):
        m = re.search(pattern, h["text"])
        otype = _occurrence_type(h["text"], m) if m else "identifier"
        sites.append({
            "file": h["file"],
            "line": h["line"],
            "col": h["col"],
            "occurrence_type": otype,
            "layer": layer_of(h["file"], layers),
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
    sites = discover(args.keyword, Path(args.root), profile)
    json.dump(sites, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
