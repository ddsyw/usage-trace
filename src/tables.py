"""Phase 3: resolve DB tables touched along the call chain (MyBatis XML / JPA / raw SQL)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import add_edge, add_node, load_profile, load_graph, dump_graph

_OP_BY_TAG = {"select": "select", "insert": "insert", "update": "update", "delete": "delete"}
_SQL_IDENT = r"(?:[A-Za-z_][\w$]*|`[A-Za-z_][\w$]*`|\"[A-Za-z_][\w$]*\"|'[A-Za-z_][\w$]*')"
_TABLE_RE = re.compile(
    rf"\b(?:from|join|into|update|table)\s+({_SQL_IDENT}(?:\s*\.\s*{_SQL_IDENT})?)",
    re.IGNORECASE,
)
_SQL_OP_RE = re.compile(r"^\s*(select|insert|update|delete)\b", re.IGNORECASE)
# Schema DDL: CREATE/ALTER/DROP TABLE/INDEX/DATABASE/SCHEMA/VIEW. Such files
# *define* tables rather than query them, so raw_sql must not attribute their
# tables to methods (every column name would match some method's terms).
_DDL_RE = re.compile(
    r"\b(?:create|alter|drop)\s+(?:table|index|database|schema|view)\b",
    re.IGNORECASE,
)
# SQL functions / pseudo-tables the table regex can mistakenly capture, e.g.
# ``ON UPDATE CURRENT_TIMESTAMP`` (reads as UPDATE CURRENT_TIMESTAMP) or
# ``SELECT ... FROM dual``.
_SQL_NON_TABLE_TERMS = {
    "current_timestamp", "utc_timestamp", "utc_time", "utc_date",
    "localtimestamp", "localtime", "current_date", "current_time",
    "now", "sysdate", "dual",
}
_JAVA_KEYWORDS = {
    "class", "interface", "public", "private", "protected", "return", "new",
    "null", "true", "false", "void", "object", "string", "long", "int",
}
_GENERIC_TERMS = {
    "add", "by", "count", "create", "delete", "exists", "find", "get",
    "insert", "mapper", "modify", "patch", "query", "read", "remove",
    "repository", "save", "select", "service", "update",
}
_MYBATIS_XML_GLOBS = (
    "**/mapper/**/*.xml",
    "**/mappers/**/*.xml",
    "**/sqlmap/**/*.xml",
    "**/sqlmaps/**/*.xml",
    "**/*Mapper.xml",
    "**/*Mapper*.xml",
)


def _rel_path(root: Path, file: Path) -> str:
    try:
        return file.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(file)


def _root_from_index(index) -> Path:
    """Best-effort root derivation when no explicit root is stored on the index."""
    if not getattr(index, "files", None):
        return Path(".")
    return Path(next(iter(index.files))).parent


_UNESCAPE_MAP = {"n": "\n", "r": "\r", "t": "\t", "'": "'", '"': '"', "\\": "\\"}


def _unescape(s: str) -> str:
    """Targeted Java-string unescape; avoids the unicode_escape footgun that
    corrupts non-ASCII bytes via bytes(s,"utf-8").decode("unicode_escape").

    Single left-to-right pass: consumes the character after each backslash so
    that an escaped backslash (``\\\\n``) decodes to backslash + ``n`` rather
    than being misread as ``\\n`` -> newline."""
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            out.append(_UNESCAPE_MAP.get(nxt, "\\" + nxt))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _tables_in_sql(sql: str) -> list[str]:
    seen: set[str] = set()
    tables: list[str] = []
    for m in _TABLE_RE.finditer(sql):
        table = re.sub(r"\s+", "", m.group(1)).split(".")[-1].strip("`\"'")
        if table.lower() in _SQL_NON_TABLE_TERMS:
            continue
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


def _attr_value(attrs: str, name: str) -> str | None:
    m = re.search(rf"\b{name}\s*=\s*(['\"])(.*?)\1", attrs, re.DOTALL)
    return m.group(2) if m else None


def _mybatis_xml_files(root: Path, configured_glob: str | list[str] | tuple[str, ...]) -> list[Path]:
    patterns: list[str] = []
    if isinstance(configured_glob, str):
        patterns.append(configured_glob)
    else:
        patterns.extend(str(item) for item in configured_glob)
    patterns.extend(pattern for pattern in _MYBATIS_XML_GLOBS if pattern not in patterns)

    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in patterns:
        for xml in Path(root).glob(pattern):
            if not xml.is_file():
                continue
            resolved = xml.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(xml)
    return files


def _parse_mybatis(root: Path, glob: str | list[str] | tuple[str, ...]) -> list[dict]:
    """Return statement dicts for each MyBatis XML mapped statement."""
    out: list[dict] = []
    statement_rx = re.compile(
        r"<(select|insert|update|delete)\b([^>]*)>(.*?)</\1>",
        re.DOTALL | re.IGNORECASE,
    )
    for xml in _mybatis_xml_files(root, glob):
        try:
            text = xml.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "<mapper" not in text.lower():
            continue
        mapper_m = re.search(r"<mapper\b([^>]*)>", text, re.DOTALL | re.IGNORECASE)
        namespace = _attr_value(mapper_m.group(1), "namespace") if mapper_m else ""
        namespace = namespace or ""
        for blk in statement_rx.finditer(text):
            tag, attrs, sql = blk.group(1).lower(), blk.group(2), blk.group(3)
            method = _attr_value(attrs, "id")
            if not method:
                continue
            tables = _tables_in_sql(sql)
            out.append({"source": "mybatis_xml", "file": _rel_path(root, xml),
                        "namespace": namespace, "method": method, "op": _OP_BY_TAG[tag],
                        "tables": tables, "sql": sql.strip()})
    return out


def _qualname_from_namespace(namespace: str, method: str) -> str:
    """com.example.mapper.OrderMapper + selectByStoreNo -> OrderMapper.selectByStoreNo"""
    cls = namespace.rsplit(".", 1)[-1] if namespace else ""
    return f"{cls}.{method}" if cls else method


def _class_name(text: str) -> str | None:
    m = re.search(r"\b(?:class|interface|enum)\s+(\w+)", text)
    return m.group(1) if m else None


def _parse_mybatis_annotations(root: Path, index) -> list[dict]:
    out: list[dict] = []
    annotation_rx = re.compile(
        r"@(?:[\w.]+\.)?(Select|Insert|Update|Delete)\s*\(\s*\"((?:\\.|[^\"])*)\""
    )
    method_rx = re.compile(r"\b([A-Za-z_]\w*)\s*\([^)]*\)\s*(?:;|\{)?")
    for java in [Path(p) for p in index.files if p.endswith(".java")]:
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
            sql = _unescape(m.group(2))
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
                out.append({"source": "mybatis_annotation", "file": _rel_path(root, java),
                            "qual": f"{cls}.{method}", "method": method, "op": op,
                            "tables": _tables_in_sql(sql), "sql": sql})
    return out


def _parse_jpa(root: Path, index) -> list[dict]:
    entities: dict[str, str] = {}
    repos: list[tuple[str, str, str, Path]] = []
    method_rx = re.compile(r"\b([A-Za-z_]\w*)\s*\([^)]*\)\s*(?:;|\{)")
    for java in [Path(p) for p in index.files if p.endswith(".java")]:
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
            repos.append((cls, repo_m.group(1), text, java))

    out: list[dict] = []
    for repo_cls, entity_cls, text, file in repos:
        table = entities.get(entity_cls)
        if not table:
            continue
        for m in method_rx.finditer(text):
            method = m.group(1)
            if method in {repo_cls, "JpaRepository", "CrudRepository"}:
                continue
            out.append({"source": "jpa_repository", "file": _rel_path(root, file),
                        "qual": f"{repo_cls}.{method}", "method": method,
                        "op": _op_from_method(method),
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


def _parse_raw_sql(root: Path, globs: list[str], unit_by_id: dict[str, dict],
                   exclude_dirs: list[str] | None = None) -> list[dict]:
    out: list[dict] = []
    units_with_terms = [(uid, _unit_terms(unit)) for uid, unit in unit_by_id.items()]
    excluded = {d.lower().strip("/") for d in (exclude_dirs or [])}
    root_resolved = root.resolve()
    for glob in globs:
        for sql_file in Path(root).glob(glob):
            # Honor the profile's exclude.dirs (target/, build/, ...) so compiled
            # copies shipped under them aren't scanned.
            try:
                rel_parts = sql_file.resolve().relative_to(root_resolved).parts
            except ValueError:
                rel_parts = sql_file.parts
            if any(part.lower() in excluded for part in rel_parts):
                continue
            try:
                sql = sql_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # A schema DDL file defines tables but is not a method query;
            # term-overlap attribution against it produces mass false positives
            # (every column name matches some method term).
            if _DDL_RE.search(sql):
                continue
            tables = _tables_in_sql(sql)
            if not tables:
                continue
            lower_sql = sql.lower()
            for uid, terms in units_with_terms:
                if terms and any(term in lower_sql for term in terms):
                    out.append({"source": "raw_sql", "file": _rel_path(root, sql_file),
                                "qual": uid, "op": _op_from_sql(sql), "tables": tables,
                                "sql": sql.strip()})

    return out


def _java_string_literals(text: str) -> list[str]:
    strings: list[str] = []
    for m in re.finditer(r'"((?:\\.|[^"\\])*)"', text, re.DOTALL):
        strings.append(_unescape(m.group(1)))
    return strings


def _parse_java_sql_literals(root: Path, unit_by_id: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    for uid, unit in unit_by_id.items():
        file = unit.get("file")
        if not file:
            continue
        try:
            lines = Path(file).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        start = max(int(unit.get("line") or 1) - 1, 0)
        end = int(unit.get("end_line") or len(lines))
        body = "\n".join(lines[start:end])
        for sql in _java_string_literals(body):
            tables = _tables_in_sql(sql)
            if tables:
                out.append({"source": "java_sql_literal", "file": _rel_path(root, Path(file)),
                            "qual": uid, "op": _op_from_sql(sql), "tables": tables, "sql": sql})
    return out


def _statement_record(st: dict, qual: str) -> dict:
    method = st.get("method") or qual.rsplit(".", 1)[-1]
    return {
        "source": st.get("source", "unknown"),
        "file": st.get("file", ""),
        "namespace": st.get("namespace", ""),
        "method": method,
        "qual": qual,
        "statement_id": st.get("statement_id") or qual,
        "op": st.get("op", "unknown"),
        "tables": list(st.get("tables") or []),
        "sql": st.get("sql", ""),
        "linked": False,
        "skip_reason": "",
    }


def resolve_tables(graph: dict, index, profile: dict) -> dict:
    root = Path(index.root) if getattr(index, "root", None) else _root_from_index(index)
    ts = profile.get("table_sources", {})
    statements: list[dict] = []
    unit_by_id = {n["id"]: n for n in graph["nodes"] if n["kind"] == "unit"}

    if "mybatis" in ts:
        glob = ts["mybatis"].get("mapper_xml_glob", "**/mapper/**/*.xml")
        statements += _parse_mybatis(root, glob)
        statements += _parse_mybatis_annotations(root, index)
    if "jpa" in ts:
        statements += _parse_jpa(root, index)
    if "raw_sql" in ts:
        exclude_dirs = profile.get("exclude", {}).get("dirs", [])
        statements += _parse_raw_sql(root, ts.get("raw_sql") or [], unit_by_id, exclude_dirs)
    if "java_sql_literals" in ts:
        statements += _parse_java_sql_literals(root, unit_by_id)

    table_by_name = {n.get("table"): n for n in graph["nodes"] if n["kind"] == "table"}
    db_statements: list[dict] = []

    for st in statements:
        qual = st.get("qual") or _qualname_from_namespace(st.get("namespace", ""), st["method"])
        record = _statement_record(st, qual)
        if not st["tables"]:
            record["skip_reason"] = "no tables found"
            db_statements.append(record)
            continue
        if qual not in unit_by_id:
            record["skip_reason"] = "not in traced call chain"
            db_statements.append(record)
            continue  # only attach tables reached by the traced chain
        record["linked"] = True
        db_statements.append(record)
        for table in st["tables"]:
            if table in table_by_name:
                tnode = table_by_name[table]
            else:
                add_node(graph, {
                    "id": f"table:{table}", "kind": "table", "label": table,
                    "layer": "Table", "table": table, "op": st["op"],
                    "ops": [], "source_unit": qual, "source_units": [],
                    "source_files": [], "statement_ids": [], "statement_sources": [],
                    "sql_snippet": st["sql"], "sql_snippets": [],
                })
                tnode = next(n for n in graph["nodes"]
                             if n["kind"] == "table" and n["table"] == table)
                table_by_name[table] = tnode
            if st["op"] not in tnode.setdefault("ops", []):
                tnode["ops"].append(st["op"])
            if qual not in tnode.setdefault("source_units", []):
                tnode["source_units"].append(qual)
            if record["file"] and record["file"] not in tnode.setdefault("source_files", []):
                tnode["source_files"].append(record["file"])
            if record["statement_id"] not in tnode.setdefault("statement_ids", []):
                tnode["statement_ids"].append(record["statement_id"])
            if record["source"] not in tnode.setdefault("statement_sources", []):
                tnode["statement_sources"].append(record["source"])
            if st["sql"] not in tnode.setdefault("sql_snippets", []):
                tnode["sql_snippets"].append(st["sql"])
            tnode["op"] = ",".join(tnode["ops"])
            tnode["source_unit"] = ",".join(tnode["source_units"])
            tnode["sql_snippet"] = "\n---\n".join(tnode["sql_snippets"])
            add_edge(graph, qual, tnode["id"], "references", "confirmed")["op"] = st["op"]
    graph["db_statements"] = db_statements
    return graph


def main() -> None:
    ap = argparse.ArgumentParser(description="usage-trace Phase 3: resolve DB tables.")
    ap.add_argument("--graph", required=True, help="path to graph JSON (from trace)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    from index import ProjectIndex
    index = ProjectIndex.load_or_build(Path(args.root), profile)
    graph = load_graph(Path(args.graph).read_text(encoding="utf-8"))
    resolve_tables(graph, index, profile)
    sys.stdout.write(dump_graph(graph))


if __name__ == "__main__":
    main()
