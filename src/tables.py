"""Phase 3: resolve DB tables touched along the call chain (MyBatis XML / JPA / raw SQL)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import add_edge, add_node, load_profile, load_graph, dump_graph

_OP_BY_TAG = {"select": "select", "insert": "insert", "update": "update", "delete": "delete"}
_TABLE_RE = re.compile(
    r"\b(?:from|join|into|update|table)\s+([A-Za-z_][\w.]*)", re.IGNORECASE)
_SQL_OP_RE = re.compile(r"^\s*(select|insert|update|delete)\b", re.IGNORECASE)
_JAVA_KEYWORDS = {
    "class", "interface", "public", "private", "protected", "return", "new",
    "null", "true", "false", "void", "object", "string", "long", "int",
}
_GENERIC_TERMS = {
    "add", "by", "count", "create", "delete", "exists", "find", "get",
    "insert", "mapper", "modify", "patch", "query", "read", "remove",
    "repository", "save", "select", "service", "update",
}


def _tables_in_sql(sql: str) -> list[str]:
    seen: set[str] = set()
    tables: list[str] = []
    for m in _TABLE_RE.finditer(sql):
        table = m.group(1).split(".")[-1]
        if table not in seen:
            seen.add(table)
            tables.append(table)
    return tables


def _op_from_sql(sql: str) -> str:
    m = _SQL_OP_RE.search(sql)
    return m.group(1).lower() if m else "unknown"


def _op_from_method(method: str) -> str:
    lower = method.lower()
    if lower.startswith(("find", "get", "read", "query", "select", "count", "exists")):
        return "select"
    if lower.startswith(("save", "insert", "create", "add")):
        return "insert"
    if lower.startswith(("update", "modify", "patch")):
        return "update"
    if lower.startswith(("delete", "remove")):
        return "delete"
    return "unknown"


def _parse_mybatis(root: Path, glob: str) -> list[dict]:
    """Return statement dicts for each MyBatis XML mapped statement."""
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
                tables = _tables_in_sql(sql)
                out.append({"namespace": namespace, "method": method, "op": op,
                            "tables": tables, "sql": sql.strip()})
    return out


def _qualname_from_namespace(namespace: str, method: str) -> str:
    """com.example.mapper.OrderMapper + selectByStoreNo -> OrderMapper.selectByStoreNo"""
    cls = namespace.rsplit(".", 1)[-1] if namespace else ""
    return f"{cls}.{method}" if cls else method


def _class_name(text: str) -> str | None:
    m = re.search(r"\b(?:class|interface|enum)\s+(\w+)", text)
    return m.group(1) if m else None


def _parse_mybatis_annotations(root: Path) -> list[dict]:
    out: list[dict] = []
    annotation_rx = re.compile(
        r"@(?:[\w.]+\.)?(Select|Insert|Update|Delete)\s*\(\s*\"((?:\\.|[^\"])*)\""
    )
    method_rx = re.compile(r"\b([A-Za-z_]\w*)\s*\([^)]*\)\s*(?:;|\{)?")
    for java in Path(root).rglob("*.java"):
        try:
            lines = java.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        text = "\n".join(lines)
        cls = _class_name(text)
        if not cls:
            continue
        for i, line in enumerate(lines):
            m = annotation_rx.search(line)
            if not m:
                continue
            op = m.group(1).lower()
            sql = bytes(m.group(2), "utf-8").decode("unicode_escape")
            method = None
            for nxt in lines[i + 1:]:
                stripped = nxt.strip()
                if not stripped or stripped.startswith("@"):
                    continue
                mm = method_rx.search(stripped)
                if mm:
                    method = mm.group(1)
                break
            if method:
                out.append({"qual": f"{cls}.{method}", "op": op,
                            "tables": _tables_in_sql(sql), "sql": sql})
    return out


def _parse_jpa(root: Path) -> list[dict]:
    entities: dict[str, str] = {}
    repos: list[tuple[str, str, str]] = []
    method_rx = re.compile(r"\b([A-Za-z_]\w*)\s*\([^)]*\)\s*(?:;|\{)")
    for java in Path(root).rglob("*.java"):
        try:
            text = java.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        cls = _class_name(text)
        if not cls:
            continue
        if "@Entity" in text:
            table_m = re.search(r"@Table\s*\(\s*name\s*=\s*\"([^\"]+)\"", text)
            entities[cls] = table_m.group(1) if table_m else cls
        repo_m = re.search(r"\b(?:class|interface)\s+\w+\s+extends\s+[\w.]*Repository\s*<\s*(\w+)", text)
        if repo_m:
            repos.append((cls, repo_m.group(1), text))

    out: list[dict] = []
    for repo_cls, entity_cls, text in repos:
        table = entities.get(entity_cls)
        if not table:
            continue
        for m in method_rx.finditer(text):
            method = m.group(1)
            if method in {repo_cls, "JpaRepository", "CrudRepository"}:
                continue
            out.append({"qual": f"{repo_cls}.{method}", "op": _op_from_method(method),
                        "tables": [table], "sql": f"JPA {repo_cls}.{method} -> {entity_cls}"})
    return out


def _terms_from_text(text: str) -> set[str]:
    terms: set[str] = set()
    for term in re.findall(r"[A-Za-z_]\w*", text):
        pieces = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", term)
        for piece in pieces or [term]:
            lower = piece.lower()
            if len(lower) > 2 and lower not in _JAVA_KEYWORDS and lower not in _GENERIC_TERMS:
                terms.add(lower)
        lower_term = term.lower()
        if len(lower_term) > 2 and lower_term not in _JAVA_KEYWORDS and lower_term not in _GENERIC_TERMS:
            terms.add(lower_term)
    return terms


def _method_part(unit: dict) -> str:
    ident = unit.get("id") or unit.get("label") or ""
    return ident.rsplit(".", 1)[-1]


def _unit_terms(unit: dict) -> set[str]:
    terms: set[str] = set()
    terms.update(_terms_from_text(_method_part(unit)))
    for usage in unit.get("usages", []):
        terms.update(_terms_from_text(usage.get("snippet", "")))
    return terms


def _parse_raw_sql(root: Path, globs: list[str], unit_by_id: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    units_with_terms = [(uid, _unit_terms(unit)) for uid, unit in unit_by_id.items()]
    for glob in globs:
        for sql_file in Path(root).glob(glob):
            try:
                sql = sql_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            tables = _tables_in_sql(sql)
            if not tables:
                continue
            lower_sql = sql.lower()
            for uid, terms in units_with_terms:
                if terms and any(term in lower_sql for term in terms):
                    out.append({"qual": uid, "op": _op_from_sql(sql), "tables": tables,
                                "sql": sql.strip()})

    return out


def resolve_tables(graph: dict, root: Path, profile: dict) -> dict:
    ts = profile.get("table_sources", {})
    statements: list[dict] = []
    unit_by_id = {n["id"]: n for n in graph["nodes"] if n["kind"] == "unit"}

    if "mybatis" in ts:
        glob = ts["mybatis"].get("mapper_xml_glob", "**/mapper/**/*.xml")
        statements += _parse_mybatis(root, glob)
        statements += _parse_mybatis_annotations(root)
    if "jpa" in ts:
        statements += _parse_jpa(root)
    if "raw_sql" in ts:
        statements += _parse_raw_sql(root, ts.get("raw_sql") or [], unit_by_id)

    table_by_name = {n.get("table"): n for n in graph["nodes"] if n["kind"] == "table"}

    for st in statements:
        if not st["tables"]:
            continue
        qual = st.get("qual") or _qualname_from_namespace(st.get("namespace", ""), st["method"])
        if qual not in unit_by_id:
            continue  # only attach tables reached by the traced chain
        for table in st["tables"]:
            if table in table_by_name:
                tnode = table_by_name[table]
            else:
                add_node(graph, {
                    "id": f"table:{table}", "kind": "table", "label": table,
                    "layer": "Table", "table": table, "op": st["op"],
                    "ops": [], "source_unit": qual, "source_units": [],
                    "sql_snippet": st["sql"], "sql_snippets": [],
                })
                tnode = next(n for n in graph["nodes"]
                             if n["kind"] == "table" and n["table"] == table)
                table_by_name[table] = tnode
            if st["op"] not in tnode.setdefault("ops", []):
                tnode["ops"].append(st["op"])
            if qual not in tnode.setdefault("source_units", []):
                tnode["source_units"].append(qual)
            if st["sql"] not in tnode.setdefault("sql_snippets", []):
                tnode["sql_snippets"].append(st["sql"])
            tnode["op"] = ",".join(tnode["ops"])
            tnode["source_unit"] = ",".join(tnode["source_units"])
            tnode["sql_snippet"] = "\n---\n".join(tnode["sql_snippets"])
            add_edge(graph, qual, tnode["id"], "references", "confirmed")["op"] = st["op"]
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
