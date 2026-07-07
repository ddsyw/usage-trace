"""Phase 2: build the call graph by walking callers (up) and callees (down)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable

from common import add_edge, add_node, classify_layer, grep, load_profile, new_graph

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


def _class_name(unit: dict) -> str | None:
    qual = unit.get("id") or unit.get("qualname") or ""
    return qual.split(".", 1)[0] if "." in qual else None


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
    try:
        text = Path(file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    return classify_layer(file, layers, text)


def _symbol_types(unit: dict) -> dict[str, str]:
    try:
        lines = Path(unit["file"]).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    cls = _class_name(unit)
    types = {"this": cls} if cls else {}
    field_rx = re.compile(
        r"\b(?:private|protected|public)?\s*(?:final\s+)?([A-Z]\w*)\s+([A-Za-z_]\w*)\s*(?:[=;])"
    )
    for ln in lines:
        m = field_rx.search(_strip_comment(ln))
        if m:
            types[m.group(2)] = m.group(1)
    sig = _strip_comment(lines[unit["line"] - 1]) if unit.get("line") else ""
    params = sig[sig.find("(") + 1:sig.rfind(")")] if "(" in sig and ")" in sig else ""
    for part in params.split(","):
        bits = part.strip().split()
        if len(bits) >= 2 and re.match(r"[A-Z]\w*", bits[-2]):
            types[bits[-1]] = bits[-2]
    return types


def _callee_refs_in_unit(unit: dict, profile: dict) -> list[tuple[str, str | None]]:
    patterns = profile.get("call_patterns", {})
    method_rx = re.compile(patterns.get("method_invocation", r"\b([A-Za-z_][\w]*)\s*\("))
    chained_rx = re.compile(r"\b([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(")
    try:
        lines = Path(unit["file"]).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    body = lines[unit["line"] - 1: unit["end_line"]]
    refs: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for offset, ln in enumerate(body):
        seg = _strip_comment(ln)
        if offset == 0 and "{" in seg:
            seg = seg.split("{", 1)[1]
        elif offset == 0:
            continue
        chained_spans = []
        for m in chained_rx.finditer(seg):
            receiver, nm = m.group(1), m.group(2)
            if nm in _CONTROL:
                continue
            ref = (nm, receiver)
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
            chained_spans.append((m.start(2), m.end(2)))
        for m in method_rx.finditer(seg):
            nm = m.group(1)
            if nm in _CONTROL:
                continue
            if any(start <= m.start(1) < end for start, end in chained_spans):
                continue
            ref = (nm, None)
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
    return refs


def _callees_in_unit(unit: dict, profile: dict) -> list[str]:
    return [name for name, _receiver in _callee_refs_in_unit(unit, profile)]


def _resolve_definition(method_name: str, root: Path, exclude: list[str],
                        target_class: str | None = None) -> list[dict]:
    """Find units whose declared method name == method_name (definition lines)."""
    pat = rf"\b{re.escape(method_name)}\s*\("
    hits = grep(pat, root, "*", exclude)
    out: list[dict] = []
    seen: set[str] = set()
    for h in hits:
        u = find_enclosing_unit(Path(h["file"]), h["line"])
        if u and u["name"] == method_name and u["line"] == h["line"]:
            if target_class and u["id"] != f"{target_class}.{method_name}":
                continue
            if u["id"] not in seen:
                seen.add(u["id"])
                out.append(u)
    return out


def _receiver_for_call(text: str, method_name: str) -> str | None:
    m = re.search(rf"\b([A-Za-z_]\w*)\s*\.\s*{re.escape(method_name)}\s*\(", _strip_comment(text))
    return m.group(1) if m else None


def _matches_target_call(caller: dict, hit_text: str, target: dict) -> bool:
    if caller["line"] == target["line"] and Path(caller["file"]) == Path(target["file"]):
        return False
    if caller["line"] == target["line"] and caller["name"] == target["name"]:
        return False
    target_class = _class_name(target)
    receiver = _receiver_for_call(hit_text, target["name"])
    if receiver:
        return _symbol_types(caller).get(receiver) == target_class
    return _class_name(caller) == target_class


def _callers_of(unit: dict, root: Path, exclude: list[str]) -> list[dict]:
    pat = rf"\b{re.escape(unit['name'])}\s*\("
    hits = grep(pat, root, "*", exclude)
    callers: list[dict] = []
    seen: set[str] = set()
    for h in hits:
        if Path(h["file"]) == Path(unit["file"]) and h["line"] == unit["line"]:
            continue  # the definition itself, not a call
        enc = find_enclosing_unit(Path(h["file"]), h["line"])
        if enc and enc["id"] != unit["id"] and enc["id"] not in seen \
                and _matches_target_call(enc, h["text"], unit):
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
        types = _symbol_types(u)
        for name, receiver in _callee_refs_in_unit(u, profile):
            target_class = types.get(receiver) if receiver else _class_name(u)
            for tgt in _resolve_definition(name, root, exclude, target_class):
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

    def walk_calls(seeds_: list[str], neighbors: Callable[[str, str], list[str]],
                   depth_: int) -> list[tuple[str, str, str]]:
        depth_ = min(depth_, HARD_DEPTH_CAP)
        visited: set[str] = set()
        edges_: list[tuple[str, str, str]] = []
        frontier = [(s, 0) for s in seeds_]
        while frontier:
            node, d = frontier.pop(0)
            if node in visited or d >= depth_:
                continue
            visited.add(node)
            for nb in neighbors(node, "down"):
                if nb == node:
                    continue
                edges_.append((node, nb, "confirmed"))
                if nb not in visited:
                    frontier.append((nb, d + 1))
        return edges_

    seed_list = [u["id"] for u in seeds]
    down_edges = walk_calls(seed_list, neighbors_down, depth)
    up_edges = walk_calls(seed_list, neighbors_up, depth)

    for uid, u in known.items():
        add_node(g, {
            "id": uid, "kind": "unit", "label": uid,
            "layer": _layer_of_file(u["file"], layers),
            "file": u["file"], "line": u["line"], "end_line": u["end_line"],
            "usages": usage_by_unit.get(uid, []),
        })
    seen_edges: set[tuple[str, str, str]] = set()
    for frm, to, conf in down_edges:
        key = (frm, to, "call")
        if key not in seen_edges:
            seen_edges.add(key)
            add_edge(g, frm, to, "call", conf)
    # up_edges: walk emitted (unit -> caller); flip so edge is caller -> callee
    for frm, to, conf in up_edges:
        key = (to, frm, "call")
        if key not in seen_edges:
            seen_edges.add(key)
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
