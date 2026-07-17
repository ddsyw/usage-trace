"""Phase 2: build the call graph around matched usage sites, via ProjectIndex."""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

from common import add_edge, add_node, classify_layer, load_profile, new_graph

HARD_DEPTH_CAP = 8


def trace(usages: list[dict], index, profile: dict, depth: int = 4) -> dict:
    depth = min(depth, HARD_DEPTH_CAP)
    layers = profile.get("layers", [])
    g = new_graph({"depth": depth})

    seeds: list = []
    seed_ids: set[str] = set()
    usage_by_unit: dict[str, list[dict]] = {}
    for site in usages:
        m = index.enclosing_method(site["file"], site["line"])
        if not m:
            continue
        if m.qual not in seed_ids:
            seed_ids.add(m.qual)
            seeds.append(m)
            usage_by_unit[m.qual] = []
        usage_by_unit[m.qual].append({
            "file": site["file"], "line": site["line"], "col": site.get("col"),
            "occurrence_type": site.get("occurrence_type"), "snippet": site.get("snippet"),
        })

    known = {m.qual: m for m in seeds}
    seed_quals = [m.qual for m in seeds]

    def expand(neighbor_fn) -> list[tuple[str, str, str]]:
        visited: set[str] = set()
        edges: list[tuple[str, str, str]] = []
        frontier: deque = deque((q, 0) for q in seed_quals)
        while frontier:
            uid, d = frontier.popleft()
            if uid in visited or d >= depth:
                continue
            visited.add(uid)
            for nb in neighbor_fn(uid, known, index):
                if nb == uid:
                    continue
                edges.append((uid, nb, "confirmed"))
                if nb not in visited:
                    frontier.append((nb, d + 1))
        return edges

    down_edges = expand(_neighbors_down)
    up_edges = expand(_neighbors_up)

    for uid, m in known.items():
        add_node(g, {
            "id": uid, "kind": "unit", "label": uid,
            "layer": index.layers.get(m.file) or _layer_fallback(m.file, layers),
            "file": m.file, "line": m.start_line, "end_line": m.end_line,
            "usages": usage_by_unit.get(uid, []),
        })

    seen: set[tuple[str, str, str]] = set()
    for frm, to, conf in down_edges:
        key = (frm, to, "call")
        if key not in seen:
            seen.add(key)
            add_edge(g, frm, to, "call", conf)
    # up_edges are (unit -> caller); emit caller -> unit
    for frm, to, conf in up_edges:
        key = (to, frm, "call")
        if key not in seen:
            seen.add(key)
            add_edge(g, to, frm, "call", conf)
    return g


def _neighbors_down(uid: str, known: dict, index) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for call in index.calls_by_caller.get(uid, []):
        for tgt in index.resolve_callee_targets(uid, call.callee_name, call.receiver):
            if tgt == uid or tgt in seen:
                continue
            seen.add(tgt)
            if tgt not in known:
                known[tgt] = index.methods[tgt]
            out.append(tgt)
    return out


def _neighbors_up(uid: str, known: dict, index) -> list[str]:
    method = index.methods.get(uid)
    if not method:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for call in index.calls_by_callee.get(method.name, []):
        targets = index.resolve_callee_targets(call.caller_qual, method.name, call.receiver)
        if uid in targets and call.caller_qual != uid and call.caller_qual not in seen:
            seen.add(call.caller_qual)
            if call.caller_qual not in known:
                known[call.caller_qual] = index.methods[call.caller_qual]
            out.append(call.caller_qual)
    return out


def _layer_fallback(file: str, layers: list[dict]) -> str:
    try:
        text = Path(file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    return classify_layer(file, layers, text)


def main() -> None:
    ap = argparse.ArgumentParser(description="usage-trace Phase 2: build call graph.")
    ap.add_argument("--usages", required=True, help="path to usages JSON (from discover)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--depth", type=int, default=4)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    from index import ProjectIndex
    index = ProjectIndex.load_or_build(Path(args.root), profile)
    usages = json.loads(Path(args.usages).read_text(encoding="utf-8"))
    g = trace(usages, index, profile, args.depth)
    json.dump(g, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
