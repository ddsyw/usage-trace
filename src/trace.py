"""Phase 2: build the call graph by walking callers (up) and callees (down)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable

from common import add_edge, add_node, grep, load_profile, new_graph

HARD_DEPTH_CAP = 8
# A Java method signature: <modifiers/type> name(params) [throws ...] { or ;
_SIG_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(throws\s+[\w.,\s]+)?\s*([{;])\s*$")
_CONTROL = {"if", "for", "while", "switch", "catch", "return", "new", "super", "this"}


# ---- Pure walk: cycle-safe, depth-capped ----
def walk(seeds: list[str], neighbors: Callable[[str, str], list[str]],
         depth: int) -> tuple[set[str], list[tuple[str, str, str]]]:
    depth = min(depth, HARD_DEPTH_CAP)
    visited: set[str] = set(seeds)
    edges: list[tuple[str, str, str]] = []
    frontier = [(s, 0) for s in seeds]
    while frontier:
        node, d = frontier.pop(0)
        if d >= depth:
            continue
        for nb in neighbors(node, "down"):
            if nb == node:
                continue
            if nb in visited:
                edges.append((node, nb, "inferred"))   # back / cross edge
                continue
            edges.append((node, nb, "confirmed"))
            visited.add(nb)
            frontier.append((nb, d + 1))
    return visited, edges


# ---- Java method span detection ----
def _strip_comment(line: str) -> str:
    return line.split("//", 1)[0].rstrip()


def _current_class(lines: list[str], upto: int) -> str | None:
    cls = None
    for i in range(upto):
        m = re.search(r"\b(?:class|interface|enum)\s+(\w+)", lines[i])
        if m:
            cls = m.group(1)
    return cls


def find_enclosing_unit(file: Path, target_line: int) -> dict | None:
    try:
        lines = Path(file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    spans: list[tuple[int, int, str]] = []  # (sig_line, end_line, name)
    i = 0
    while i < len(lines):
        raw = _strip_comment(lines[i])
        m = _SIG_RE.search(raw)
        if m and m.group(1) not in _CONTROL:
            name = m.group(1)
            if m.group(4) == ";":               # interface / abstract method
                spans.append((i + 1, i + 1, name))
            else:                                # '{' — brace match for end
                depth = raw.count("{") - raw.count("}")
                j = i + 1
                while j < len(lines) and depth > 0:
                    seg = _strip_comment(lines[j])
                    depth += seg.count("{") - seg.count("}")
                    j += 1
                spans.append((i + 1, j, name))
        i += 1
    for sig, end, name in spans:
        if sig <= target_line <= end:
            cls = _current_class(lines, sig - 1)
            qual = f"{cls}.{name}" if cls else name
            return {"id": qual, "name": name, "qualname": qual,
                    "file": str(file), "line": sig, "end_line": end}
    return None


def _layer_of_file(file: str, layers: list[dict]) -> str:
    fpath = str(file).replace("\\", "/")
    for L in layers:
        hint = L.get("path_hint")
        if hint and re.search(hint, fpath, re.IGNORECASE):
            return L["name"]
    return "Unknown"


def _callees_in_unit(unit: dict, profile: dict) -> list[str]:
    patterns = profile.get("call_patterns", {})
    regs = []
    if "method_invocation" in patterns:
        regs.append(re.compile(patterns["method_invocation"]))
    if "chain_step" in patterns:
        regs.append(re.compile(patterns["chain_step"]))
    try:
        lines = Path(unit["file"]).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    body = lines[unit["line"] - 1: unit["end_line"]]
    names: list[str] = []
    seen: set[str] = set()
    for ln in body:
        seg = _strip_comment(ln)
        for rx in regs:
            for m in rx.finditer(seg):
                nm = m.group(1)
                if nm in _CONTROL or nm in seen:
                    continue
                seen.add(nm)
                names.append(nm)
    return names


def _resolve_definition(method_name: str, root: Path, exclude: list[str]) -> list[dict]:
    """Find units whose declared method name == method_name (definition lines)."""
    pat = rf"\b{re.escape(method_name)}\s*\("
    hits = grep(pat, root, "*", exclude)
    out: list[dict] = []
    seen: set[str] = set()
    for h in hits:
        u = find_enclosing_unit(Path(h["file"]), h["line"])
        if u and u["name"] == method_name and u["line"] == h["line"]:
            if u["id"] not in seen:
                seen.add(u["id"])
                out.append(u)
    return out


def _callers_of(unit: dict, root: Path, exclude: list[str]) -> list[dict]:
    pat = rf"\b{re.escape(unit['name'])}\s*\("
    hits = grep(pat, root, "*", exclude)
    callers: list[dict] = []
    seen: set[str] = set()
    for h in hits:
        if Path(h["file"]) == Path(unit["file"]) and h["line"] == unit["line"]:
            continue  # the definition itself, not a call
        enc = find_enclosing_unit(Path(h["file"]), h["line"])
        if enc and enc["id"] != unit["id"] and enc["id"] not in seen:
            seen.add(enc["id"])
            callers.append(enc)
    return callers


def trace(usages: list[dict], root: Path, profile: dict, depth: int = 4) -> dict:
    layers = profile.get("layers", [])
    exclude = profile.get("exclude", {}).get("dirs", [])
    g = new_graph({"depth": min(depth, HARD_DEPTH_CAP)})

    seeds: list[dict] = []
    seed_ids: set[str] = set()
    usage_by_unit: dict[str, list[dict]] = {}
    for site in usages:
        u = find_enclosing_unit(Path(site["file"]), site["line"])
        if not u:
            continue
        if u["id"] not in seed_ids:
            seed_ids.add(u["id"])
            seeds.append(u)
            usage_by_unit[u["id"]] = []
        usage_by_unit[u["id"]].append({
            "file": site["file"], "line": site["line"], "col": site.get("col"),
            "occurrence_type": site.get("occurrence_type"), "snippet": site.get("snippet"),
        })

    known: dict[str, dict] = {u["id"]: u for u in seeds}

    def neighbors_down(uid: str, _dir: str) -> list[str]:
        u = known.get(uid)
        if not u:
            return []
        out: list[str] = []
        for name in _callees_in_unit(u, profile):
            for tgt in _resolve_definition(name, root, exclude):
                if tgt["id"] == uid:
                    continue
                if tgt["id"] not in known:
                    known[tgt["id"]] = tgt
                out.append(tgt["id"])
        return out

    def neighbors_up(uid: str, _dir: str) -> list[str]:
        u = known.get(uid)
        if not u:
            return []
        out: list[str] = []
        for c in _callers_of(u, root, exclude):
            if c["id"] not in known:
                known[c["id"]] = c
            out.append(c["id"])
        return out

    seed_list = [u["id"] for u in seeds]
    _, down_edges = walk(seed_list, neighbors_down, depth)
    _, up_edges = walk(seed_list, neighbors_up, depth)

    for uid, u in known.items():
        add_node(g, {
            "id": uid, "kind": "unit", "label": uid,
            "layer": _layer_of_file(u["file"], layers),
            "file": u["file"], "line": u["line"],
            "usages": usage_by_unit.get(uid, []),
        })
    for frm, to, conf in down_edges:
        add_edge(g, frm, to, "call", conf)
    # up_edges: walk emitted (unit -> caller); flip so edge is caller -> callee
    for frm, to, conf in up_edges:
        add_edge(g, to, frm, "call", conf)
    return g


def main() -> None:
    ap = argparse.ArgumentParser(description="codex-find Phase 2: build call graph.")
    ap.add_argument("--usages", required=True, help="path to usages JSON (from discover)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--depth", type=int, default=4)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    usages = json.loads(Path(args.usages).read_text(encoding="utf-8"))
    g = trace(usages, Path(args.root), profile, args.depth)
    json.dump(g, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
