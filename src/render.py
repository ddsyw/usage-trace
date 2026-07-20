"""Phase 5: render a single self-contained HTML report with an interactive graph."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

from common import load_graph

COL_W, ROW_H, NODE_W, NODE_H, PAD = 230, 72, 178, 44, 34

LAYER_CLASSES = {
    "Controller": "node-controller",
    "Service": "node-service",
    "Repository": "node-repository",
    "Entity": "node-entity",
    "SQL": "node-sql",
    "Table": "node-table",
    "Unknown": "node-unknown",
}

SOURCE_LABELS = {
    "mybatis_xml": "MyBatis XML",
    "mybatis_annotation": "MyBatis 注解",
    "jpa_repository": "JPA Repository",
    "raw_sql": "SQL 文件",
    "java_sql_literal": "Java SQL 字符串",
}


def _esc(s) -> str:
    return escape(str(s))


def _attr(s) -> str:
    return escape(str(s), {'"': "&quot;"})


def _layer_class(layer: str | None) -> str:
    return LAYER_CLASSES.get(layer or "Unknown", "node-unknown")


def _source_label(source: str | None) -> str:
    return SOURCE_LABELS.get(source or "", source or "unknown")


def _code_lines(values: list[str] | tuple[str, ...]) -> str:
    return "<br>".join(f"<code>{_esc(value)}</code>" for value in values if value)


def _node_positions(graph: dict) -> dict[str, tuple[int, int]]:
    return {
        n["id"]: (PAD + int(n.get("col", 0)) * COL_W, PAD + int(n.get("row", 0)) * ROW_H)
        for n in graph.get("nodes", [])
    }


def _display_lines(label: str, max_chars: int = 24) -> list[str]:
    label = str(label)
    if len(label) <= max_chars:
        return [label]
    head = label[:max_chars]
    tail = label[max_chars:max_chars * 2 - 1]
    if len(label) > max_chars * 2 - 1:
        tail = tail[:max_chars - 2] + "..."
    return [head, tail]


def _node_label_lines(node: dict) -> list[str]:
    label = str(node.get("label", node["id"]))
    if node.get("kind") != "table":
        return _display_lines(label)
    lines = _display_lines(label, 22)[:1]
    op = node.get("op") or ",".join(node.get("ops") or [])
    if op:
        lines.append(str(op)[:24])
    return lines


def _edge_key(src: str, dst: str) -> str:
    return f"{src}\u001f{dst}"


def _main_path_sets(graph: dict) -> tuple[set[str], set[str]]:
    main_nodes: set[str] = set()
    main_edges: set[str] = set()
    for path in graph.get("main_paths", []):
        ids = path["nodes"]
        main_nodes.update(ids)
        for src, dst in zip(ids, ids[1:]):
            main_edges.add(_edge_key(src, dst))
    return main_nodes, main_edges


def _group_frames_svg(graph: dict, pos: dict[str, tuple[int, int]]) -> str:
    nodes = graph.get("nodes", [])
    counts = _layer_counts(graph)
    parts: list[str] = []
    for layer in _ordered_layers(graph, counts):
        group_nodes = [n for n in nodes if (n.get("layer") or "Unknown") == layer and n["id"] in pos]
        if not group_nodes:
            continue
        xs = [pos[n["id"]][0] for n in group_nodes]
        ys = [pos[n["id"]][1] for n in group_nodes]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        frame_x = max(4, min_x - 18)
        frame_y = max(4, min_y - 30)
        frame_w = max_x - min_x + NODE_W + 36
        frame_h = max_y - min_y + NODE_H + 44
        label = f"{layer} · {len(group_nodes)}"
        parts.append(
            f'<g class="graph-group {_layer_class(layer)}" data-layer="{_attr(layer)}">'
            f'<rect class="group-frame" x="{frame_x}" y="{frame_y}" '
            f'width="{frame_w}" height="{frame_h}" rx="10"/>'
            f'<text class="group-label" x="{frame_x + 10}" y="{frame_y + 18}">{_esc(label)}</text>'
            "</g>"
        )
    return "".join(parts)


def render_svg(graph: dict) -> str:
    """Layered left-to-right SVG with click targets for the report dashboard."""
    nodes = graph.get("nodes", [])
    if not nodes:
        return '<svg id="trace-graph" viewBox="0 0 420 120"><text x="20" y="64">no nodes</text></svg>'
    ncol = max(n.get("col", 0) for n in nodes) + 1
    nrow = max(n.get("row", 0) for n in nodes) + 1
    width = max(320, ncol * COL_W + PAD)
    height = max(60, nrow * ROW_H + PAD)
    pos = _node_positions(graph)
    main_nodes, main_edges = _main_path_sets(graph)
    parts = [
        f'<svg id="trace-graph" class="trace-graph" data-width="{width}" data-height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="usage trace graph">',
        '<g id="graph-viewport">',
    ]
    parts.append(_group_frames_svg(graph, pos))
    for e in graph.get("edges", []):
        if e["from"] not in pos or e["to"] not in pos:
            continue
        x1, y1 = pos[e["from"]]
        x2, y2 = pos[e["to"]]
        confidence = e.get("confidence", "direct")
        dash = ' stroke-dasharray="5,4"' if confidence == "inferred" else ""
        main_cls = " main-path" if _edge_key(e["from"], e["to"]) in main_edges else ""
        parts.append(
            f'<path d="M{x1 + NODE_W},{y1 + NODE_H / 2} '
            f'C{x1 + NODE_W + 30},{y1 + NODE_H / 2} '
            f'{x2 - 30},{y2 + NODE_H / 2} {x2},{y2 + NODE_H / 2}" '
            f'class="graph-edge{main_cls}" data-from="{_attr(e["from"])}" data-to="{_attr(e["to"])}" '
            f'data-confidence="{_attr(confidence)}" fill="none"{dash}/>'
        )
    for n in nodes:
        x, y = pos[n["id"]]
        label = str(n.get("label", n["id"]))
        cls = _layer_class(n.get("layer"))
        main_cls = " main-path" if n["id"] in main_nodes else ""
        parts.append(
            f'<g class="graph-node {cls}{main_cls}" tabindex="0" role="button" '
            f'data-node-id="{_attr(n["id"])}" data-label="{_attr(label)}" '
            f'transform="translate({x},{y})">'
        )
        parts.append(f'<title>{_esc(label)}</title>')
        parts.append(f'<rect width="{NODE_W}" height="{NODE_H}" rx="7"/>')
        lines = _node_label_lines(n)
        start_y = 20 if len(lines) == 1 else 16
        parts.append(f'<text x="{NODE_W / 2}" y="{start_y}" text-anchor="middle">')
        for i, line in enumerate(lines):
            dy = 0 if i == 0 else 14
            parts.append(f'<tspan x="{NODE_W / 2}" dy="{dy}">{_esc(line)}</tspan>')
        parts.append("</text></g>")
    parts.append("</g></svg>")
    return "".join(parts)


def render_panorama_svg(graph: dict) -> str:
    """Collapsed secondary view: radial layout (rings by layer col)."""
    nodes = graph.get("nodes", [])
    if not nodes:
        return '<svg width="200" height="40"><text x="8" y="24">no nodes</text></svg>'
    size = 420
    cx = cy = size / 2
    by_col: dict[int, list[dict]] = defaultdict(list)
    for n in nodes:
        by_col[n.get("col", 0)].append(n)
    pos: dict[str, tuple[float, float]] = {}
    for col, group in by_col.items():
        r = 60 + col * 70
        for i, n in enumerate(group):
            ang = 2 * math.pi * i / max(len(group), 1)
            pos[n["id"]] = (cx + r * math.cos(ang), cy + r * math.sin(ang))
    parts = [f'<svg width="{size}" height="{size}">']
    for e in graph.get("edges", []):
        if e["from"] in pos and e["to"] in pos:
            x1, y1 = pos[e["from"]]
            x2, y2 = pos[e["to"]]
            parts.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                         f'stroke="#94a3b8" stroke-width="1"/>')
    for n in nodes:
        x, y = pos[n["id"]]
        cls = _layer_class(n.get("layer"))
        yt = y - 14
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="10" class="{cls}"/>')
        parts.append(f'<text x="{x:.0f}" y="{yt:.0f}" font-size="9" text-anchor="middle">'
                     f'{_esc(n["label"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _tables_html(graph: dict) -> str:
    rows = [n for n in graph["nodes"] if n.get("kind") == "table"]
    candidates: dict[tuple[str, str, str], dict] = {}
    linked_tables = {n.get("table") for n in rows}
    for st in graph.get("db_statements") or []:
        if st.get("linked"):
            continue
        for table in st.get("tables") or []:
            if table in linked_tables:
                continue
            key = (table, st.get("op", "unknown"), st.get("file", ""))
            candidates[key] = {
                "table": table,
                "op": st.get("op", "unknown"),
                "source_unit": st.get("qual") or st.get("statement_id") or "",
                "source_files": [st.get("file", "")] if st.get("file") else [],
                "sql_snippet": st.get("sql", ""),
                "status": "候选表（未连接）",
            }
    if not rows:
        rows = list(candidates.values())
        if not rows:
            return "<p>无涉及表</p>"
    else:
        rows = [*rows, *candidates.values()]
    body = "".join(
        f"<tr><td><code>{_esc(n['table'])}</code></td>"
        f"<td>{_esc(n.get('op', 'unknown'))}</td>"
        f"<td>{_esc(n.get('status', '已连接'))}</td>"
        f"<td>{_esc(n.get('source_unit', ''))}</td>"
        f"<td>{_code_lines(n.get('source_files') or [])}</td>"
        f"<td><code>{_esc(n.get('sql_snippet', ''))[:160]}</code></td></tr>"
        for n in rows
    )
    return ("<table><tr><th>表</th><th>操作</th><th>状态</th><th>访问单元</th>"
            "<th>来源文件</th><th>SQL 片段</th></tr>"
            f"{body}</table>")


def _db_sources_html(graph: dict) -> str:
    statements = graph.get("db_statements") or []
    if not statements:
        return "<p>无 XML / SQL 来源</p>"
    body = "".join(
        "<tr>"
        f"<td>{_esc(_source_label(st.get('source')))}</td>"
        f"<td><code>{_esc(st.get('file', ''))}</code></td>"
        f"<td><code>{_esc(st.get('statement_id') or st.get('qual') or '')}</code></td>"
        f"<td>{_esc(st.get('op', 'unknown'))}</td>"
        f"<td>{_code_lines(st.get('tables') or [])}</td>"
        f"<td>{_esc('已连接' if st.get('linked') else st.get('skip_reason', '未连接'))}</td>"
        f"<td><code>{_esc(st.get('sql', ''))[:180]}</code></td>"
        "</tr>"
        for st in statements
    )
    return (
        "<table><tr><th>来源</th><th>文件</th><th>Statement</th><th>操作</th>"
        "<th>表</th><th>状态</th><th>SQL</th></tr>"
        f"{body}</table>"
    )


def _usages_html(graph: dict) -> str:
    rows = []
    for n in graph["nodes"]:
        if n.get("kind") != "unit":
            continue
        for u in n.get("usages", []):
            rows.append(
                f"<tr><td>{_esc(Path(u['file']).name)}:{u['line']}</td>"
                f"<td>{_esc(n['layer'])}</td><td>{_esc(u.get('occurrence_type', ''))}</td>"
                f"<td><code>{_esc(u.get('snippet', ''))[:160]}</code></td></tr>"
            )
    if not rows:
        return "<p>无使用位置</p>"
    return ("<table><tr><th>位置</th><th>层</th><th>类型</th><th>代码片段</th></tr>"
            + "".join(rows) + "</table>")


def _layer_summary_html(graph: dict) -> str:
    counts: dict[str, int] = {}
    for n in graph.get("nodes", []):
        layer = n.get("layer") or "Unknown"
        counts[layer] = counts.get(layer, 0) + 1
    if not counts:
        return '<p class="muted">无节点</p>'
    return "".join(
        f'<button type="button" class="layer-chip {_layer_class(layer)}" data-layer="{_attr(layer)}">'
        f'<span></span>{_esc(layer)} <b>{count}</b></button>'
        for layer, count in sorted(counts.items(), key=lambda item: item[0])
    )


def _layer_counts(graph: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in graph.get("nodes", []):
        layer = n.get("layer") or "Unknown"
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def _ordered_layers(graph: dict, counts: dict[str, int]) -> list[str]:
    ordered: list[str] = []
    for layer in graph.get("layers") or []:
        name = layer.get("name") or layer.get("id")
        if name in counts and name not in ordered:
            ordered.append(name)
    for name in LAYER_CLASSES:
        if name in counts and name not in ordered:
            ordered.append(name)
    ordered.extend(sorted(name for name in counts if name not in ordered))
    return ordered


def _layer_tabs_html(graph: dict) -> str:
    counts = _layer_counts(graph)
    total = sum(counts.values())
    tabs = [
        f'<button type="button" class="layer-tab active" data-layer="all" '
        f'aria-pressed="true"><span>全部</span><b>{total}</b></button>'
    ]
    for layer in _ordered_layers(graph, counts):
        tabs.append(
            f'<button type="button" class="layer-tab {_layer_class(layer)}" '
            f'data-layer="{_attr(layer)}" aria-pressed="false">'
            f'<span>{_esc(layer)}</span><b>{counts[layer]}</b></button>'
        )
    return "".join(tabs)


def _top_nodes_html(graph: dict) -> str:
    degree: dict[str, int] = {}
    labels = {n["id"]: n.get("label", n["id"]) for n in graph.get("nodes", [])}
    for e in graph.get("edges", []):
        degree[e["from"]] = degree.get(e["from"], 0) + 1
        degree[e["to"]] = degree.get(e["to"], 0) + 1
    rows = sorted(degree.items(), key=lambda item: item[1], reverse=True)[:6]
    if not rows:
        return '<p class="muted">无连接节点</p>'
    return "".join(
        f'<button type="button" class="node-jump" data-node-id="{_attr(node_id)}">'
        f'<span>{i}</span><strong>{_esc(labels.get(node_id, node_id))}</strong><em>{count}</em></button>'
        for i, (node_id, count) in enumerate(rows, 1)
    )


def _main_paths_html(graph: dict) -> str:
    paths = graph.get("main_paths", [])
    if not paths:
        return '<p class="muted">无通向表的主路径</p>'
    lanes = []
    for i, path in enumerate(paths, 1):
        steps = "".join(
            f'<span class="path-step"><em>{_esc(layer or "Unknown")}</em>'
            f'<strong>{_esc(label)}</strong></span>'
            for label, layer in zip(path["labels"], path["layers"])
        )
        lanes.append(
            f'<button type="button" class="path-lane" data-path-index="{i - 1}" '
            f'data-node-id="{_attr(path["nodes"][-1])}">'
            f'<span class="path-rank">{i}</span><span class="path-chain">{steps}</span></button>'
        )
    return "".join(lanes)


def _tour_html(graph: dict) -> str:
    steps = graph.get("tour") or []
    if not steps:
        return '<p class="muted">无导览</p>'
    return "".join(
        f'<button type="button" class="tour-step" data-node-id="{_attr((step.get("nodeIds") or [""])[0])}">'
        f'<span>{_esc(step.get("order", ""))}</span><strong>{_esc(step.get("title", ""))}</strong>'
        f'<em>{_esc(step.get("description", ""))}</em></button>'
        for step in steps[:8]
    )


def _layer_edges_html(graph: dict) -> str:
    layer_edges = graph.get("layer_edges") or []
    layer_names = {layer["id"]: layer.get("name", layer["id"]) for layer in graph.get("layers", [])}
    if not layer_edges:
        return '<p class="muted">无跨层关系</p>'
    return "".join(
        f'<div class="layer-edge"><strong>{_esc(layer_names.get(edge["sourceLayerId"], edge["sourceLayerId"]))}'
        f' → {_esc(layer_names.get(edge["targetLayerId"], edge["targetLayerId"]))}</strong>'
        f'<span>{edge["count"]} · {_esc(", ".join(edge.get("edgeTypes") or []))}</span></div>'
        for edge in layer_edges[:8]
    )


def _method_source(node: dict, max_chars: int = 2000) -> str:
    """Slice a unit node's method body text from its source file.

    Returns "" when file/line/end_line are missing or unreadable (e.g. table
    nodes, which lack these fields), so it is harmless to call on any node.
    """
    file = node.get("file")
    start = node.get("line")
    end = node.get("end_line")
    if not (file and start and end):
        return ""
    try:
        lines = Path(file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    body = "\n".join(lines[start - 1:end])
    if len(body) > max_chars:
        return body[:max_chars] + "…"
    return body


def _dashboard_graph_json(graph: dict) -> str:
    positions = _node_positions(graph)
    payload = {
        "meta": graph.get("meta", {}),
        "nodes": [
            {
                **node,
                "x": positions.get(node["id"], (0, 0))[0],
                "y": positions.get(node["id"], (0, 0))[1],
                "width": NODE_W,
                "height": NODE_H,
                "source": _method_source(node),
            }
            for node in graph.get("nodes", [])
        ],
        "edges": graph.get("edges", []),
        "db_statements": graph.get("db_statements", []),
        "layers": graph.get("layers", []),
        "layer_edges": graph.get("layer_edges", []),
        "main_paths": graph.get("main_paths", []),
        "tour": graph.get("tour", []),
    }
    return (
        json.dumps(payload, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def render(graph: dict, keyword: str, meta: dict, template_path: Path) -> str:
    tmpl = Path(template_path).read_text(encoding="utf-8")
    counts = graph.get("meta", {}).get("counts", {})
    trunc = graph.get("meta", {}).get("truncated")
    notes = "无截断。" if not trunc else f"⚠ 已截断 {trunc['pruned_count']} 个节点（{trunc['reason']}）。"
    inferred = sum(1 for e in graph.get("edges", []) if e.get("confidence") == "inferred")
    if inferred:
        notes += f" 图中含 {inferred} 条推断边（虚线）。"
    out = tmpl
    out = out.replace("{{KEYWORD}}", _esc(keyword))
    out = out.replace("{{PROJECT}}", _esc(meta.get("project", "")))
    out = out.replace("{{LANGUAGE}}", _esc(meta.get("language", "")))
    out = out.replace("{{GENERATED_AT}}", _esc(meta.get("generated_at", "")))
    out = out.replace("{{USAGES}}", str(counts.get("usages", 0)))
    out = out.replace("{{TABLES}}", str(counts.get("tables", 0)))
    out = out.replace("{{DEPTH}}", str(graph.get("meta", {}).get("depth", "")))
    out = out.replace("{{SVG}}", render_svg(graph))
    out = out.replace("{{PANORAMA_SVG}}", render_panorama_svg(graph))
    out = out.replace("{{TABLES_HTML}}", _tables_html(graph))
    out = out.replace("{{DB_SOURCES_HTML}}", _db_sources_html(graph))
    out = out.replace("{{USAGES_HTML}}", _usages_html(graph))
    out = out.replace("{{MAIN_PATHS_HTML}}", _main_paths_html(graph))
    out = out.replace("{{TOUR_HTML}}", _tour_html(graph))
    out = out.replace("{{LAYER_EDGES_HTML}}", _layer_edges_html(graph))
    out = out.replace("{{LAYERS_HTML}}", _layer_summary_html(graph))
    out = out.replace("{{LAYER_TABS_HTML}}", _layer_tabs_html(graph))
    out = out.replace("{{TOP_NODES_HTML}}", _top_nodes_html(graph))
    out = out.replace("{{GRAPH_DATA}}", _dashboard_graph_json(graph))
    out = out.replace("{{NOTES}}", notes)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="usage-trace Phase 5: render report.")
    ap.add_argument("--graph", required=True)
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--meta", required=True, help="path to meta JSON")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    graph = load_graph(Path(args.graph).read_text(encoding="utf-8"))
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    tmpl = Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"
    Path(args.out).write_text(render(graph, args.keyword, meta, tmpl), encoding="utf-8")


if __name__ == "__main__":
    main()
