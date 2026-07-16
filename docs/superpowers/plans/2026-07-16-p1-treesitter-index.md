# P1: tree-sitter 引擎 + 项目索引 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace regex/brace-counting parsing with a tree-sitter-backed `ProjectIndex` so a keyword query resolves usage sites, call chains, and DB tables via in-memory indexes (fast, accurate, scan-once with on-disk incremental cache).

**Architecture:** A new `ProjectIndex` (`src/index.py`) parses every source file once with a per-language tree-sitter adapter (`src/parsing.py`), building symbol / field / call / reverse-call tables plus a layer cache. `trace`, `discover`, and `tables` consume the index instead of re-grepping the whole tree. The index persists to `<root>/.usage-trace/index/` with file-level mtime+hash incremental invalidation. The graph dict shape produced by `trace` is unchanged, so `graph.py` / `render.py` / `understand_rules.py` are untouched.

**Tech Stack:** Python 3.10+, tree-sitter (>=0.25) + tree-sitter-java, pytest, ruff. SQL/table extraction stays regex.

## Global Constraints

- **Python:** >=3.10.
- **New runtime deps:** `tree-sitter>=0.25`, `tree-sitter-java>=0.23` (prebuilt wheels; no local compilation on macOS/Linux/Windows x64+arm). Add to `pyproject.toml` `[project].dependencies`.
- **tree-sitter is a hard analysis-time dependency.** No regex-parser fallback (avoid dual-engine maintenance). It never enters the report.
- **Report constraint unchanged:** single offline HTML file, no external HTTP assets.
- **Cache location:** `<root>/.usage-trace/index/` (`manifest.json` + `symbols/<sha>.json`); `INDEX_VERSION = 1`; invalidate per file by `mtime+size` fast path then `sha256` confirm; whole-cache rebuild if `root_hash` or `version` changes. If the cache dir is not writable, build in-memory without persisting (graceful).
- **Commits:** repo convention is no auto-commit. At each "Commit" step, stage the files and ask the user before running `git commit`.
- **Backward compatibility:** CLI flags, `usage-trace` / `codex-find` entry points, and the 5 debug subcommands (`python -m discover|trace|tables|graph|render`) must keep working.
- **Scope:** Java only in P1. The `LANGUAGES` registry is the extension point for P4 (C#/Python).
- **Regression gates (every task):** `python3 -m pytest`, `python3 -m ruff check .`, `python3 -m compileall -q src tests`, `git diff --check`.
- **`conftest.py`** already inserts `src/` on `sys.path` and provides `fixture_root` and `profiles_dir` fixtures — use them in tests.

## File Structure

- **Create** `src/parsing.py` — tree-sitter adapter: `LanguageParser` interface, `JavaParser`, dataclasses (`MethodSymbol`, `FieldSymbol`, `CallSite`, `FileSymbols`), `LANGUAGES` registry, `parser_for(path)`.
- **Create** `src/index.py` — `ProjectIndex`: build / load / save / incremental invalidate; `enclosing_method`, `symbol_types`, `resolve_callee_targets`; in-memory indexes.
- **Modify** `src/trace.py` — rewrite `trace()` to consume `ProjectIndex` + `deque` BFS; delete dead `walk()`; remove now-unused regex helpers (`find_enclosing_unit`, `_symbol_types`, `_callee_refs_in_unit`, `_resolve_definition`, `_callers_of`, `_matches_target_call`, `_receiver_for_call`, `_signature_line`, `_strip_comment`, `_current_class`, `_class_name`, `_layer_of_file`, `_callees_in_unit`). Keep `HARD_DEPTH_CAP`.
- **Modify** `src/discover.py` — `discover(keyword, profile, extra_variants, index)` searches `index.files` instead of `grep`.
- **Modify** `src/tables.py` — `resolve_tables(graph, index, profile)`; source Java files from `index.files`; fix `unicode_escape` footgun.
- **Modify** `src/usage_trace.py` — `run()` calls `ProjectIndex.load_or_build(root, profile)`; debug subcommands build a transient index.
- **Modify** `pyproject.toml` — add deps; keep `py-modules` list (add `index`, `parsing`).
- **Modify** `tests/test_trace.py` — drop `walk` import + 3 `test_walk_*`; convert `find_enclosing_unit` tests to `index.enclosing_method`.
- **Modify** `tests/test_discover.py`, `tests/test_tables.py`, `tests/test_cli.py`, `tests/test_e2e.py` — pass/accept the index where signatures changed.
- **Create** `tests/test_parsing.py`, `tests/test_index.py`.
- **Create** `tests/fixtures/java-spring/src/main/java/com/example/service/EdgeCaseService.java` — string `"}"` + block comment inside a method body (proves #6).

---

### Task 1: Add tree-sitter deps + `parsing.py` (Java extraction)

**Files:**
- Modify: `pyproject.toml`
- Create: `src/parsing.py`
- Create: `tests/test_parsing.py`
- Create: `tests/fixtures/java-spring/src/main/java/com/example/service/EdgeCaseService.java`

**Interfaces:**
- Produces: `parsing.JavaParser().parse(source: str, file: str) -> FileSymbols`; `parsing.LANGUAGES: dict[str, type[LanguageParser]]`; `parsing.parser_for(path: str) -> LanguageParser | None`. Dataclasses: `MethodSymbol(name, qual, file, start_line, end_line, params, cls)`, `FieldSymbol(cls, name, type)`, `CallSite(caller_qual, callee_name, receiver, file, line)`, `FileSymbols(methods, fields, inheritance, calls)` with `to_dict()`/`from_dict()`.

- [ ] **Step 1: Add deps to `pyproject.toml`**

In `[project].dependencies` replace:
```toml
dependencies = [
  "pyyaml>=6.0",
]
```
with:
```toml
dependencies = [
  "pyyaml>=6.0",
  "tree-sitter>=0.25",
  "tree-sitter-java>=0.23",
]
```
In `[tool.setuptools]` `py-modules`, append `"index"` and `"parsing"` so the list reads:
```toml
py-modules = ["usage_trace", "codex_find", "common", "discover", "graph", "render", "tables", "trace", "understand_rules", "index", "parsing"]
```

- [ ] **Step 2: Install**

Run: `python3 -m pip install -e ".[dev]"`
Expected: installs `tree-sitter` and `tree-sitter-java`; no errors.

- [ ] **Step 3: Write the failing test `tests/test_parsing.py`**

```python
from parsing import JavaParser, FileSymbols


JAVA_BASIC = """\
package com.example.service;

public class OrderService {
    private final OrderMapper orderMapper;

    public OrderService(OrderMapper orderMapper) {
        this.orderMapper = orderMapper;
    }

    public Object findByStoreNo(String storeNo) {
        return orderMapper.selectByStoreNo(storeNo);
    }
}
"""


def test_parse_methods_fields_calls():
    sym = JavaParser().parse(JAVA_BASIC, "OrderService.java")
    assert isinstance(sym, FileSymbols)
    quals = {m.qual for m in sym.methods}
    assert "OrderService.findByStoreNo" in quals
    assert "OrderService.OrderService" in quals  # constructor

    fields = {(f.cls, f.name, f.type) for f in sym.fields}
    assert ("OrderService", "orderMapper", "OrderMapper") in fields

    calls = {(c.callee_name, c.receiver) for c in sym.calls}
    assert ("selectByStoreNo", "orderMapper") in calls


def test_parse_method_span_ignores_braces_in_strings_and_block_comments():
    # The #6 regression: a "}" inside a string literal and a block comment must
    # NOT skew the method end line. A naive brace counter ends the method early.
    src = """\
public class EdgeCaseService {
    public void tricky(String storeNo) {
        String s = "}{ not a real brace ";
        /* } another fake brace } */
        doWork(storeNo);
    }

    public void after() {
        other();
    }
}
"""
    sym = JavaParser().parse(src, "EdgeCaseService.java")
    by_name = {m.name: m for m in sym.methods}
    # `tricky` body is lines 3-7 (1-indexed). end_line must reach the real closing brace.
    assert by_name["tricky"].start_line == 3
    assert by_name["tricky"].end_line == 7
    # `after` is still parsed -> proves the string/comment braces didn't terminate tricky early
    assert "after" in by_name
    assert any(c.callee_name == "doWork" for c in sym.calls)


def test_parse_inheritance():
    src = "public class Foo extends Bar implements Baz, Qux { void x() {} }"
    sym = JavaParser().parse(src, "Foo.java")
    assert "Bar" in sym.inheritance.get("Foo", [])
    assert "Baz" in sym.inheritance["Foo"]
    assert "Qux" in sym.inheritance["Foo"]


def test_filesymbols_roundtrip():
    sym = JavaParser().parse(JAVA_BASIC, "OrderService.java")
    d = sym.to_dict()
    sym2 = FileSymbols.from_dict(d)
    assert {m.qual for m in sym.methods} == {m.qual for m in sym2.methods}
    assert {f.name for f in sym.fields} == {f.name for f in sym2.fields}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python3 -m pytest tests/test_parsing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'parsing'`.

- [ ] **Step 5: Write `src/parsing.py`**

```python
"""tree-sitter-backed source extraction. P1 ships Java; LANGUAGES is the P4 extension point."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tree_sitter import Language, Parser


@dataclass
class MethodSymbol:
    name: str
    qual: str
    file: str
    start_line: int   # 1-indexed
    end_line: int     # 1-indexed, inclusive
    params: dict[str, str]  # param name -> type
    cls: str


@dataclass
class FieldSymbol:
    cls: str
    name: str
    type: str


@dataclass
class CallSite:
    caller_qual: str
    callee_name: str
    receiver: str | None  # receiver var name when `<expr>.name(`, else None
    file: str
    line: int


@dataclass
class FileSymbols:
    methods: list[MethodSymbol] = field(default_factory=list)
    fields: list[FieldSymbol] = field(default_factory=list)
    inheritance: dict[str, list[str]] = field(default_factory=dict)
    calls: list[CallSite] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "methods": [m.__dict__ for m in self.methods],
            "fields": [f.__dict__ for f in self.fields],
            "inheritance": {k: list(v) for k, v in self.inheritance.items()},
            "calls": [c.__dict__ for c in self.calls],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FileSymbols":
        return cls(
            methods=[MethodSymbol(**m) for m in d.get("methods", [])],
            fields=[FieldSymbol(**f) for f in d.get("fields", [])],
            inheritance={k: list(v) for k, v in d.get("inheritance", {}).items()},
            calls=[CallSite(**c) for c in d.get("calls", [])],
        )


class LanguageParser:
    extension: str = ""

    def parse(self, source: str, file: str) -> FileSymbols:
        raise NotImplementedError


def parser_for(path: str) -> LanguageParser | None:
    cls = LANGUAGES.get(Path(path).suffix)
    return cls() if cls else None


class JavaParser(LanguageParser):
    extension = ".java"
    _parser: Parser | None = None

    @classmethod
    def _ts_parser(cls) -> Parser:
        if cls._parser is None:
            import tree_sitter_java
            lang = Language(tree_sitter_java.language())
            try:
                cls._parser = Parser(lang)
            except TypeError:  # older calling convention
                p = Parser()
                p.set_language(lang)
                cls._parser = p
        return cls._parser

    def parse(self, source: str, file: str) -> FileSymbols:
        src = source.encode("utf-8")
        tree = self._ts_parser().parse(src)
        sym = FileSymbols()
        self._visit(tree.root_node, src, file, [], sym)
        return sym

    def _visit(self, node, src, file, class_stack, sym: FileSymbols) -> None:
        t = node.type
        if t in ("class_declaration", "interface_declaration", "enum_declaration",
                 "record_declaration", "annotation_type_declaration"):
            name_node = node.child_by_field_name("name")
            cls = _text(src, name_node) if name_node else (class_stack[-1] if class_stack else "")
            if cls:
                sym.inheritance.setdefault(cls, [])
                sym.inheritance[cls].extend(_supertypes(node, src))
                class_stack.append(cls)
            for c in node.children:
                self._visit(c, src, file, class_stack, sym)
            if cls:
                class_stack.pop()
            return
        if t in ("method_declaration", "constructor_declaration"):
            cls = class_stack[-1] if class_stack else ""
            name_node = node.child_by_field_name("name")
            name = _text(src, name_node) if name_node else "<init>"
            qual = f"{cls}.{name}" if cls else name
            sym.methods.append(MethodSymbol(
                name=name, qual=qual, file=file,
                start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                params=_params(node, src), cls=cls))
            _collect_calls(node, src, file, qual, sym)
            return
        if t == "field_declaration":
            cls = class_stack[-1] if class_stack else ""
            type_node = node.child_by_field_name("type")
            ftype = _text(src, type_node) if type_node else ""
            for decl in _iter_declarators(node):
                vname = decl.child_by_field_name("name")
                if vname:
                    sym.fields.append(FieldSymbol(cls, _text(src, vname), ftype))
            for c in node.children:
                self._visit(c, src, file, class_stack, sym)
            return
        for c in node.children:
            self._visit(c, src, file, class_stack, sym)


def _text(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "replace") if node else ""


def _supertypes(class_node, src) -> list[str]:
    supers: list[str] = []
    sc = class_node.child_by_field_name("superclass")
    if sc:
        supers.append(_text(src, sc))
    si = class_node.child_by_field_name("interfaces")
    if si:
        for c in si.children:
            if c.type in ("type_identifier", "scoped_type_identifier", "generic_type"):
                supers.append(_text(src, c))
    return supers


def _params(method_node, src) -> dict[str, str]:
    out: dict[str, str] = {}
    pl = method_node.child_by_field_name("parameters")
    if not pl:
        return out
    for c in pl.children:
        if c.type == "formal_parameter":
            tnode = c.child_by_field_name("type")
            nnode = c.child_by_field_name("name")
            if tnode and nnode:
                out[_text(src, nnode)] = _text(src, tnode)
    return out


def _iter_declarators(field_node):
    # Robust to grammar layout: field_declaration -> variable_declarator_list -> variable_declarator
    for c in field_node.children:
        if c.type == "variable_declarator":
            yield c
        for gc in c.children:
            if gc.type == "variable_declarator":
                yield gc


def _collect_calls(method_node, src, file, caller_qual, sym: FileSymbols) -> None:
    stack = list(method_node.children)
    while stack:
        n = stack.pop()
        if n.type == "method_invocation":
            name_node = n.child_by_field_name("name")
            obj_node = n.child_by_field_name("object")
            callee = _text(src, name_node)
            receiver = _text(src, obj_node) if (obj_node is not None and obj_node.type == "identifier") else None
            if callee:
                sym.calls.append(CallSite(caller_qual, callee, receiver, file, n.start_point[0] + 1))
        stack.extend(n.children)


LANGUAGES: dict[str, type[LanguageParser]] = {
    ".java": JavaParser,
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python3 -m pytest tests/test_parsing.py -v`
Expected: PASS (4 tests). If a tree-sitter node-type assertion fails, the failing test names the exact mismatch — adjust the affected `_visit` branch to the installed grammar's node type.

- [ ] **Step 7: Add the edge-case fixture file**

Create `tests/fixtures/java-spring/src/main/java/com/example/service/EdgeCaseService.java`:
```java
package com.example.service;

public class EdgeCaseService {
    public void tricky(String storeNo) {
        String s = "}{ not a real brace ";
        /* } another fake brace } */
        doWork(storeNo);
    }

    public void after() {
        other();
    }
}
```

- [ ] **Step 8: Lint + compile**

Run: `python3 -m ruff check src/parsing.py tests/test_parsing.py && python3 -m compileall -q src tests`
Expected: clean.

- [ ] **Step 9: Stage and ask to commit**

```bash
git add pyproject.toml src/parsing.py tests/test_parsing.py tests/fixtures/java-spring/src/main/java/com/example/service/EdgeCaseService.java
```
Ask the user, then: `git commit -m "feat(p1): add tree-sitter Java parser (methods/fields/calls/inheritance)"`

---

### Task 2: `ProjectIndex` build + in-memory indexes + resolution

**Files:**
- Create: `src/index.py`
- Create: `tests/test_index.py`

**Interfaces:**
- Consumes: `parsing.parser_for`, `parsing.FileSymbols`/`MethodSymbol`; `common.classify_layer`.
- Produces: `ProjectIndex.load_or_build(root, profile, cache_dir=None)`, `.build(root, profile)`, `.enclosing_method(file, line) -> MethodSymbol | None`, `.symbol_types(qual) -> dict[str,str]`, `.resolve_callee_targets(caller_qual, callee_name, receiver) -> list[str]`, plus attributes `.methods`, `.methods_by_name`, `.methods_by_file`, `.fields`, `.calls_by_caller`, `.calls_by_callee`, `.layers`, `.files`.

- [ ] **Step 1: Write the failing test `tests/test_index.py`**

```python
from common import load_profile
from index import ProjectIndex


def test_index_build_and_resolve(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(fixture_root, profile)

    assert "OrderService.findByStoreNo" in idx.methods
    assert "OrderMapper.selectByStoreNo" in idx.methods_by_name.get("selectByStoreNo", [])
    assert idx.fields["OrderService"]["orderMapper"] == "OrderMapper"

    targets = idx.resolve_callee_targets("OrderService.findByStoreNo", "selectByStoreNo", "orderMapper")
    assert targets == ["OrderMapper.selectByStoreNo"]

    st = idx.symbol_types("OrderService.findByStoreNo")
    assert st["this"] == "OrderService"
    assert st["orderMapper"] == "OrderMapper"
    assert st["storeNo"] == "String"

    edge = fixture_root / "src/main/java/com/example/service/EdgeCaseService.java"
    lines = edge.read_text().splitlines()
    call_line = next(i + 1 for i, ln in enumerate(lines) if "doWork(storeNo)" in ln)
    m = idx.enclosing_method(str(edge), call_line)
    assert m is not None and m.name == "tricky"
    # end_line reaches the real closing brace, not the string/comment braces
    close_line = next(i + 1 for i, ln in enumerate(lines) if ln.strip() == "}" and i > call_line - 1)
    assert m.end_line == close_line


def test_resolve_callers_reverse_index(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(fixture_root, profile)
    callers = idx.calls_by_callee.get("selectByStoreNo", [])
    assert any(c.caller_qual == "OrderService.findByStoreNo" for c in callers)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'index'`.

- [ ] **Step 3: Write `src/index.py` (build + resolution; persistence added in Task 3)**

```python
"""ProjectIndex: parse-once symbol/call index with on-disk incremental cache."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from common import classify_layer
from parsing import FileSymbols, parser_for

INDEX_VERSION = 1
_SOURCE_EXTS = (".java",)  # P1; P4 adds .cs/.py via LANGUAGES


class ProjectIndex:
    def __init__(self) -> None:
        self.root_hash: str = ""
        self.files: dict[str, dict] = {}            # path -> {mtime, size, hash}
        self.methods: dict[str, object] = {}        # qual -> MethodSymbol
        self.methods_by_name: dict[str, list[str]] = {}
        self.methods_by_file: dict[str, list[object]] = {}
        self.fields: dict[str, dict[str, str]] = {} # cls -> {field: type}
        self.inheritance: dict[str, list[str]] = {}
        self.calls_by_caller: dict[str, list[object]] = {}
        self.calls_by_callee: dict[str, list[object]] = {}
        self.layers: dict[str, str] = {}
        self._symbols_cache: dict[str, FileSymbols] = {}

    def build(self, root: Path, profile: dict) -> "ProjectIndex":
        root = Path(root)
        self.root_hash = _root_hash(root, profile.get("profile", ""))
        layers = profile.get("layers", [])
        exclude = set(profile.get("exclude", {}).get("dirs", []))
        for path in _walk_sources(root, exclude):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            factory = parser_for(str(path))
            if factory is None:
                continue
            fs = factory.parse(text, str(path))
            self._integrate(str(path), fs)
            self.layers[str(path)] = classify_layer(str(path), layers, text)
            st = path.stat()
            self.files[str(path)] = {
                "mtime": int(st.st_mtime), "size": st.st_size,
                "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            self._symbols_cache[str(path)] = fs
        return self

    def _integrate(self, path: str, fs: FileSymbols) -> None:
        for m in fs.methods:
            self.methods[m.qual] = m
            self.methods_by_name.setdefault(m.name, []).append(m.qual)
            self.methods_by_file.setdefault(path, []).append(m)
        for f in fs.fields:
            self.fields.setdefault(f.cls, {})[f.name] = f.type
        for cls, supers in fs.inheritance.items():
            self.inheritance.setdefault(cls, [])
            for s in supers:
                if s not in self.inheritance[cls]:
                    self.inheritance[cls].append(s)
        for c in fs.calls:
            self.calls_by_caller.setdefault(c.caller_qual, []).append(c)
            self.calls_by_callee.setdefault(c.callee_name, []).append(c)

    def enclosing_method(self, file: str, line: int):
        best = None
        best_span = None
        for m in self.methods_by_file.get(file, []):
            if m.start_line <= line <= m.end_line:
                span = m.end_line - m.start_line
                if best is None or span < best_span:
                    best, best_span = m, span
        return best

    def symbol_types(self, qual: str) -> dict[str, str]:
        m = self.methods.get(qual)
        if not m:
            return {}
        types: dict[str, str] = {"this": m.cls} if m.cls else {}
        types.update(self.fields.get(m.cls, {}))
        types.update(m.params)
        return types

    def resolve_callee_targets(self, caller_qual: str, callee_name: str, receiver: str | None) -> list[str]:
        candidates = self.methods_by_name.get(callee_name, [])
        if not candidates:
            return []
        if receiver:
            rtype = self.symbol_types(caller_qual).get(receiver)
            return [q for q in candidates if _class_of(q) == rtype] if rtype else []
        caller = self.methods.get(caller_qual)
        caller_cls = caller.cls if caller else None
        return [q for q in candidates if _class_of(q) == caller_cls]

    @classmethod
    def load_or_build(cls, root: Path, profile: dict, cache_dir: Path | None = None) -> "ProjectIndex":
        raise NotImplementedError  # replaced in Task 3


def _class_of(qual: str) -> str:
    return qual.rsplit(".", 1)[0] if "." in qual else qual


def _root_hash(root: Path, profile_name: str) -> str:
    try:
        loc = str(root.resolve())
    except OSError:
        loc = str(root)
    return hashlib.sha1(f"{loc}|{profile_name}".encode("utf-8")).hexdigest()[:16]


def _walk_sources(root: Path, exclude: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude]
        for fn in filenames:
            if Path(fn).suffix in _SOURCE_EXTS:
                yield Path(dirpath) / fn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_index.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Lint + compile**

Run: `python3 -m ruff check src/index.py tests/test_index.py && python3 -m compileall -q src`
Expected: clean.

- [ ] **Step 6: Stage and ask to commit**

```bash
git add src/index.py tests/test_index.py
```
Ask the user, then: `git commit -m "feat(p1): ProjectIndex build + symbol/call resolution"`

---

### Task 3: `ProjectIndex` persistence + incremental invalidation

**Files:**
- Modify: `src/index.py` (replace `load_or_build` stub; add `_build_from`, `_save`)
- Modify: `tests/test_index.py` (append cache tests)

**Interfaces:**
- Produces: `ProjectIndex.load_or_build(root, profile, cache_dir=None)` (final). Cache layout: `<cache_dir>/manifest.json` = `{"root_hash","version","files":{path:{mtime,size,hash}}}`; `<cache_dir>/symbols/<hash>.json` per file. Default `cache_dir = <root>/.usage-trace/index`.

- [ ] **Step 1: Write the failing cache tests (append to `tests/test_index.py`)**

```python
import json


def _build_cached(fixture_root, profiles_dir, tmp_path):
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex.load_or_build(fixture_root, profile, cache_dir=tmp_path)
    return profile, idx


def test_index_persists_and_reuses(tmp_path, fixture_root, profiles_dir):
    profile, idx = _build_cached(fixture_root, profiles_dir, tmp_path)
    n = len(idx.methods)
    assert (tmp_path / "manifest.json").exists()
    idx2 = ProjectIndex.load_or_build(fixture_root, profile, cache_dir=tmp_path)
    assert len(idx2.methods) == n


def test_index_invalidates_changed_file(tmp_path, fixture_root, profiles_dir):
    profile, _ = _build_cached(fixture_root, profiles_dir, tmp_path)
    edge = fixture_root / "src/main/java/com/example/service/EdgeCaseService.java"
    original = edge.read_text()
    try:
        edge.write_text(original + "\n    public void brandNew() { done(); }\n}\n")
        idx2 = ProjectIndex.load_or_build(fixture_root, profile, cache_dir=tmp_path)
        assert "EdgeCaseService.brandNew" in idx2.methods
    finally:
        edge.write_text(original)


def test_index_manifest_has_version_and_root_hash(tmp_path, fixture_root, profiles_dir):
    profile, idx = _build_cached(fixture_root, profiles_dir, tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["version"] == 1
    assert manifest["root_hash"] == idx.root_hash
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_index.py -v`
Expected: the 3 new tests FAIL (`NotImplementedError` from `load_or_build`).

- [ ] **Step 3: Implement persistence in `src/index.py`**

Add `import json` at the top. Replace the `load_or_build` stub with the final implementation plus the two helper methods:

```python
    @classmethod
    def load_or_build(cls, root: Path, profile: dict, cache_dir: Path | None = None) -> "ProjectIndex":
        root = Path(root)
        cache_dir = Path(cache_dir) if cache_dir else root / ".usage-trace" / "index"
        idx = cls()
        idx.root_hash = _root_hash(root, profile.get("profile", ""))
        cached_manifest = _read_json(cache_dir / "manifest.json")
        idx._build_from(root, profile, cached_manifest, cache_dir)
        try:
            idx._save(cache_dir)
        except OSError:
            pass  # read-only root: keep in-memory, no persistence
        return idx

    def _build_from(self, root: Path, profile: dict, cached_manifest: dict | None,
                    cache_dir: Path) -> "ProjectIndex":
        layers = profile.get("layers", [])
        exclude = set(profile.get("exclude", {}).get("dirs", []))
        cached_files: dict[str, dict] = {}
        if cached_manifest and cached_manifest.get("root_hash") == self.root_hash \
                and cached_manifest.get("version") == INDEX_VERSION:
            cached_files = cached_manifest.get("files", {})

        for path in _walk_sources(root, exclude):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            factory = parser_for(str(path))
            if factory is None:
                continue
            st = path.stat()
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            self.files[str(path)] = {
                "mtime": int(st.st_mtime), "size": st.st_size, "hash": digest,
            }

            fs = None
            cached = cached_files.get(str(path))
            if cached and cached.get("hash") == digest:
                blob = _read_json(cache_dir / "symbols" / f"{digest}.json")
                if blob:
                    fs = FileSymbols.from_dict(blob)
            if fs is None:
                fs = factory.parse(text, str(path))
            self._integrate(str(path), fs)
            self.layers[str(path)] = classify_layer(str(path), layers, text)
            self._symbols_cache[str(path)] = fs
        return self

    def _save(self, cache_dir: Path) -> None:
        sym_dir = cache_dir / "symbols"
        sym_dir.mkdir(parents=True, exist_ok=True)
        for path, fs in self._symbols_cache.items():
            digest = self.files[path]["hash"]
            target = sym_dir / f"{digest}.json"
            if not target.exists():
                target.write_text(json.dumps(fs.to_dict(), ensure_ascii=False), encoding="utf-8")
        manifest = {"root_hash": self.root_hash, "version": INDEX_VERSION, "files": self.files}
        (cache_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
```

Add the `_read_json` helper near `_walk_sources`:

```python
def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_index.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint + compile**

Run: `python3 -m ruff check src/index.py tests/test_index.py && python3 -m compileall -q src`
Expected: clean.

- [ ] **Step 6: Stage and ask to commit**

```bash
git add src/index.py tests/test_index.py
```
Ask the user, then: `git commit -m "feat(p1): persist ProjectIndex with mtime+hash incremental invalidation"`

---

### Task 4: Rewire `trace.py` to the index (+ `deque`, delete `walk()`)

**Files:**
- Modify: `src/trace.py` (rewrite graph-building; keep `HARD_DEPTH_CAP`, `main`)
- Modify: `tests/test_trace.py` (drop `walk` import + 3 `test_walk_*`; convert `find_enclosing_unit` tests)

**Interfaces:**
- Consumes: `ProjectIndex` (`.methods`, `.calls_by_caller`, `.calls_by_callee`, `.resolve_callee_targets`, `.enclosing_method`, `.layers`).
- Produces: `trace(usages, index, profile, depth=4) -> dict` returning the SAME graph dict shape as before (`nodes` with `id/kind/label/layer/file/line/end_line/usages`; `edges` with `from/to/kind/call`).

- [ ] **Step 1: Rewrite `tests/test_trace.py`**

Replace the entire file with:

```python
from common import load_profile
from discover import discover
from index import ProjectIndex
from trace import HARD_DEPTH_CAP, trace


def test_trace_builds_graph_around_usage(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(fixture_root, profile)
    usages = discover("storeNo", profile, None, idx)
    g = trace(usages, idx, profile, depth=4)

    ids = {n["id"] for n in g["nodes"]}
    assert "OrderService.findByStoreNo" in ids
    edge_pairs = {(e["from"], e["to"]) for e in g["edges"]}
    assert ("OrderService.findByStoreNo", "OrderMapper.selectByStoreNo") in edge_pairs


def test_trace_depth_hard_cap_default():
    assert HARD_DEPTH_CAP == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_trace.py -v`
Expected: FAIL — `trace()` signature/behavior mismatch with the old implementation.

- [ ] **Step 3: Rewrite `src/trace.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_trace.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Lint + compile**

Run: `python3 -m ruff check src/trace.py tests/test_trace.py && python3 -m compileall -q src`
Expected: clean.

- [ ] **Step 6: Stage and ask to commit**

```bash
git add src/trace.py tests/test_trace.py
```
Ask the user, then: `git commit -m "feat(p1): trace via ProjectIndex + deque BFS; remove dead walk()"`

---

### Task 5: Rewire `discover.py` to the index file set

**Files:**
- Modify: `src/discover.py`
- Modify: `tests/test_discover.py`

**Interfaces:**
- Consumes: `ProjectIndex.files` (file list) and `ProjectIndex.layers`.
- Produces: `discover(keyword, profile, extra_variants=None, index=None) -> list[dict]` (same site dict shape: `file/line/col/occurrence_type/layer/snippet`).

- [ ] **Step 1: Update `tests/test_discover.py` to build an index**

At the top add `from index import ProjectIndex`. Convert every existing `discover(keyword, fixture_root, profile, ...)` call to build an index and use the new signature `discover(keyword, profile, variants, idx)`. Representative pattern:

```python
def test_discover_finds_usages(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(fixture_root, profile)
    sites = discover("storeNo", profile, None, idx)
    assert sites
    assert all("line" in s and "snippet" in s for s in sites)
```

Drop the now-unused `root` positional argument everywhere; keep any keyword-variant assertions already present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_discover.py -v`
Expected: FAIL — signature mismatch.

- [ ] **Step 3: Rewrite `discover()` in `src/discover.py`**

Replace the `discover` function with:

```python
def discover(keyword: str, profile: dict, extra_variants: list[str] | None = None,
             index=None) -> list[dict]:
    variants = keyword_variants(keyword, extra_variants)
    pattern = "|".join(re.escape(v) for v in variants)
    rx = re.compile(pattern)
    layers = profile.get("layers", [])
    sites: list[dict] = []
    paths = list(index.files.keys()) if index is not None else []
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        layer = index.layers.get(path) if index is not None else None
        for i, line in enumerate(text.splitlines(), 1):
            code = _code_portion(line)
            m = rx.search(code)
            if not m:
                continue
            sites.append({
                "file": path,
                "line": i,
                "col": m.start() + 1,
                "occurrence_type": _occurrence_type(line, m),
                "layer": layer or classify_layer(path, layers, text),
                "snippet": line.strip(),
            })
    return sites
```

Keep `keyword_variants`, `layer_of`, `_occurrence_type`, `_line_comment_start`, `_code_portion`. Update imports: replace `from common import classify_layer, grep, load_profile` with `from common import classify_layer, load_profile`, and ensure `from pathlib import Path` is present. Update `main()` to build a transient index:

```python
def main() -> None:
    ap = argparse.ArgumentParser(description="usage-trace Phase 1: discover usage sites.")
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--variants", default="")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    from index import ProjectIndex
    index = ProjectIndex.load_or_build(Path(args.root), profile)
    extra_variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    sites = discover(args.keyword, profile, extra_variants, index)
    json.dump(sites, sys.stdout, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_discover.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + compile**

Run: `python3 -m ruff check src/discover.py tests/test_discover.py && python3 -m compileall -q src`
Expected: clean.

- [ ] **Step 6: Stage and ask to commit**

```bash
git add src/discover.py tests/test_discover.py
```
Ask the user, then: `git commit -m "feat(p1): discover over ProjectIndex file set"`

---

### Task 6: Rewire `tables.py` (index files + `unicode_escape` fix)

**Files:**
- Modify: `src/tables.py`
- Modify: `tests/test_tables.py`

**Interfaces:**
- Consumes: `index.files` (Java file list) instead of `Path(root).rglob("*.java")`.
- Produces: `resolve_tables(graph, index, profile) -> dict` (unchanged graph + `db_statements` shape).

- [ ] **Step 1: Confirm the fixture's table name**

Run: `grep -i "from\|update\|table" tests/fixtures/java-spring/src/main/resources/mapper/OrderMapper.xml`
Note the exact table name for the assertion in the next step.

- [ ] **Step 2: Update `tests/test_tables.py` for the index signature**

For each test that calls `resolve_tables(graph, root, profile)`, build an index and call `resolve_tables(graph, idx, profile)`. Representative pattern:

```python
def test_tables_resolve_via_index(fixture_root, profiles_dir):
    from index import ProjectIndex
    from trace import trace
    from discover import discover
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(fixture_root, profile)
    g = trace(discover("storeNo", profile, None, idx), idx, profile, 4)
    resolve_tables(g, idx, profile)
    tables = {n["table"] for n in g["nodes"] if n.get("kind") == "table"}
    assert "<TABLE_NAME_FROM_STEP_1>" in tables
```

(Replace `<TABLE_NAME_FROM_STEP_1>` with the exact name found in Step 1 — this is a concrete value, not a placeholder.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_tables.py -v`
Expected: FAIL — signature/`root` mismatch.

- [ ] **Step 4: Update `src/tables.py`**

(a) Signature + Java file source. Change:
```python
def resolve_tables(graph: dict, root: Path, profile: dict) -> dict:
    root = Path(root)
    ...
    if "mybatis" in ts:
        ...
        statements += _parse_mybatis_annotations(root)
    if "jpa" in ts:
        statements += _parse_jpa(root)
```
to thread `index` through (add `index` param to `_parse_mybatis_annotations` and `_parse_jpa`, replace `Path(root).rglob("*.java")` with iterating `index.files`):
```python
def resolve_tables(graph: dict, index, profile: dict) -> dict:
    root = _root_from_index(index)
    ts = profile.get("table_sources", {})
    ...
    if "mybatis" in ts:
        glob = ts["mybatis"].get("mapper_xml_glob", "**/mapper/**/*.xml")
        statements += _parse_mybatis(root, glob)
        statements += _parse_mybatis_annotations(root, index)
    if "jpa" in ts:
        statements += _parse_jpa(root, index)
    ...
```
Add helper:
```python
def _root_from_index(index) -> Path:
    if not index.files:
        return Path(".")
    return Path(next(iter(index.files))).parent
```
In `_parse_mybatis_annotations(root, index)` and `_parse_jpa(root, index)`, replace:
```python
    for java in Path(root).rglob("*.java"):
```
with:
```python
    for java in [Path(p) for p in index.files if p.endswith(".java")]:
```

(b) Fix the `unicode_escape` footgun. Add a targeted unescaper and use it:
```python
def _unescape(s: str) -> str:
    return (s.replace("\\'", "'").replace('\\"', '"')
             .replace("\\n", "\n").replace("\\r", "\r")
             .replace("\\t", "\t").replace("\\\\", "\\"))
```
Replace in `_java_string_literals`:
```python
        strings.append(bytes(m.group(1), "utf-8").decode("unicode_escape"))
```
with:
```python
        strings.append(_unescape(m.group(1)))
```
and in `_parse_mybatis_annotations`:
```python
            sql = bytes(m.group(2), "utf-8").decode("unicode_escape")
```
with:
```python
            sql = _unescape(m.group(2))
```

(c) Update `main()` to build a transient index:
```python
def main() -> None:
    ap = argparse.ArgumentParser(description="usage-trace Phase 3: resolve DB tables.")
    ap.add_argument("--graph", required=True)
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_tables.py -v`
Expected: PASS.

- [ ] **Step 6: Lint + compile**

Run: `python3 -m ruff check src/tables.py tests/test_tables.py && python3 -m compileall -q src`
Expected: clean.

- [ ] **Step 7: Stage and ask to commit**

```bash
git add src/tables.py tests/test_tables.py
```
Ask the user, then: `git commit -m "feat(p1): tables source Java files from index; fix unicode_escape footgun"`

---

### Task 7: Wire `usage_trace.run()` + CLI + debug subcommands

**Files:**
- Modify: `src/usage_trace.py`
- Modify: `tests/test_cli.py`, `tests/test_e2e.py` (only if they pass removed positional args)

**Interfaces:**
- Produces: `run(keyword, root, profile_name, depth, max_nodes, out, variants)` builds the index once and threads it through discover/trace/tables. The CLI `main()` is externally unchanged.

- [ ] **Step 1: Update `run()` in `src/usage_trace.py`**

Replace the body of `run` with:

```python
def run(keyword: str, root: Path | str, profile_name: str = "auto",
        depth: int = 4, max_nodes: int = 300, out: Path | str | None = None,
        variants: list[str] | None = None) -> dict:
    root = Path(root)
    profile_name = detect_profile_name(root) if profile_name == "auto" else profile_name
    profile = load_profile(profile_name, _profile_dir())
    profile.setdefault("profile", profile_name)

    from index import ProjectIndex
    index = ProjectIndex.load_or_build(root, profile)

    usages = discover(keyword, profile, variants, index)
    if usages:
        graph = trace(usages, index, profile, depth)
    else:
        graph = new_graph({"depth": min(depth, HARD_DEPTH_CAP)})
    graph["meta"]["profile"] = profile_name
    graph = resolve_tables(graph, index, profile)
    graph = prune_and_layout(graph, max_nodes, _layer_order(profile))

    output = Path(out) if out is not None else Path(".usage-trace") / f"{keyword}-report.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "project": root.name,
        "language": profile_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output.write_text(render(graph, keyword, meta, _template_path()), encoding="utf-8")
    return graph
```

- [ ] **Step 2: Run CLI + e2e tests**

Run: `python3 -m pytest tests/test_cli.py tests/test_e2e.py -v`
Expected: PASS. If a test passes a removed positional arg, update it to the documented signature.

- [ ] **Step 3: Lint + compile**

Run: `python3 -m ruff check src/usage_trace.py && python3 -m compileall -q src`
Expected: clean.

- [ ] **Step 4: Stage and ask to commit**

```bash
git add src/usage_trace.py tests/test_cli.py tests/test_e2e.py
```
Ask the user, then: `git commit -m "feat(p1): run() builds ProjectIndex once and threads it through phases"`

---

### Task 8: End-to-end smoke + full regression gate

**Files:** verify only (edge-case fixture added in Task 1).

- [ ] **Step 1: Full test suite**

Run: `python3 -m pytest -q`
Expected: all green.

- [ ] **Step 2: Lint + compile + whitespace**

Run: `python3 -m ruff check . && python3 -m compileall -q src tests && git diff --check`
Expected: clean.

- [ ] **Step 3: Smoke test (matches README quick start)**

Run:
```bash
rm -rf tests/fixtures/java-spring/.usage-trace
python3 src/usage_trace.py --keyword storeNo --root tests/fixtures/java-spring
```
Expected: writes `.usage-trace/storeNo-report.html` (in cwd); exit 0; no traceback.

- [ ] **Step 4: Verify cache reuse**

Run:
```bash
ls tests/fixtures/java-spring/.usage-trace/index/manifest.json
python3 -c "import json; m=json.load(open('tests/fixtures/java-spring/.usage-trace/index/manifest.json')); print(m['version'], len(m['files']), 'files indexed')"
```
Expected: prints `1 <N> files indexed` (N = fixture `.java` count). A second smoke run completes via cache hits.

- [ ] **Step 5: Verify no grep-in-walk (acceptance #3)**

Run: `grep -n "grep(" src/trace.py || echo "no grep in trace.py"`
Expected: `no grep in trace.py`.

- [ ] **Step 6: Stage and ask to commit (final P1 commit)**

```bash
git add -A
```
Ask the user, then: `git commit -m "test(p1): full regression green; smoke + cache reuse verified"`

---

## Self-Review

**1. Spec coverage:**
- tree-sitter Java parse (methods/fields/calls/inheritance) → Task 1 ✓
- #6 string/block-comment brace accuracy → Task 1 `test_parse_method_span_ignores_braces_...` + Task 2 `enclosing_method` assertion ✓
- `ProjectIndex` (build + indexes) → Task 2 ✓
- `enclosing_method` / `symbol_types` / `resolve_callee_targets` → Task 2 ✓
- trace via index + deque + delete `walk()` + no grep-in-walk → Task 4 (+ Task 8 Step 5) ✓
- scan-once + mtime+hash incremental cache → Task 3 ✓
- tables source Java files from index + `unicode_escape` fix → Task 6 ✓
- discover over index files → Task 5 ✓
- `run()` builds index once → Task 7 ✓
- deps (`tree-sitter>=0.25`, `tree-sitter-java`) → Task 1 ✓
- debug subcommands + CLI compat → Tasks 4/5/6/7 `main()` + Task 8 smoke ✓
- Java-only scope; `LANGUAGES` extension point → Task 1 ✓
- regression gates → every task + Task 8 ✓
- No gaps.

**2. Placeholder scan:** Task 6 Step 2 contains `<TABLE_NAME_FROM_STEP_1>` which is resolved to a concrete value by the verifiable read in Step 1 of the same task — not an open TODO. No `TBD` / `implement later` / `add error handling` anywhere. All code steps show full code.

**3. Type/name consistency:** `MethodSymbol.qual/.name/.cls/.start_line/.end_line/.params`, `CallSite.caller_qual/.callee_name/.receiver/.file/.line`, `FileSymbols.to_dict/from_dict`, `ProjectIndex.methods/.methods_by_name/.methods_by_file/.fields/.calls_by_caller/.calls_by_callee/.layers/.files`, `enclosing_method` / `symbol_types` / `resolve_callee_targets` / `load_or_build` — identical across all tasks. `trace(usages, index, profile, depth)`, `discover(keyword, profile, extra_variants, index)`, `resolve_tables(graph, index, profile)` signatures match between producers and consumers. `INDEX_VERSION=1`, `HARD_DEPTH_CAP=8` consistent.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-16-p1-treesitter-index.md`.
