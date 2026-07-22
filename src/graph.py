"""Phase 4: enforce caps and compute layered layout."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from collections import defaultdict, deque

from common import dump_graph, load_graph
from understand_rules import apply_understand_rules

DEFAULT_LAYER_ORDER = ["Controller", "Service", "Repository", "Table", "Other"]


def _critical_node_ids(graph: dict) -> list[str]:
    ids = {n["id"] for n in graph["nodes"] if n.get("kind") == "table"}
    for edge in graph["edges"]:
        if edge.get("kind") == "references":
            ids.add(edge["from"])
            ids.add(edge["to"])
    ordered: list[str] = []
    seen: set[str] = set()
    for node in graph["nodes"]:
        nid = node["id"]
        if nid in ids and nid not in seen:
            seen.add(nid)
            ordered.append(nid)
    return ordered


def _truncate(graph: dict, max_nodes: int) -> None:
    """Keep the first `max_nodes` reachable from usage-bearing units; drop the rest."""
    if len(graph["nodes"]) <= max_nodes:
        return
    keep_ids: set[str] = set()
    for nid in _critical_node_ids(graph):
        if len(keep_ids) >= max_nodes:
            break
        keep_ids.add(nid)
    seeds = [n["id"] for n in graph["nodes"]
             if n.get("kind") == "unit" and n.get("usages")]
    if not seeds:
        seeds = [graph["nodes"][0]["id"]] if graph["nodes"] else []
    adj: dict[str, list[str]] = defaultdict(list)
    for e in graph["edges"]:
        adj[e["from"]].append(e["to"])
    q = deque(seeds)
    expanded: set[str] = set()
    while q and len(keep_ids) < max_nodes:
        nid = q.popleft()
        if nid in expanded:
            continue
        expanded.add(nid)
        if nid not in keep_ids:
            keep_ids.add(nid)
        for nb in adj.get(nid, []):
            if nb not in expanded:
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


def _class_of_node(node: dict) -> str:
    """Group key: class/table name so methods of one class sit together."""
    if node.get("kind") == "table":
        return str(node.get("table") or node.get("label") or node["id"])
    label = str(node.get("label") or node.get("id") or "")
    if "." in label:
        return label.rsplit(".", 1)[0]
    nid = str(node.get("id") or "")
    if nid.startswith("table:"):
        return nid.split(":", 1)[1]
    if "." in nid:
        return nid.rsplit(".", 1)[0]
    return label or nid or "unknown"


def _layout(graph: dict, layer_order: list[str]) -> None:
    """Left-to-right by layer; within a layer, group by class then method name.

    Controllers A/B/C form sub-regions: all AController methods consecutive,
    then BController, then CController (same for Service/Repository/...).
    """
    col_of = {name: i for i, name in enumerate(layer_order)}
    buckets: dict[int, list[dict]] = defaultdict(list)
    for n in graph["nodes"]:
        layer = n.get("layer") or "Other"
        col = col_of.get(layer, col_of.get("Other", col_of.get("Unknown", 0)))
        n["col"] = col
        n["group"] = _class_of_node(n)
        buckets[col].append(n)

    class_groups: list[dict] = []
    for col in sorted(buckets):
        nodes = buckets[col]
        # stable order: class name, then method/label
        nodes.sort(key=lambda n: (
            str(n.get("group") or ""),
            str(n.get("label") or n.get("id") or ""),
        ))
        # Row 0 reserved visually (via render top pad) for layer+class titles.
        # Between classes leave 2 rows so the next class title never collides
        # with the previous method node.
        row = 0
        prev_group = None
        group_start = 0
        layer_name = nodes[0].get("layer") or "Other"
        group_layer = layer_name
        for n in nodes:
            gname = n.get("group")
            if prev_group is not None and gname != prev_group:
                class_groups.append({
                    "layer": group_layer,
                    "col": col,
                    "group": prev_group,
                    "row_start": group_start,
                    "row_end": row - 1,
                })
                row += 2  # gap + room for next class title
                group_start = row
            if prev_group is None:
                group_start = row
            n["row"] = row
            prev_group = gname
            group_layer = n.get("layer") or "Other"
            row += 1
        if prev_group is not None and nodes:
            class_groups.append({
                "layer": group_layer,
                "col": col,
                "group": prev_group,
                "row_start": group_start,
                "row_end": row - 1,
            })
    graph["class_groups"] = class_groups


def prune_and_layout(graph: dict, max_nodes: int = 300,
                     layer_order: list[str] | None = None) -> dict:
    layer_order = layer_order or DEFAULT_LAYER_ORDER
    _truncate(graph, max_nodes)
    _layout(graph, layer_order)
    apply_understand_rules(graph, layer_order)
    graph["meta"]["counts"] = {
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
        "tables": sum(1 for n in graph["nodes"] if n.get("kind") == "table"),
        "usages": sum(len(n.get("usages", [])) for n in graph["nodes"]
                      if n.get("kind") == "unit"),
    }
    return graph


def main() -> None:
    ap = argparse.ArgumentParser(description="usage-trace Phase 4: prune + layout.")
    ap.add_argument("--graph", required=True)
    ap.add_argument("--max-nodes", type=int, default=300)
    args = ap.parse_args()
    graph = load_graph(Path(args.graph).read_text(encoding="utf-8"))
    prune_and_layout(graph, args.max_nodes)
    sys.stdout.write(dump_graph(graph))


if __name__ == "__main__":
    main()
