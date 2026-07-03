"""Phase 4: enforce caps and compute layered layout."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import defaultdict, deque

from common import dump_graph, load_graph

DEFAULT_LAYER_ORDER = ["Controller", "Service", "Repository", "Table", "Unknown"]


def _truncate(graph: dict, max_nodes: int) -> None:
    """Keep the first `max_nodes` reachable from usage-bearing units; drop the rest."""
    if len(graph["nodes"]) <= max_nodes:
        return
    keep_ids: set[str] = set()
    seeds = [n["id"] for n in graph["nodes"]
             if n.get("kind") == "unit" and n.get("usages")]
    if not seeds:
        seeds = [graph["nodes"][0]["id"]] if graph["nodes"] else []
    adj: dict[str, list[str]] = defaultdict(list)
    for e in graph["edges"]:
        adj[e["from"]].append(e["to"])
    q = deque(seeds)
    while q and len(keep_ids) < max_nodes:
        nid = q.popleft()
        if nid in keep_ids:
            continue
        keep_ids.add(nid)
        for nb in adj.get(nid, []):
            if nb not in keep_ids:
                q.append(nb)
    if len(keep_ids) < max_nodes:
        for n in graph["nodes"]:
            if len(keep_ids) >= max_nodes:
                break
            keep_ids.add(n["id"])
    pruned = len(graph["nodes"]) - len(keep_ids)
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] in keep_ids]
    graph["edges"] = [e for e in graph["edges"]
                      if e["from"] in keep_ids and e["to"] in keep_ids]
    graph["meta"]["truncated"] = {"pruned_count": pruned, "reason": f"max_nodes={max_nodes}"}


def _layout(graph: dict, layer_order: list[str]) -> None:
    col_of = {name: i for i, name in enumerate(layer_order)}
    buckets: dict[int, list[dict]] = defaultdict(list)
    for n in graph["nodes"]:
        col = col_of.get(n.get("layer", "Unknown"), col_of.get("Unknown", 0))
        n["col"] = col
        buckets[col].append(n)
    for nodes in buckets.values():
        for row, n in enumerate(nodes):
            n["row"] = row


def prune_and_layout(graph: dict, max_nodes: int = 300,
                     layer_order: list[str] | None = None) -> dict:
    layer_order = layer_order or DEFAULT_LAYER_ORDER
    _truncate(graph, max_nodes)
    _layout(graph, layer_order)
    graph["meta"]["counts"] = {
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "tables": sum(1 for n in graph["nodes"] if n.get("kind") == "table"),
        "usages": sum(len(n.get("usages", [])) for n in graph["nodes"]
                      if n.get("kind") == "unit"),
    }
    return graph


def main() -> None:
    ap = argparse.ArgumentParser(description="codex-find Phase 4: prune + layout.")
    ap.add_argument("--graph", required=True)
    ap.add_argument("--max-nodes", type=int, default=300)
    args = ap.parse_args()
    graph = load_graph(Path(args.graph).read_text(encoding="utf-8"))
    prune_and_layout(graph, args.max_nodes)
    sys.stdout.write(dump_graph(graph))


if __name__ == "__main__":
    main()
