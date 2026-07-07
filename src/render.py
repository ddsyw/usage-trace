"""Phase 5: render a single self-contained HTML report with embedded layered SVG."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

from common import load_graph

COL_W, ROW_H, NODE_W, NODE_H, PAD = 190, 56, 150, 34, 24


def _esc(s) -> str:
    return escape(str(s))


def render_svg(graph: dict) -> str:
    """Layered left→right SVG: nodes positioned by (col, row); bezier edges.

    No xmlns attribute: the SVG is inline in an HTML5 document, where the SVG
    namespace is applied automatically. Omitting it keeps the report free of any
    `http://` string (the report's offline invariant).
    """
    nodes = graph.get("nodes", [])
    if not nodes:
        return '<svg width="200" height="40"><text x="8" y="24">no nodes</text></svg>'
    ncol = max(n.get("col", 0) for n in nodes) + 1
    nrow = max(n.get("row", 0) for n in nodes) + 1
    width = max(320, ncol * COL_W + PAD)
    height = max(60, nrow * ROW_H + PAD)
    pos = {n["id"]: (PAD + n.get("col", 0) * COL_W, PAD + n.get("row", 0) * ROW_H)
           for n in nodes}
    parts = [f'<svg width="{width}" height="{height}">']
    for e in graph.get("edges", []):
        if e["from"] not in pos or e["to"] not in pos:
            continue
        x1, y1 = pos[e["from"]]
        x2, y2 = pos[e["to"]]
        dash = ' stroke-dasharray="4,3"' if e.get("confidence") == "inferred" else ""
        parts.append(
            f'<path d="M{x1 + NODE_W},{y1 + NODE_H / 2} '
            f'C{x1 + NODE_W + 30},{y1 + NODE_H / 2} '
            f'{x2 - 30},{y2 + NODE_H / 2} {x2},{y2 + NODE_H / 2}" '
            f'fill="none" stroke="#64748b" stroke-width="1.4"{dash}/>'
        )
    for n in nodes:
        x, y = pos[n["id"]]
        cls = "node-" + (n.get("layer") or "Unknown")
        parts.append(
            f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="5" class="{cls}"/>'
        )
        parts.append(
            f'<text x="{x + NODE_W / 2}" y="{y + NODE_H / 2 + 4}" '
            f'text-anchor="middle">{_esc(n["label"])}</text>'
        )
    parts.append("</svg>")
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
        cls = "node-" + (n.get("layer") or "Unknown")
        yt = y - 14
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="10" class="{cls}"/>')
        parts.append(f'<text x="{x:.0f}" y="{yt:.0f}" font-size="9" text-anchor="middle">'
                     f'{_esc(n["label"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _tables_html(graph: dict) -> str:
    rows = [n for n in graph["nodes"] if n.get("kind") == "table"]
    if not rows:
        return "<p>无涉及表</p>"
    body = "".join(
        f"<tr><td><code>{_esc(n['table'])}</code></td><td>{_esc(n.get('op', 'unknown'))}</td>"
        f"<td>{_esc(n.get('source_unit', ''))}</td>"
        f"<td><code>{_esc(n.get('sql_snippet', ''))[:160]}</code></td></tr>"
        for n in rows
    )
    return ("<table><tr><th>表</th><th>操作</th><th>访问单元</th><th>SQL 片段</th></tr>"
            f"{body}</table>")


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
    out = out.replace("{{USAGES_HTML}}", _usages_html(graph))
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
