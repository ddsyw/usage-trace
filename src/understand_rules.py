"""Understand-Anything-inspired graph normalization and teaching metadata."""
from __future__ import annotations

import re
from collections import defaultdict, deque


EDGE_TYPE_BY_KIND = {
    "call": "calls",
    "references": "reads_from",
}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _edge_key(src: str, dst: str) -> str:
    return f"{src}\u001f{dst}"


def _node_type(node: dict) -> str:
    if node.get("kind") == "table":
        return "table"
    if node.get("kind") == "unit":
        return "function"
    return "concept"


def _edge_type(edge: dict) -> str:
    return EDGE_TYPE_BY_KIND.get(edge.get("kind", ""), edge.get("kind") or "related")


def _edge_weight(edge: dict) -> float:
    if edge.get("confidence") == "inferred":
        return 0.55
    if edge.get("kind") == "references":
        return 0.9
    return 1.0


def _complexity(node: dict, degree: int) -> str:
    usage_count = len(node.get("usages", []))
    sql_len = len(node.get("sql_snippet") or "")
    score = degree + usage_count + (1 if sql_len > 160 else 0)
    if score <= 1:
        return "simple"
    if score <= 4:
        return "moderate"
    return "complex"


def _tags(node: dict) -> list[str]:
    tags = {_slug(node.get("layer") or "unknown"), _slug(node.get("kind") or "node")}
    if node.get("table"):
        tags.add("table")
    if node.get("op"):
        tags.add(_slug(node["op"]))
    return sorted(tags)


def _summary(node: dict) -> str:
    label = node.get("label") or node.get("id") or "node"
    if node.get("kind") == "table":
        op = node.get("op") or "unknown"
        source = node.get("source_unit") or "traced call chain"
        return f"Database table {label} is accessed via {source} ({op})."
    layer = node.get("layer") or "Unknown"
    return f"{label} participates in the traced keyword flow at the {layer} layer."


def _normalize_edges(graph: dict) -> dict[str, int]:
    node_ids = {node["id"] for node in graph.get("nodes", [])}
    merged: dict[tuple[str, str, str], dict] = {}
    dropped = 0
    deduped = 0
    for edge in graph.get("edges", []):
        src, dst = edge.get("from"), edge.get("to")
        if src not in node_ids or dst not in node_ids or src == dst:
            dropped += 1
            continue
        kind = edge.get("kind", "related")
        key = (src, dst, kind)
        normalized = {
            **edge,
            "type": _edge_type(edge),
            "direction": "forward",
            "weight": _edge_weight(edge),
        }
        existing = merged.get(key)
        if existing is None:
            merged[key] = normalized
            continue
        deduped += 1
        if normalized["weight"] > existing["weight"]:
            merged[key] = normalized
    graph["edges"] = list(merged.values())
    return {"dropped_edges": dropped, "deduped_edges": deduped}


def _degrees(graph: dict) -> dict[str, int]:
    degree: dict[str, int] = defaultdict(int)
    for edge in graph.get("edges", []):
        degree[edge["from"]] += 1
        degree[edge["to"]] += 1
    return degree


def _enrich_nodes(graph: dict) -> None:
    degree = _degrees(graph)
    for node in graph.get("nodes", []):
        node["type"] = _node_type(node)
        node["name"] = node.get("label") or node.get("id", "")
        node["summary"] = node.get("summary") or _summary(node)
        node["tags"] = node.get("tags") or _tags(node)
        node["complexity"] = node.get("complexity") or _complexity(node, degree.get(node["id"], 0))


def _layer_id(layer: str) -> str:
    return f"layer:{_slug(layer)}"


def _build_layers(graph: dict, layer_order: list[str]) -> list[dict]:
    order = list(dict.fromkeys(layer_order + [
        node.get("layer", "Unknown") for node in graph.get("nodes", [])
    ]))
    layers = []
    for layer in order:
        node_ids = [
            node["id"] for node in graph.get("nodes", [])
            if (node.get("layer") or "Unknown") == layer
        ]
        if not node_ids:
            continue
        layers.append({
            "id": _layer_id(layer),
            "name": layer,
            "description": f"{layer} nodes involved in the traced keyword flow.",
            "nodeIds": node_ids,
        })
    return layers


def _aggregate_layer_edges(graph: dict) -> list[dict]:
    node_to_layer: dict[str, str] = {}
    for layer in graph.get("layers", []):
        for node_id in layer.get("nodeIds", []):
            node_to_layer[node_id] = layer["id"]
    pairs: dict[tuple[str, str], dict] = {}
    for edge in graph.get("edges", []):
        src_layer = node_to_layer.get(edge["from"])
        dst_layer = node_to_layer.get(edge["to"])
        if not src_layer or not dst_layer or src_layer == dst_layer:
            continue
        key = (src_layer, dst_layer)
        entry = pairs.setdefault(key, {
            "sourceLayerId": src_layer,
            "targetLayerId": dst_layer,
            "count": 0,
            "edgeTypes": set(),
        })
        entry["count"] += 1
        entry["edgeTypes"].add(edge.get("type") or _edge_type(edge))
    return [
        {**entry, "edgeTypes": sorted(entry["edgeTypes"])}
        for entry in pairs.values()
    ]


def _shortest_path(adj: dict[str, list[str]], start: str, targets: set[str]) -> list[str]:
    q = deque([(start, [start])])
    seen = {start}
    while q:
        node, path = q.popleft()
        if node in targets and node != start:
            return path
        if len(path) > 12:
            continue
        for nxt in adj.get(node, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            q.append((nxt, path + [nxt]))
    return []


def _is_subpath(path: list[str], existing_paths: list[dict]) -> bool:
    for existing in existing_paths:
        ids = existing["nodes"]
        if len(path) >= len(ids):
            continue
        for i in range(0, len(ids) - len(path) + 1):
            if ids[i:i + len(path)] == path:
                return True
    return False


def _main_paths(graph: dict) -> list[dict]:
    nodes = graph.get("nodes", [])
    node_by_id = {node["id"]: node for node in nodes}
    table_ids = {node["id"] for node in nodes if node.get("kind") == "table"}
    if not table_ids:
        return []
    adj: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    for edge in graph.get("edges", []):
        adj[edge["from"]].append(edge["to"])
        incoming[edge["to"]] += 1
    unit_ids = [node["id"] for node in nodes if node.get("kind") == "unit"]
    controller_ids = [node["id"] for node in nodes if node.get("layer") == "Controller"]
    root_ids = [node_id for node_id in unit_ids if incoming.get(node_id, 0) == 0]
    usage_ids = [node["id"] for node in nodes if node.get("kind") == "unit" and node.get("usages")]
    starts = list(dict.fromkeys(controller_ids + root_ids + usage_ids + unit_ids))
    paths: list[dict] = []
    seen: set[tuple[str, ...]] = set()
    for start in starts:
        path = _shortest_path(adj, start, table_ids)
        path_key = tuple(path)
        if not path or path_key in seen or _is_subpath(path, paths):
            continue
        seen.add(path_key)
        paths.append({
            "nodes": path,
            "labels": [node_by_id[node_id].get("label", node_id) for node_id in path],
            "layers": [node_by_id[node_id].get("layer", "") for node_id in path],
            "table": node_by_id[path[-1]].get("table", node_by_id[path[-1]].get("label", "")),
        })
        if len(paths) >= 4:
            break
    return paths


def _build_tour(graph: dict) -> list[dict]:
    steps = []
    for path in graph.get("main_paths", [])[:1]:
        steps.append({
            "order": len(steps) + 1,
            "title": "主路径",
            "description": "从入口方法沿调用链到数据库表的核心阅读路径。",
            "nodeIds": path["nodes"],
        })
    for layer in graph.get("layers", []):
        steps.append({
            "order": len(steps) + 1,
            "title": layer["name"],
            "description": layer["description"],
            "nodeIds": layer["nodeIds"],
        })
    return steps[:15]


def apply_understand_rules(graph: dict, layer_order: list[str]) -> dict:
    """Add graph metadata modeled after Understand-Anything's knowledge graph rules."""
    stats = _normalize_edges(graph)
    _enrich_nodes(graph)
    graph["layers"] = _build_layers(graph, layer_order)
    graph["layer_edges"] = _aggregate_layer_edges(graph)
    graph["main_paths"] = _main_paths(graph)
    graph["tour"] = _build_tour(graph)
    graph.setdefault("meta", {})["understand_rules"] = {
        **stats,
        "layers": len(graph["layers"]),
        "tour_steps": len(graph["tour"]),
        "layer_edges": len(graph["layer_edges"]),
    }
    return graph
