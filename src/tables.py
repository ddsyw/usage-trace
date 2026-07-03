"""Phase 3: resolve DB tables touched along the call chain (MyBatis XML / JPA / raw SQL)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import add_edge, add_node, load_profile, load_graph, dump_graph

_OP_BY_TAG = {"select": "select", "insert": "insert", "update": "update", "delete": "delete"}
_TABLE_RE = re.compile(
    r"\b(?:from|join|into|update|table)\s+([A-Za-z_][\w.]*)", re.IGNORECASE)


def _parse_mybatis(root: Path, glob: str) -> list[dict]:
    """Return [{namespace, method, op, table, sql}] for each mapped statement."""
    out: list[dict] = []
    for xml in Path(root).glob(glob):
        try:
            text = xml.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        ns_m = re.search(r'namespace\s*=\s*"([^"]+)"', text)
        namespace = ns_m.group(1) if ns_m else ""
        for tag, op in _OP_BY_TAG.items():
            for blk in re.finditer(rf"<{tag}\s+[^>]*id\s*=\s*\"([^\"]+)\"[^>]*>(.*?)</{tag}>",
                                   text, re.DOTALL):
                method, sql = blk.group(1), blk.group(2)
                tm = _TABLE_RE.search(sql)
                table = tm.group(1).split(".")[-1] if tm else None
                out.append({"namespace": namespace, "method": method, "op": op,
                            "table": table, "sql": sql.strip()})
    return out


def _qualname_from_namespace(namespace: str, method: str) -> str:
    """com.example.mapper.OrderMapper + selectByStoreNo -> OrderMapper.selectByStoreNo"""
    cls = namespace.rsplit(".", 1)[-1] if namespace else ""
    return f"{cls}.{method}" if cls else method


def resolve_tables(graph: dict, root: Path, profile: dict) -> dict:
    ts = profile.get("table_sources", {})
    statements: list[dict] = []
    if "mybatis" in ts:
        glob = ts["mybatis"].get("mapper_xml_glob", "**/mapper/**/*.xml")
        statements += _parse_mybatis(root, glob)

    unit_by_id = {n["id"]: n for n in graph["nodes"] if n["kind"] == "unit"}
    existing_tables = {n.get("table") for n in graph["nodes"] if n["kind"] == "table"}

    for st in statements:
        if not st["table"]:
            continue
        qual = _qualname_from_namespace(st["namespace"], st["method"])
        if qual not in unit_by_id:
            continue  # only attach tables reached by the traced chain
        if st["table"] in existing_tables:
            tnode = next(n for n in graph["nodes"]
                         if n["kind"] == "table" and n["table"] == st["table"])
        else:
            add_node(graph, {
                "id": f"table:{st['table']}", "kind": "table", "label": st["table"],
                "layer": "Table", "table": st["table"], "op": st["op"],
                "source_unit": qual, "sql_snippet": st["sql"],
            })
            existing_tables.add(st["table"])
            tnode = next(n for n in graph["nodes"]
                         if n["kind"] == "table" and n["table"] == st["table"])
        add_edge(graph, qual, tnode["id"], "references", "confirmed")
    return graph


def main() -> None:
    ap = argparse.ArgumentParser(description="codex-find Phase 3: resolve DB tables.")
    ap.add_argument("--graph", required=True, help="path to graph JSON (from trace)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    graph = load_graph(Path(args.graph).read_text(encoding="utf-8"))
    resolve_tables(graph, Path(args.root), profile)
    sys.stdout.write(dump_graph(graph))


if __name__ == "__main__":
    main()
