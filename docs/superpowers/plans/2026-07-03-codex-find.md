# codex-find Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `codex-find`, a Claude Code subagent that takes a keyword + project root, traces its usage → call chain → DB tables, and emits a single self-contained HTML/SVG report.

**Architecture:** Agent/script split — a Claude Code subagent (`.claude/agents/codex-find.md`) orchestrates a 5-phase pipeline; deterministic Python helpers (`src/*.py`) do grep/parse/render; phases pass JSON graphs between them. A declarative language profile (`profiles/*.yml`) makes the analyzer pluggable per language; v1 ships Java/Spring.

**Tech Stack:** Python 3.10+, PyYAML (profile loading), pytest (tests), ripgrep (optional, with Python fallback). Output: vanilla HTML + hand-written SVG, no JS framework, no runtime network.

## Global Constraints

- **Python ≥ 3.10.** Every module starts with `from __future__ import annotations`.
- **Runtime deps: only PyYAML.** Dev deps: `pytest`. No network at runtime; report is a single offline HTML file with no external assets.
- **Node schema** (the graph's single source of truth): `node = {id, kind: "unit"|"table"|"usage", label, layer, file, line, ...}`; `edge = {from, to, kind: "call"|"references", confidence: "confirmed"|"inferred"}`. Every module uses these exact field names.
- **Unit node id = Java qualname** (`ClassName.methodName`), stable and human-readable.
- **Layer names** for v1: `"Controller"`, `"Service"`, `"Repository"`, `"Unknown"`. Table nodes use layer `"Table"`.
- **Usage site dict** (discover output): `{file, line, col, occurrence_type, layer, snippet}`.
- **Caps:** depth default 4 / hard cap 8 (enforced in `trace.py`); `max_nodes` 300 (enforced in `graph.py`).
- **File layout** exactly as spec §10 (paths in each task).
- `rg` is optional — `common.grep` falls back to pure Python.
- Commits after each task (Task 1 inits the git repo).

---

### Task 1: Project scaffold, test harness, Java/Spring fixture

**Files:**
- Create: `codex-find/requirements.txt`, `codex-find/requirements-dev.txt`, `codex-find/.gitignore`
- Create: `codex-find/tests/conftest.py`
- Create: `codex-find/tests/fixtures/java-spring/pom.xml`
- Create: `codex-find/tests/fixtures/java-spring/src/main/java/com/example/controller/OrderController.java`
- Create: `codex-find/tests/fixtures/java-spring/src/main/java/com/example/service/OrderService.java`
- Create: `codex-find/tests/fixtures/java-spring/src/main/java/com/example/service/StoreService.java`
- Create: `codex-find/tests/fixtures/java-spring/src/main/java/com/example/mapper/OrderMapper.java`
- Create: `codex-find/tests/fixtures/java-spring/src/main/resources/mapper/OrderMapper.xml`
- Create: `codex-find/tests/test_scaffold.py`
- Create: `codex-find/src/__init__.py` (empty), `codex-find/tests/__init__.py` (empty)

**Interfaces:**
- Consumes: nothing.
- Produces: `fixture_root` and `profiles_dir` pytest fixtures (in `conftest.py`); a runnable pytest suite; a git repo. `tests/conftest.py` also puts `src/` on `sys.path` so later tasks can `import common`, etc.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_scaffold.py`:
```python
from pathlib import Path


def test_fixture_files_exist(fixture_root):
    expected = [
        "pom.xml",
        "src/main/java/com/example/controller/OrderController.java",
        "src/main/java/com/example/service/OrderService.java",
        "src/main/java/com/example/service/StoreService.java",
        "src/main/java/com/example/mapper/OrderMapper.java",
        "src/main/resources/mapper/OrderMapper.xml",
    ]
    for rel in expected:
        assert (fixture_root / rel).exists(), f"missing fixture file: {rel}"


def test_fixture_store_no_chain_present(fixture_root):
    # The known chain the whole test-suite depends on.
    ctrl = (fixture_root / "src/main/java/com/example/controller/OrderController.java").read_text()
    svc = (fixture_root / "src/main/java/com/example/service/OrderService.java").read_text()
    mp = (fixture_root / "src/main/resources/mapper/OrderMapper.xml").read_text()
    assert "queryByStoreNo" in ctrl and "storeNo" in ctrl
    assert "findByStoreNo" in svc and "storeNo" in svc
    assert "selectByStoreNo" in mp and "t_order" in mp and "store_no" in mp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_scaffold.py -v`
Expected: FAIL (fixtures / conftest missing).

- [ ] **Step 3: Create scaffold + fixture**

`codex-find/requirements.txt`:
```
pyyaml>=6.0
```

`codex-find/requirements-dev.txt`:
```
-r requirements.txt
pytest>=7.0
```

`codex-find/.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
output/
.superpowers/
```

`codex-find/tests/conftest.py`:
```python
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
# Make src/ importable as top-level modules (common, discover, ...).
sys.path.insert(0, str(ROOT.parent / "src"))


@pytest.fixture
def fixture_root():
    return ROOT / "fixtures" / "java-spring"


@pytest.fixture
def profiles_dir():
    return ROOT.parent / "profiles"
```

`codex-find/tests/__init__.py` — empty file.
`codex-find/src/__init__.py` — empty file.

`codex-find/tests/fixtures/java-spring/pom.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>fixture</artifactId>
  <version>1.0.0</version>
</project>
```

`codex-find/tests/fixtures/java-spring/src/main/java/com/example/controller/OrderController.java`:
```java
package com.example.controller;

import com.example.service.OrderService;

@org.springframework.web.bind.annotation.RestController
public class OrderController {
    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    public Object queryByStoreNo(String storeNo) {
        return orderService.findByStoreNo(storeNo);
    }
}
```

`codex-find/tests/fixtures/java-spring/src/main/java/com/example/service/OrderService.java`:
```java
package com.example.service;

import com.example.mapper.OrderMapper;

@org.springframework.stereotype.Service
public class OrderService {
    private final OrderMapper orderMapper;

    public OrderService(OrderMapper orderMapper) {
        this.orderMapper = orderMapper;
    }

    public Object findByStoreNo(String storeNo) {
        return orderMapper.selectByStoreNo(storeNo);
    }
}
```

`codex-find/tests/fixtures/java-spring/src/main/java/com/example/service/StoreService.java` (ambiguous same-name method in a different class):
```java
package com.example.service;

@org.springframework.stereotype.Service
public class StoreService {
    // Same method name as OrderService.findByStoreNo — exercises ambiguity handling.
    public Object findByStoreNo(String storeNo) {
        return null;
    }
}
```

`codex-find/tests/fixtures/java-spring/src/main/java/com/example/mapper/OrderMapper.java`:
```java
package com.example.mapper;

@org.apache.ibatis.annotations.Mapper
public interface OrderMapper {
    Object selectByStoreNo(String storeNo);
}
```

`codex-find/tests/fixtures/java-spring/src/main/resources/mapper/OrderMapper.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="com.example.mapper.OrderMapper">
  <select id="selectByStoreNo" resultType="object">
    SELECT * FROM t_order WHERE store_no = #{storeNo}
  </select>
</mapper>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_scaffold.py -v`
Expected: 2 passed.

- [ ] **Step 5: Init repo and commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
python -m pip install -r requirements-dev.txt
git init && git add -A
git commit -m "chore: scaffold project, test harness, java-spring fixture"
```

---

### Task 2: common.py — profile loader, graph IO, grep wrapper

**Files:**
- Create: `codex-find/src/common.py`
- Test: `codex-find/tests/test_common.py`

**Interfaces:**
- Consumes: nothing.
- Produces (imported by every later task):
  - `load_profile(name: str, profiles_dir: Path | None = None) -> dict`
  - `grep(pattern: str, root: Path, glob: str = "*", exclude_dirs: Iterable[str] = ()) -> list[dict]` → `[{file, line, col, text}]`
  - `new_graph(meta: dict | None = None) -> dict`, `add_node(g, node) -> str`, `add_edge(g, frm, to, kind="call", confidence="confirmed") -> dict`
  - `dump_graph(g) -> str`, `load_graph(s) -> dict`

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_common.py`:
```python
import json
from pathlib import Path

from common import (
    load_profile, grep, new_graph, add_node, add_edge, dump_graph, load_graph,
)


def test_graph_roundtrip():
    g = new_graph({"keyword": "storeNo"})
    a = add_node(g, {"kind": "unit", "label": "A.foo", "layer": "Service"})
    b = add_node(g, {"kind": "unit", "label": "A.bar", "layer": "Service"})
    add_edge(g, a, b)
    s = dump_graph(g)
    g2 = load_graph(s)
    assert len(g2["nodes"]) == 2
    assert g2["edges"][0]["from"] == a and g2["edges"][0]["to"] == b
    assert g["nodes"][0]["id"] != g["nodes"][1]["id"]


def test_grep_finds_store_no(fixture_root):
    hits = grep(r"storeNo", fixture_root, "*", ("target", "node_modules"))
    files = {Path(h["file"]).name for h in hits}
    assert "OrderController.java" in files
    assert "OrderService.java" in files
    for h in hits:
        assert h["line"] >= 1 and h["col"] >= 1 and h["text"]


def test_grep_excludes_dirs(fixture_root):
    hits = grep(r"storeNo", fixture_root, "*", ("target",))
    assert not any("target" in h["file"] for h in hits)


def test_load_profile_not_found(profiles_dir):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_profile("does-not-exist", profiles_dir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_common.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'common'`).

- [ ] **Step 3: Write minimal implementation**

`codex-find/src/common.py`:
```python
"""Shared utilities: profile loading, graph schema IO, grep wrapper (rg or pure Python)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - import guard
    yaml = None


# ---- Profile loading ----
def load_profile(name: str, profiles_dir: Path | None = None) -> dict:
    """Load a language profile YAML by name ('java-spring') or by path."""
    p = Path(name)
    if not p.is_absolute() and not p.exists() and profiles_dir is not None:
        for ext in (".yml", ".yaml"):
            cand = Path(profiles_dir) / f"{name}{ext}"
            if cand.exists():
                p = cand
                break
    if not p.exists():
        raise FileNotFoundError(f"profile not found: {name}")
    if yaml is None:
        raise RuntimeError("PyYAML is required to load profiles: pip install pyyaml")
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---- Graph schema IO ----
def new_graph(meta: dict | None = None) -> dict:
    return {"meta": meta or {}, "nodes": [], "edges": []}


def add_node(g: dict, node: dict) -> str:
    if not node.get("id"):
        node["id"] = f"n{len(g['nodes']) + 1}"
    g["nodes"].append(node)
    return node["id"]


def add_edge(g: dict, frm: str, to: str, kind: str = "call",
             confidence: str = "confirmed") -> dict:
    e = {"from": frm, "to": to, "kind": kind, "confidence": confidence}
    g["edges"].append(e)
    return e


def dump_graph(g: dict) -> str:
    return json.dumps(g, ensure_ascii=False, indent=2)


def load_graph(s: str | bytes) -> dict:
    if isinstance(s, bytes):
        s = s.decode("utf-8")
    return json.loads(s)


# ---- Grep wrapper ----
def has_ripgrep() -> bool:
    return shutil.which("rg") is not None


def _is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" in f.read(2048)
    except OSError:
        return True


def grep(pattern: str, root: Path, glob: str = "*",
         exclude_dirs: Iterable[str] = ()) -> list[dict]:
    """Search text files under root for regex `pattern`. Returns [{file, line, col, text}]."""
    root = Path(root)
    excludes = set(exclude_dirs)
    if has_ripgrep():
        try:
            return _grep_rg(pattern, root, excludes)
        except FileNotFoundError:
            pass
    return _grep_py(pattern, root, excludes)


def _grep_rg(pattern: str, root: Path, excludes: set[str]) -> list[dict]:
    cmd = ["rg", "--line-number", "--column", "--no-heading", "--color=never"]
    for d in excludes:
        cmd += ["--glob", f"!{d}/**"]
    cmd += [pattern, str(root)]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    results = []
    for line in out.stdout.splitlines():
        m = re.match(r"^(.*?):(\d+):(\d+):(.*)$", line)
        if m:
            results.append({"file": m.group(1), "line": int(m.group(2)),
                            "col": int(m.group(3)), "text": m.group(4)})
    return results


def _grep_py(pattern: str, root: Path, excludes: set[str]) -> list[dict]:
    rx = re.compile(pattern)
    results: list[dict] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in excludes for part in path.parts):
            continue
        if _is_binary(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    m = rx.search(line)
                    if m:
                        results.append({"file": str(path), "line": i,
                                        "col": m.start() + 1,
                                        "text": line.rstrip("\n")})
        except OSError:
            continue
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_common.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add src/common.py tests/test_common.py
git commit -m "feat(common): profile loader, graph schema IO, grep wrapper"
```

---

### Task 3: java-spring.yml profile

**Files:**
- Create: `codex-find/profiles/java-spring.yml`
- Test: `codex-find/tests/test_profile_java.py`

**Interfaces:**
- Consumes: `common.load_profile`.
- Produces: a profile dict with keys `profile, detect.files, layers[], table_sources.{jpa,mybatis,raw_sql}, call_patterns.{method_invocation,chain_step}, exclude.dirs`. Consumed by discover/trace/tables.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_profile_java.py`:
```python
from common import load_profile


def test_profile_loads(profiles_dir):
    p = load_profile("java-spring", profiles_dir)
    assert p["profile"] == "java-spring"
    assert "pom.xml" in p["detect"]["files"]


def test_profile_layers_ordered(profiles_dir):
    p = load_profile("java-spring", profiles_dir)
    names = [L["name"] for L in p["layers"]]
    assert names == ["Controller", "Service", "Repository"]


def test_profile_table_sources(profiles_dir):
    p = load_profile("java-spring", profiles_dir)
    ts = p["table_sources"]
    assert "mybatis" in ts and "jpa" in ts
    assert ts["mybatis"]["namespace_to_interface"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_profile_java.py -v`
Expected: FAIL (`FileNotFoundError: profile not found: java-spring`).

- [ ] **Step 3: Write minimal implementation**

`codex-find/profiles/java-spring.yml`:
```yaml
profile: java-spring
detect:
  files: [pom.xml, build.gradle]
layers:
  - {name: Controller, match: "@RestController|@Controller", path_hint: "controller"}
  - {name: Service, match: "@Service", path_hint: "service"}
  - {name: Repository, match: "@Repository|@Mapper", path_hint: "(mapper|repository|dao)"}
table_sources:
  jpa: {entity_annotation: "@Entity", table_annotation: '@Table\s*\(\s*name\s*=\s*"([^"]+)"'}
  mybatis: {mapper_xml_glob: "**/mapper/**/*.xml", namespace_to_interface: true}
  raw_sql: ["**/*.sql"]
call_patterns:
  method_invocation: '\b([A-Za-z_][\w]*)\s*\('
  chain_step: '\.\s*([A-Za-z_]\w*)\s*\('
exclude:
  dirs: [target, node_modules, .git, dist, build, .idea]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_profile_java.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add profiles/java-spring.yml tests/test_profile_java.py
git commit -m "feat(profiles): java-spring language profile"
```

---

### Task 4: discover.py — Phase 1 usage discovery

**Files:**
- Create: `codex-find/src/discover.py`
- Test: `codex-find/tests/test_discover.py`

**Interfaces:**
- Consumes: `common.grep`; profile dict (`exclude.dirs`, `layers`).
- Produces:
  - `keyword_variants(keyword: str) -> list[str]`
  - `layer_of(file: str, layers: list[dict]) -> str`
  - `discover(keyword: str, root: Path, profile: dict) -> list[dict]` → usage sites `[{file, line, col, occurrence_type, layer, snippet}]`
  - `main()` CLI: `discover.py --keyword K --variants "" --root PATH --profile NAME` → sites JSON on stdout.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_discover.py`:
```python
from pathlib import Path

from common import load_profile
from discover import keyword_variants, layer_of, discover


def test_variants_cover_forms():
    v = keyword_variants("storeNo")
    assert "storeNo" in v and "store_no" in v and "STORE_NO" in v and "StoreNo" in v


def test_layer_of_by_path_hint():
    layers = [{"name": "Controller", "path_hint": "controller"},
              {"name": "Service", "path_hint": "service"},
              {"name": "Repository", "path_hint": "(mapper|repository|dao)"}]
    assert layer_of("pkg/service/OrderService.java", layers) == "Service"
    assert layer_of("pkg/mapper/OrderMapper.java", layers) == "Repository"
    assert layer_of("pkg/util/Helper.java", layers) == "Unknown"


def test_discovers_fixture_sites(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    sites = discover("storeNo", fixture_root, profile)
    files = {Path(s["file"]).name for s in sites}
    assert "OrderController.java" in files
    assert "OrderService.java" in files
    assert "OrderMapper.java" in files
    s = sites[0]
    assert set(s) == {"file", "line", "col", "occurrence_type", "layer", "snippet"}
    assert any(s["layer"] == "Service" and "OrderService" in s["file"] for s in sites)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_discover.py -v`
Expected: FAIL (`No module named 'discover'`).

- [ ] **Step 3: Write minimal implementation**

`codex-find/src/discover.py`:
```python
"""Phase 1: discover keyword usage sites across the project."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import grep, load_profile

_CONTROL = {"if", "for", "while", "switch", "catch", "return", "new", "super", "this"}


def keyword_variants(keyword: str) -> list[str]:
    """Expand a keyword into common naming variants (longest first)."""
    parts = [p for p in re.split(r"[_\-]+|(?<=[a-z0-9])(?=[A-Z])", keyword) if p] or [keyword]
    lower = "_".join(p.lower() for p in parts)
    variants = {
        keyword,
        lower,                                  # store_no
        lower.upper(),                          # STORE_NO
        "".join(p.lower() for p in parts),      # storeno
        "-".join(p.lower() for p in parts),     # store-no
        "".join(p.capitalize() for p in parts), # StoreNo
        lower + "s",                            # store_nos
        lower + "_list",
    }
    return sorted(variants, key=len, reverse=True)


def layer_of(file: str, layers: list[dict]) -> str:
    """Classify a file by its path (package) against layer path_hints."""
    fpath = str(file).replace("\\", "/")
    for L in layers:
        hint = L.get("path_hint")
        if hint and re.search(hint, fpath, re.IGNORECASE):
            return L["name"]
    return "Unknown"


def _occurrence_type(text: str, match: re.Match) -> str:
    before = text[: match.start()].rstrip()
    if before.endswith("@"):
        return "annotation"
    seg = text[match.start(): match.end() + 1]
    if ('"' in seg) or ("'" in seg):
        return "string"
    if re.search(r"\b(public|private|protected|void|int|long|String|var|boolean)\b", before) \
            and "(" in text[match.start():]:
        return "definition"
    return "identifier"


def discover(keyword: str, root: Path, profile: dict) -> list[dict]:
    variants = keyword_variants(keyword)
    pattern = "|".join(re.escape(v) for v in variants)
    exclude = profile.get("exclude", {}).get("dirs", [])
    layers = profile.get("layers", [])
    sites: list[dict] = []
    for h in grep(pattern, Path(root), "*", exclude):
        m = re.search(pattern, h["text"])
        otype = _occurrence_type(h["text"], m) if m else "identifier"
        sites.append({
            "file": h["file"],
            "line": h["line"],
            "col": h["col"],
            "occurrence_type": otype,
            "layer": layer_of(h["file"], layers),
            "snippet": h["text"].strip(),
        })
    return sites


def main() -> None:
    ap = argparse.ArgumentParser(description="codex-find Phase 1: discover usage sites.")
    ap.add_argument("--keyword", required=True)
    ap.add_argument("--variants", default="",
                    help="comma-separated extra variants (optional; auto-expanded if empty)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    sites = discover(args.keyword, Path(args.root), profile)
    json.dump(sites, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_discover.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add src/discover.py tests/test_discover.py
git commit -m "feat(discover): phase 1 keyword usage discovery"
```

---

### Task 5: trace.py — Phase 2 call-chain tracing

**Files:**
- Create: `codex-find/src/trace.py`
- Test: `codex-find/tests/test_trace.py`

**Interfaces:**
- Consumes: usage sites (discover output), `common.grep`, profile (`call_patterns`, `exclude.dirs`, `layers`).
- Produces:
  - `walk(seeds, neighbors, depth) -> tuple[set, list[tuple[str,str,str]]]` — pure, cycle-safe, depth-capped (hard cap 8). Edges are `(from, to, confidence)`.
  - `find_enclosing_unit(file: Path, target_line: int) -> dict | None` → `{id, name, qualname, file, line, end_line}`.
  - `trace(usages, root, profile, depth=4) -> dict` → graph `{meta, nodes, edges}`.
  - `main()` CLI: `trace.py --usages PATH --root PATH --profile NAME --depth N` → graph JSON on stdout.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_trace.py`:
```python
from common import load_profile
from discover import discover
from trace import walk, find_enclosing_unit, trace


# ---- walk: cycle + depth (pure, no fixture) ----

def test_walk_detects_cycle_and_terminates():
    graph = {"A": ["B"], "B": ["A"]}
    neighbors = lambda node, direction: graph.get(node, [])
    reached, edges = walk(["A"], neighbors, depth=4)
    assert reached == {"A", "B"}
    assert ("A", "B", "confirmed") in edges
    assert ("B", "A", "inferred") in edges  # back-edge to visited node


def test_walk_respects_depth():
    chain = {"A": ["B"], "B": ["C"], "C": ["D"], "D": ["E"], "E": []}
    neighbors = lambda node, direction: chain.get(node, [])
    reached, _ = walk(["A"], neighbors, depth=2)
    assert reached == {"A", "B", "C"}  # 2 hops: A->B->C


def test_walk_depth_hard_cap():
    chain = {f"n{i}": [f"n{i+1}"] for i in range(20)}
    chain["n20"] = []
    neighbors = lambda node, d: chain.get(node, [])
    reached, _ = walk(["n0"], neighbors, depth=100)
    assert reached == {f"n{i}" for i in range(9)}  # hard cap 8 hops


# ---- find_enclosing_unit (fixture) ----

def test_find_enclosing_unit(fixture_root):
    f = fixture_root / "src/main/java/com/example/service/OrderService.java"
    text = f.read_text().splitlines()
    target = next(i + 1 for i, ln in enumerate(text) if "selectByStoreNo(storeNo)" in ln)
    unit = find_enclosing_unit(f, target)
    assert unit is not None
    assert unit["name"] == "findByStoreNo"
    assert unit["qualname"] == "OrderService.findByStoreNo"


def test_find_enclosing_unit_interface_method(fixture_root):
    f = fixture_root / "src/main/java/com/example/mapper/OrderMapper.java"
    text = f.read_text().splitlines()
    target = next(i + 1 for i, ln in enumerate(text) if "selectByStoreNo" in ln)
    unit = find_enclosing_unit(f, target)
    assert unit is not None and unit["name"] == "selectByStoreNo"


# ---- end-to-end on fixture ----

def test_trace_fixture_chain(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    usages = discover("storeNo", fixture_root, profile)
    g = trace(usages, fixture_root, profile, depth=4)
    labels = {n["label"] for n in g["nodes"]}
    assert "OrderController.queryByStoreNo" in labels
    assert "OrderService.findByStoreNo" in labels
    assert "OrderMapper.selectByStoreNo" in labels

    def has(frm, to):
        return any(e["from"] == frm and e["to"] == to for e in g["edges"])
    assert has("OrderController.queryByStoreNo", "OrderService.findByStoreNo")
    assert has("OrderService.findByStoreNo", "OrderMapper.selectByStoreNo")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_trace.py -v`
Expected: FAIL (`No module named 'trace'`).

- [ ] **Step 3: Write minimal implementation**

`codex-find/src/trace.py`:
```python
"""Phase 2: build the call graph by walking callers (up) and callees (down)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Callable

from common import add_edge, add_node, grep, load_profile, new_graph

HARD_DEPTH_CAP = 8
# A Java method signature: <modifiers/type> name(params) [throws ...] { or ;
_SIG_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(throws\s+[\w.,\s]+)?\s*([{;])\s*$")
_CONTROL = {"if", "for", "while", "switch", "catch", "return", "new", "super", "this"}


# ---- Pure walk: cycle-safe, depth-capped ----
def walk(seeds: list[str], neighbors: Callable[[str, str], list[str]],
         depth: int) -> tuple[set[str], list[tuple[str, str, str]]]:
    depth = min(depth, HARD_DEPTH_CAP)
    visited: set[str] = set(seeds)
    edges: list[tuple[str, str, str]] = []
    frontier = [(s, 0) for s in seeds]
    while frontier:
        node, d = frontier.pop(0)
        if d >= depth:
            continue
        for nb in neighbors(node, "down"):
            if nb == node:
                continue
            if nb in visited:
                edges.append((node, nb, "inferred"))   # back / cross edge
                continue
            edges.append((node, nb, "confirmed"))
            visited.add(nb)
            frontier.append((nb, d + 1))
    return visited, edges


# ---- Java method span detection ----
def _strip_comment(line: str) -> str:
    return line.split("//", 1)[0].rstrip()


def _current_class(lines: list[str], upto: int) -> str | None:
    cls = None
    for i in range(upto):
        m = re.search(r"\b(?:class|interface|enum)\s+(\w+)", lines[i])
        if m:
            cls = m.group(1)
    return cls


def find_enclosing_unit(file: Path, target_line: int) -> dict | None:
    try:
        lines = Path(file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    spans: list[tuple[int, int, str]] = []  # (sig_line, end_line, name)
    i = 0
    while i < len(lines):
        raw = _strip_comment(lines[i])
        m = _SIG_RE.search(raw)
        if m and m.group(1) not in _CONTROL:
            name = m.group(1)
            if m.group(4) == ";":               # interface / abstract method
                spans.append((i + 1, i + 1, name))
            else:                                # '{' — brace match for end
                depth = raw.count("{") - raw.count("}")
                j = i + 1
                while j < len(lines) and depth > 0:
                    seg = _strip_comment(lines[j])
                    depth += seg.count("{") - seg.count("}")
                    j += 1
                spans.append((i + 1, j, name))
        i += 1
    for sig, end, name in spans:
        if sig <= target_line <= end:
            cls = _current_class(lines, sig - 1)
            qual = f"{cls}.{name}" if cls else name
            return {"id": qual, "name": name, "qualname": qual,
                    "file": str(file), "line": sig, "end_line": end}
    return None


def _layer_of_file(file: str, layers: list[dict]) -> str:
    fpath = str(file).replace("\\", "/")
    for L in layers:
        hint = L.get("path_hint")
        if hint and re.search(hint, fpath, re.IGNORECASE):
            return L["name"]
    return "Unknown"


def _callees_in_unit(unit: dict, profile: dict) -> list[str]:
    patterns = profile.get("call_patterns", {})
    regs = []
    if "method_invocation" in patterns:
        regs.append(re.compile(patterns["method_invocation"]))
    if "chain_step" in patterns:
        regs.append(re.compile(patterns["chain_step"]))
    try:
        lines = Path(unit["file"]).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    body = lines[unit["line"] - 1: unit["end_line"]]
    names: list[str] = []
    seen: set[str] = set()
    for ln in body:
        seg = _strip_comment(ln)
        for rx in regs:
            for m in rx.finditer(seg):
                nm = m.group(1)
                if nm in _CONTROL or nm in seen:
                    continue
                seen.add(nm)
                names.append(nm)
    return names


def _resolve_definition(method_name: str, root: Path, exclude: list[str]) -> list[dict]:
    """Find units whose declared method name == method_name (definition lines)."""
    pat = rf"\b{re.escape(method_name)}\s*\("
    hits = grep(pat, root, "*", exclude)
    out: list[dict] = []
    seen: set[str] = set()
    for h in hits:
        u = find_enclosing_unit(Path(h["file"]), h["line"])
        if u and u["name"] == method_name and u["line"] == h["line"]:
            if u["id"] not in seen:
                seen.add(u["id"])
                out.append(u)
    return out


def _callers_of(unit: dict, root: Path, exclude: list[str]) -> list[dict]:
    pat = rf"\b{re.escape(unit['name'])}\s*\("
    hits = grep(pat, root, "*", exclude)
    callers: list[dict] = []
    seen: set[str] = set()
    for h in hits:
        if Path(h["file"]) == Path(unit["file"]) and h["line"] == unit["line"]:
            continue  # the definition itself, not a call
        enc = find_enclosing_unit(Path(h["file"]), h["line"])
        if enc and enc["id"] != unit["id"] and enc["id"] not in seen:
            seen.add(enc["id"])
            callers.append(enc)
    return callers


def trace(usages: list[dict], root: Path, profile: dict, depth: int = 4) -> dict:
    layers = profile.get("layers", [])
    exclude = profile.get("exclude", {}).get("dirs", [])
    g = new_graph({"depth": min(depth, HARD_DEPTH_CAP)})

    seeds: list[dict] = []
    seed_ids: set[str] = set()
    usage_by_unit: dict[str, list[dict]] = {}
    for site in usages:
        u = find_enclosing_unit(Path(site["file"]), site["line"])
        if not u:
            continue
        if u["id"] not in seed_ids:
            seed_ids.add(u["id"])
            seeds.append(u)
            usage_by_unit[u["id"]] = []
        usage_by_unit[u["id"]].append({
            "file": site["file"], "line": site["line"], "col": site.get("col"),
            "occurrence_type": site.get("occurrence_type"), "snippet": site.get("snippet"),
        })

    known: dict[str, dict] = {u["id"]: u for u in seeds}

    def neighbors_down(uid: str, _dir: str) -> list[str]:
        u = known.get(uid)
        if not u:
            return []
        out: list[str] = []
        for name in _callees_in_unit(u, profile):
            for tgt in _resolve_definition(name, root, exclude):
                if tgt["id"] == uid:
                    continue
                if tgt["id"] not in known:
                    known[tgt["id"]] = tgt
                out.append(tgt["id"])
        return out

    def neighbors_up(uid: str, _dir: str) -> list[str]:
        u = known.get(uid)
        if not u:
            return []
        out: list[str] = []
        for c in _callers_of(u, root, exclude):
            if c["id"] not in known:
                known[c["id"]] = c
            out.append(c["id"])
        return out

    seed_list = [u["id"] for u in seeds]
    _, down_edges = walk(seed_list, neighbors_down, depth)
    _, up_edges = walk(seed_list, neighbors_up, depth)

    for uid, u in known.items():
        add_node(g, {
            "id": uid, "kind": "unit", "label": uid,
            "layer": _layer_of_file(u["file"], layers),
            "file": u["file"], "line": u["line"],
            "usages": usage_by_unit.get(uid, []),
        })
    for frm, to, conf in down_edges:
        add_edge(g, frm, to, "call", conf)
    # up_edges: walk emitted (unit -> caller); flip so edge is caller -> callee
    for frm, to, conf in up_edges:
        add_edge(g, to, frm, "call", conf)
    return g


def main() -> None:
    ap = argparse.ArgumentParser(description="codex-find Phase 2: build call graph.")
    ap.add_argument("--usages", required=True, help="path to usages JSON (from discover)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--depth", type=int, default=4)
    args = ap.parse_args()
    profiles_dir = Path(__file__).resolve().parent.parent / "profiles"
    profile = load_profile(args.profile, profiles_dir)
    usages = json.loads(Path(args.usages).read_text(encoding="utf-8"))
    g = trace(usages, Path(args.root), profile, args.depth)
    json.dump(g, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_trace.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add src/trace.py tests/test_trace.py
git commit -m "feat(trace): phase 2 call-graph walk with cycle/depth control"
```

---

### Task 6: tables.py — Phase 3 DB table resolution

**Files:**
- Create: `codex-find/src/tables.py`
- Test: `codex-find/tests/test_tables.py`

**Interfaces:**
- Consumes: graph from `trace`, `common.grep`, profile (`table_sources`).
- Produces:
  - `resolve_tables(graph, root, profile) -> dict` — augments graph with `kind:"table"` nodes + `references` edges; table node: `{id, kind:"table", label, layer:"Table", table, op, source_unit, sql_snippet}`.
  - `main()` CLI: `tables.py --graph PATH --root PATH --profile NAME` → graph JSON on stdout.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_tables.py`:
```python
from common import load_profile
from discover import discover
from trace import trace
from tables import resolve_tables


def test_resolves_t_order_from_mybatis(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    usages = discover("storeNo", fixture_root, profile)
    g = trace(usages, fixture_root, profile, depth=4)
    g = resolve_tables(g, fixture_root, profile)

    table_nodes = [n for n in g["nodes"] if n["kind"] == "table"]
    assert any(n["table"] == "t_order" for n in table_nodes)
    t = next(n for n in table_nodes if n["table"] == "t_order")
    assert t["op"] == "select"
    assert t["layer"] == "Table"
    assert "store_no" in t["sql_snippet"]
    assert any(e["kind"] == "references" and e["to"] == t["id"] for e in g["edges"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_tables.py -v`
Expected: FAIL (`No module named 'tables'`).

- [ ] **Step 3: Write minimal implementation**

`codex-find/src/tables.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_tables.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add src/tables.py tests/test_tables.py
git commit -m "feat(tables): phase 3 mybatis table resolution"
```

---

### Task 7: graph.py — Phase 4 assemble, prune, layout

**Files:**
- Create: `codex-find/src/graph.py`
- Test: `codex-find/tests/test_graph.py`

**Interfaces:**
- Consumes: graph from `tables`.
- Produces:
  - `prune_and_layout(graph, max_nodes=300, layer_order=None) -> dict` — sets `meta.truncated` when over cap; assigns each node `col` + `row`.
  - `main()` CLI: `graph.py --graph PATH --max-nodes 300` → graph JSON on stdout.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_graph.py`:
```python
from common import new_graph, add_node, add_edge
from graph import prune_and_layout


def _big_graph(n):
    g = new_graph({})
    prev = None
    for i in range(n):
        nid = add_node(g, {"kind": "unit", "label": f"u{i}", "layer": "Service"})
        if prev:
            add_edge(g, prev, nid)
        prev = nid
    return g


def test_layout_assigns_col_and_row():
    g = new_graph({})
    a = add_node(g, {"kind": "unit", "label": "A", "layer": "Controller"})
    b = add_node(g, {"kind": "unit", "label": "B", "layer": "Service"})
    c = add_node(g, {"kind": "table", "label": "t", "layer": "Table"})
    add_edge(g, a, b); add_edge(g, b, c)
    prune_and_layout(g, max_nodes=300,
                     layer_order=["Controller", "Service", "Repository", "Table"])
    by_id = {n["id"]: n for n in g["nodes"]}
    assert by_id[a]["col"] == 0 and by_id[a]["row"] == 0
    assert by_id[b]["col"] == 1
    assert by_id[c]["col"] == 3   # Table column


def test_truncation_when_over_cap():
    g = _big_graph(400)
    prune_and_layout(g, max_nodes=300)
    assert len(g["nodes"]) <= 300
    assert g["meta"]["truncated"] is not None
    assert g["meta"]["truncated"]["pruned_count"] >= 100


def test_no_truncation_under_cap():
    g = _big_graph(50)
    prune_and_layout(g, max_nodes=300)
    assert g["meta"].get("truncated") is None
    assert len(g["nodes"]) == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_graph.py -v`
Expected: FAIL (`No module named 'graph'`).

- [ ] **Step 3: Write minimal implementation**

`codex-find/src/graph.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_graph.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add src/graph.py tests/test_graph.py
git commit -m "feat(graph): phase 4 cap enforcement and layered layout"
```

---

### Task 8: render.py + template — Phase 5 HTML/SVG report

**Files:**
- Create: `codex-find/templates/report.html.tmpl`
- Create: `codex-find/src/render.py`
- Test: `codex-find/tests/test_render.py`

**Interfaces:**
- Consumes: final graph (from `graph`), keyword, meta, template path.
- Produces:
  - `render_svg(graph: dict) -> str` — layered left→right SVG fragment.
  - `render(graph, keyword, meta, template_path) -> str` — full single-file HTML string.
  - `main()` CLI: `render.py --graph PATH --keyword K --meta PATH --out report.html`.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_render.py`:
```python
from pathlib import Path

from common import new_graph, add_node, add_edge
from graph import prune_and_layout
from render import render, render_svg, render_panorama_svg

TMPL = Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"


def _fixture_graph():
    g = new_graph({})
    a = add_node(g, {"kind": "unit", "label": "OrderController.queryByStoreNo", "layer": "Controller"})
    b = add_node(g, {"kind": "unit", "label": "OrderService.findByStoreNo", "layer": "Service"})
    c = add_node(g, {"kind": "unit", "label": "OrderMapper.selectByStoreNo", "layer": "Repository"})
    d = add_node(g, {"kind": "table", "label": "t_order", "layer": "Table", "table": "t_order", "op": "select"})
    add_edge(g, a, b); add_edge(g, b, c); add_edge(g, c, d, "references")
    prune_and_layout(g, 300, ["Controller", "Service", "Repository", "Table"])
    return g


def test_svg_contains_nodes_and_edge():
    svg = render_svg(_fixture_graph())
    assert "OrderController.queryByStoreNo" in svg
    assert "t_order" in svg
    assert "<path" in svg  # an edge


def test_render_single_file_html():
    html = render(_fixture_graph(), "storeNo",
                  {"project": "demo", "language": "java-spring"}, TMPL)
    assert html.startswith("<!DOCTYPE html>")
    assert "storeNo" in html and "t_order" in html
    assert "http://" not in html and "https://" not in html  # offline single file
    assert "<svg" in html


def test_panorama_present_and_renderable():
    g = _fixture_graph()
    svg = render_panorama_svg(g)
    assert "<circle" in svg and "t_order" in svg
    html = render(g, "storeNo", {"project": "demo", "language": "java-spring"}, TMPL)
    assert "<details" in html and "网络全景" in html


def test_template_file_exists():
    assert TMPL.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_render.py -v`
Expected: FAIL (`No module named 'render'`).

- [ ] **Step 3: Write minimal implementation**

`codex-find/templates/report.html.tmpl`:
```html
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>codex-find · {{KEYWORD}}</title>
<style>
  body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;color:#0f172a}
  header{background:#1e293b;color:#fff;padding:12px 18px;font-size:14px}
  header b{font-size:16px}
  section{padding:14px 18px;border-top:1px solid #e2e8f0}
  .label{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#64748b}
  table{border-collapse:collapse;width:100%;font-size:13px;margin-top:6px}
  th,td{border:1px solid #e2e8f0;padding:5px 8px;text-align:left;vertical-align:top}
  th{background:#f1f5f9}
  code{background:#f1f5f9;padding:1px 4px;border-radius:3px}
  .notes{font-size:12px;color:#475569}
  .node-Controller{fill:#e8f0fe;stroke:#3b82f6}
  .node-Service{fill:#fef3c7;stroke:#d97706}
  .node-Repository{fill:#dcfce7;stroke:#16a34a}
  .node-Table{fill:#f3e8ff;stroke:#9333ea}
  text{font:11px sans-serif}
</style>
</head>
<body>
<header>
  <b>{{KEYWORD}}</b> · {{PROJECT}} · {{LANGUAGE}} · {{GENERATED_AT}} ·
  usages {{USAGES}} / tables {{TABLES}} / depth {{DEPTH}}
</header>
<section>
  <div class="label">调用链 (主图 · 分层左→右)</div>
  {{SVG}}
</section>
<section>
  <details>
    <summary>显示网络全景 (径向)</summary>
    {{PANORAMA_SVG}}
  </details>
</section>
<section>
  <div class="label">涉及表</div>
  {{TABLES_HTML}}
</section>
<section>
  <div class="label">使用位置</div>
  {{USAGES_HTML}}
</section>
<section class="notes">{{NOTES}}</section>
</body>
</html>
```

`codex-find/src/render.py`:
```python
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
    """Layered left→right SVG: nodes positioned by (col, row); bezier edges."""
    nodes = graph.get("nodes", [])
    if not nodes:
        return '<svg width="200" height="40"><text x="8" y="24">no nodes</text></svg>'
    ncol = max(n.get("col", 0) for n in nodes) + 1
    nrow = max(n.get("row", 0) for n in nodes) + 1
    width = max(320, ncol * COL_W + PAD)
    height = max(60, nrow * ROW_H + PAD)
    pos = {n["id"]: (PAD + n.get("col", 0) * COL_W, PAD + n.get("row", 0) * ROW_H)
           for n in nodes}
    parts = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
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
    parts = [f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">']
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
    ap = argparse.ArgumentParser(description="codex-find Phase 5: render report.")
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_render.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add src/render.py templates/report.html.tmpl tests/test_render.py
git commit -m "feat(render): phase 5 single-file HTML + layered SVG report"
```

---

### Task 9: codex-find subagent definition

**Files:**
- Create: `codex-find/.claude/agents/codex-find.md`
- Test: `codex-find/tests/test_agent_def.py`

**Interfaces:**
- Consumes: the 5 phase scripts (their `main()` CLIs).
- Produces: a Claude Code subagent named `codex-find` that runs the pipeline end-to-end and writes a report.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_agent_def.py`:
```python
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent / ".claude" / "agents" / "codex-find.md"


def test_agent_file_exists():
    assert AGENT.exists()


def test_agent_mentions_each_phase_and_tools():
    text = AGENT.read_text(encoding="utf-8")
    for needle in ["discover.py", "trace.py", "tables.py", "graph.py", "render.py",
                   "storeNo", "report.html", "Bash", "Read", "Grep"]:
        assert needle in text, f"agent def missing: {needle}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_agent_def.py -v`
Expected: FAIL (file missing).

- [ ] **Step 3: Write minimal implementation**

`codex-find/.claude/agents/codex-find.md`:
```markdown
---
name: codex-find
description: Trace a keyword's full usage across a Java/Spring codebase — usage sites, call chain, and involved DB tables — and emit a single self-contained HTML/SVG report. Use when the user asks to analyze how a field/identifier (e.g. storeNo) flows through a project.
tools: Bash, Read, Grep, Glob, Write, Edit
---

You are the codex-find analyzer. Given a **keyword** and a **project root**, produce a single offline HTML report showing the keyword's complete footprint.

# Inputs
- `keyword` (required, e.g. `storeNo`)
- `project root` (required, absolute path)
- `language` (optional; auto-detected — defaults to `java-spring`)
- `depth` (optional; default 4)
- `output` (optional; default `output/<keyword>-report.html`)

# Pipeline — run these helper scripts in order from the codex-find repo root
1. **Discover** (Phase 1):
   `python src/discover.py --keyword "<keyword>" --root "<target>" --profile java-spring > /tmp/cf-usages.json`
2. **Trace** (Phase 2):
   `python src/trace.py --usages /tmp/cf-usages.json --root "<target>" --profile java-spring --depth 4 > /tmp/cf-graph.json`
3. **Tables** (Phase 3):
   `python src/tables.py --graph /tmp/cf-graph.json --root "<target>" --profile java-spring > /tmp/cf-graph2.json`
4. **Assemble** (Phase 4):
   `python src/graph.py --graph /tmp/cf-graph2.json --max-nodes 300 > /tmp/cf-graph3.json`
5. **Render** (Phase 5):
   Write `/tmp/cf-meta.json` = `{"project":"<target basename>","language":"java-spring","generated_at":"<ISO datetime>"}`, then
   `python src/render.py --graph /tmp/cf-graph3.json --keyword "<keyword>" --meta /tmp/cf-meta.json --out "<output>"`

# Semantic judgment (your job, not the scripts')
- If `discover` returns zero hits, still write a "no matches" report listing searched variants.
- If a symbol name is ambiguous (many classes define it), note the ambiguity in the report notes; do not collapse unrelated units.
- If a phase fails, emit a report from whatever succeeded and record which phase failed in the notes.

# Rules
- Always emit a report file (never leave the user with nothing).
- The report must be a single offline HTML file with no external (`http`) assets.
- Report inferred (LLM-judged) edges distinctly from confirmed (grep-found) edges.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_agent_def.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add .claude/agents/codex-find.md tests/test_agent_def.py
git commit -m "feat(agent): codex-find subagent definition"
```

---

### Task 10: End-to-end pipeline test

**Files:**
- Test: `codex-find/tests/test_e2e.py`

**Interfaces:**
- Consumes: every module (`discover`, `trace`, `tables`, `graph`, `render`) and the template.
- Produces: confidence that the full pipeline produces a correct report on the fixture.

- [ ] **Step 1: Write the failing test**

`codex-find/tests/test_e2e.py`:
```python
from pathlib import Path

from common import load_profile, new_graph
from discover import discover
from trace import trace
from tables import resolve_tables
from graph import prune_and_layout
from render import render

TMPL = Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"


def test_full_pipeline_on_fixture(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    usages = discover("storeNo", fixture_root, profile)
    assert usages, "expected usage sites in fixture"

    g = trace(usages, fixture_root, profile, depth=4)
    g = resolve_tables(g, fixture_root, profile)
    g = prune_and_layout(g, max_nodes=300,
                         layer_order=["Controller", "Service", "Repository", "Table"])

    html = render(g, "storeNo",
                  {"project": "fixture", "language": "java-spring",
                   "generated_at": "2026-07-03T12:00:00"}, TMPL)

    assert "<svg" in html
    assert "storeNo" in html
    assert "t_order" in html
    for unit in ["OrderController.queryByStoreNo",
                 "OrderService.findByStoreNo",
                 "OrderMapper.selectByStoreNo"]:
        assert unit in html
    assert "http://" not in html and "https://" not in html  # offline single file


def test_zero_hit_still_renders(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    usages = discover("___no_such_keyword___", fixture_root, profile)
    assert usages == []
    g = new_graph({"depth": 4})
    prune_and_layout(g, 300, ["Controller", "Service", "Repository", "Table"])
    html = render(g, "___no_such_keyword___",
                  {"project": "fixture", "language": "java-spring",
                   "generated_at": "2026-07-03T12:00:00"}, TMPL)
    assert "<svg" in html and "无涉及表" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_e2e.py -v`
Expected: FAIL only if a prior phase is broken (Tasks 4–8 implement everything this exercises).

- [ ] **Step 3: No new implementation — fix the offending module if needed**

If it fails, fix the module that broke (do not weaken the assertions). Run focused first:

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest tests/test_e2e.py::test_full_pipeline_on_fixture -v`

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `cd /Users/sunyawei/mywork/github/codex-find && python -m pytest -v`
Expected: all tests pass (scaffold + common + profile + discover + trace + tables + graph + render + agent + e2e).

- [ ] **Step 5: Commit**

```bash
cd /Users/sunyawei/mywork/github/codex-find
git add tests/test_e2e.py
git commit -m "test(e2e): full pipeline on java-spring fixture + zero-hit case"
```

---

## Completion Check

After Task 10, verify the CLI works end-to-end from the shell (smoke test):

```bash
cd /Users/sunyawei/mywork/github/codex-find
python src/discover.py --keyword storeNo --root tests/fixtures/java-spring --profile java-spring > /tmp/cf-usages.json
python src/trace.py --usages /tmp/cf-usages.json --root tests/fixtures/java-spring --profile java-spring --depth 4 > /tmp/cf-graph.json
python src/tables.py --graph /tmp/cf-graph.json --root tests/fixtures/java-spring --profile java-spring > /tmp/cf-graph2.json
python src/graph.py --graph /tmp/cf-graph2.json --max-nodes 300 > /tmp/cf-graph3.json
printf '{"project":"fixture","language":"java-spring","generated_at":"2026-07-03T12:00:00"}' > /tmp/cf-meta.json
python src/render.py --graph /tmp/cf-graph3.json --keyword storeNo --meta /tmp/cf-meta.json --out output/storeNo-report.html
open output/storeNo-report.html   # visually confirm layered diagram + t_order
```

Expected: `output/storeNo-report.html` opens showing the Controller → Service → Mapper → `t_order` layered chain.
```
