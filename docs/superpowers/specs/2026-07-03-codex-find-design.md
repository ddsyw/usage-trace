# codex-find — Design Spec

**Date:** 2026-07-03
**Status:** Draft (pending user review)
**Owner:** sunyawei

---

## 1. Problem

Given a keyword (e.g. a field name `storeNo`), it is hard to quickly see its **complete footprint** across a codebase: where it is read/written, the **call chain** that reaches those uses, and which **database tables** are ultimately touched. Manual `grep` + reading is slow and misses transitive links.

## 2. Goals

- Input: a **keyword** + **project root** (+ optional flags).
- Output: a **single self-contained offline HTML report** with an embedded **SVG call-chain diagram** + supporting tables, giving the keyword's full usage picture.
- Trace: usage sites → call chain (callers up + callees down) → involved DB tables.
- **Cross-language by design**: ship **Java/Spring** in v1, with a profile mechanism so adding a language = adding one file.
- Runs as a **Claude Code subagent** (LLM orchestrates semantics; Python helpers do deterministic work).

## 3. Non-Goals (v1)

- Runtime/dynamic analysis (no execution, no profiler).
- IDE integration / LSP server.
- Full type-resolution / perfect overload resolution.
- Graphviz/Mermaid rendering (future extension point only).
- Languages beyond Java/Spring at launch (architecture allows, profiles added later).

## 4. Architecture — Agent / Script Split

- **Python helper scripts** do deterministic, reproducible heavy lifting: bulk grep, parsing, graph building, SVG/HTML rendering. Fast, testable.
- **LLM subagent** orchestrates the pipeline and handles what scripts cannot: semantic classification, disambiguation, table inference, ambiguity resolution, and graceful handling of edge cases.

The subagent definition lives at `.claude/agents/codex-find.md`; its system prompt describes the workflow below and the per-script CLI contracts (§10). Tool allowlist: `Bash, Read, Grep, Glob, Write, Edit`.

## 5. Pipeline

```
inputs: keyword, project root, lang?, depth?, out?
   │
Phase 0  Resolve     auto-detect language; expand keyword variants (camelCase / snake_case / kebab / table-name forms)
   │
Phase 1  Discover    grep keyword+variants project-wide (respect profile.exclude);
│                    collect usage sites
   │
Phase 2  Trace       classify each site's unit + layer (profile-driven);
│                    walk callers (up) + callees (down) up to `depth` hops → directed graph
   │
Phase 3  Tables      resolve DB tables touched along the chain (MyBatis XML / JPA @Table / raw SQL per profile);
│                    infer CRUD op where possible
   │
Phase 4  Assemble    merge usage + graph + tables; enforce caps; detect cycles; compute layout hints
   │
Phase 5  Render      emit single report.html with embedded SVG + tables
```

**Data passed between phases is always JSON** (graph model, §7), written to stdout by each script. The agent reads/transforms it.

## 6. Phase Contracts

**Phase 0 — Resolve** (agent, no script)
- Auto-detect language via marker files: `pom.xml`|`build.gradle`→java-spring, `package.json`→node, `requirements.txt`|`pyproject.toml`→python, `go.mod`→go.
- Expand keyword to variant set, e.g. `storeNo` → `{storeNo, store_no, StoreNo, STORE_NO, store-no, storeNos, store_no_list}`.

**Phase 1 — Discover** (`discover.py`)
- Input: `--keyword`, `--variants`, `--root`, `--profile`.
- Excludes per profile (`target, node_modules, .git, dist, build, .idea` for java-spring).
- Output JSON array:
  ```json
  [{ "file": ".../OrderService.java", "line": 88, "col": 12,
     "occurrence_type": "identifier|string|annotation|param|definition",
     "layer": "Service", "snippet": "..." }]
  ```
- Engine: `rg` when available, else Python `glob`+`re` fallback.

**Phase 2 — Trace** (`trace.py`)
- Input: usages JSON, `--root`, `--profile`, `--depth` (default 4, hard-capped at 8 by the script).
- For each usage site → classify containing unit (method) + layer (profile `layers`). Then:
  - **Callers (up)**: grep for invocations of this unit across the project; resolve by symbol + signature/file heuristics.
  - **Callees (down)**: read the unit body; extract calls via profile `call_patterns`.
  - Walk transitively to `depth` hops each direction; track `visited` to break cycles.
- Output: graph JSON (§7), with `edge.confidence` ∈ `confirmed|inferred`.

**Phase 3 — Tables** (`tables.py`)
- Input: graph JSON, `--root`, `--profile`.
- Sources per profile (`table_sources`):
  - **MyBatis**: parse mapper XML glob; map `<mapper namespace>` → interface; attribute `<select|insert|update|delete>` SQL to mapper methods; extract table names from SQL.
  - **JPA**: `@Entity` classes; `@Table(name=…)`; repositories referenced by traced services.
  - **Raw SQL**: `*.sql` files + SQL string literals referencing the keyword or called units.
- Output: graph augmented with `kind=table` nodes + `references` edges; each table node carries `{table, op (select|insert|update|delete|unknown), source_unit, sql_snippet}`.

**Phase 4 — Assemble + Prune** (`graph.py`)
- Input: graph JSON, `--max-nodes` (default 300).
- Merge usage sites, call graph, table nodes into one graph.
- If `max_nodes` exceeded: collapse deep subtrees, keep layer representatives, record `truncated` metadata `{pruned_count, reason}`.
- Detect cycles → mark back-edges.
- Compute layout hints: `layer` → column index (left→right rank); within-column vertical order.

**Phase 5 — Render** (`render.py`)
- Input: final graph JSON, `--keyword`, meta (project, language, timestamp, counts), `--out`.
- Emits **single `report.html`** (layout §9). Hand-written SVG, no external assets, fully offline.

## 7. Graph Model (single source of truth)

```json
{
  "meta": { "keyword": "storeNo", "project": "...", "language": "java-spring",
            "generated_at": "2026-07-03T12:00:00", "depth": 4,
            "counts": { "usages": 12, "tables": 3, "nodes": 27, "edges": 31 },
            "truncated": null },
  "nodes": [
    { "id": "n1", "kind": "unit|table|usage", "label": "OrderService.findByStoreNo",
      "layer": "Service", "file": "...", "line": 88,
      "table": "t_order", "op": "select",           // table nodes only
      "occurrence_type": "...", "snippet": "..." }   // usage nodes only
  ],
  "edges": [
    { "from": "n3", "to": "n1", "kind": "call|references", "confidence": "confirmed|inferred" }
  ]
}
```

`layer` ordering (Controller → Service → Repository → Table) defines the diagram's left→right ranks.

## 8. Language Profile Format

Declarative YAML; five sections, each consumed by a phase. Adding a language = adding one file.

```yaml
# profiles/java-spring.yml
profile: java-spring
detect:
  files: [pom.xml, build.gradle]
layers:                                   # ordered = diagram ranks (left→right)
  - { name: Controller,  match: "@RestController|@Controller", path_hint: "controller" }
  - { name: Service,     match: "@Service",                    path_hint: "service" }
  - { name: Repository,  match: "@Repository|@Mapper",         path_hint: "(mapper|repository|dao)" }
table_sources:
  jpa:    { entity_annotation: "@Entity", table_annotation: '@Table\s*\(\s*name\s*=\s*"([^"]+)"' }
  mybatis:{ mapper_xml_glob: "**/mapper/**/*.xml", namespace_to_interface: true }
  raw_sql: ["**/*.sql"]
call_patterns:
  method_invocation: '\b([A-Za-z_][\w]*)\s*\('
  chain_step:        '\.\s*([A-Za-z_]\w*)\s*\('
exclude:
  dirs: [target, node_modules, .git, dist, build, .idea]
```

**Profile missing / language undetected →** fall back to generic grep-based tracing (no layer classification; flat graph), noted in report.

## 9. Output — HTML Report

**Decisions (approved):**
- **Main diagram**: layered **left→right** (Controller → Service → Mapper → Table columns).
- **Secondary diagram**: **network panorama**, default **collapsed**, deterministic **radial layout** (rings by layer) for v1.
- **Page layout**: **single-column vertical scroll**.
- **Rendering engine**: **hand-written SVG** (emitted by `render.py`); zero runtime deps; single offline file.

**Page sections (top → bottom):**
1. **Header bar** — keyword · project · language · generated_at · counts (usages / tables / depth).
2. **Call-chain main diagram (SVG)** — layered LR; node color by layer (Controller blue / Service amber / Repository green / Table purple); table nodes styled distinctly; multi-caller fan-in collapsed into a `+N callers` badge; edges arrowed, dashed for `inferred`.
3. **Panorama toggle** — `▸ 显示网络全景` expands the radial network SVG below the main diagram.
4. **Usage sites table** — file:line · layer · occurrence_type · snippet (collapsible rows).
5. **Involved tables** — table · CRUD op · touching unit · SQL snippet.
6. **Notes / caveats** — truncation, inferred edges, unresolved dynamic calls, profile fallbacks.

**Always emits a report**, even on partial failure (§11).

## 10. Project Structure

```
codex-find/
├─ .claude/agents/codex-find.md     # subagent: system prompt + workflow + tool allowlist
├─ profiles/java-spring.yml         # v1 profile (+ node/python/go later)
├─ src/
│  ├─ discover.py  trace.py  tables.py  graph.py  render.py
│  └─ common.py                     # shared: graph schema IO, profile loader, grep wrapper
├─ templates/report.html.tmpl
├─ tests/
│  ├─ fixtures/java-spring/         # synthetic Spring project, known chain
│  └─ test_discover.py test_trace.py test_tables.py test_graph.py test_render.py test_profile_java.py test_e2e.py
└─ output/                          # generated reports (gitignored)
```

**Script CLI contracts** (invoked by the agent via Bash):
```
discover.py --keyword K --variants v1,v2 --root PATH --profile P          → usages JSON (stdout)
trace.py    --usages JSON  --root PATH --profile P --depth N              → graph JSON (stdout)
tables.py   --graph JSON   --root PATH --profile P                        → graph JSON (stdout, annotated)
graph.py    --graph JSON   --max-nodes 300                                → graph JSON (stdout, pruned + layout)
render.py   --graph JSON   --keyword K --meta JSON --out report.html      → writes report.html
```

## 11. Error Handling, Caps, Edge Cases

**Caps (explosion control):**
- `depth`: default **4**, hard cap **8**.
- `max_nodes`: **300**; beyond → collapse deep subtrees, set `meta.truncated`.
- Usage hits shown: **500**; beyond → cluster/sample, note total.
- Per-phase timeout → emit partial results + note.

**Edge cases:**
| Case | Handling |
|---|---|
| Zero hits | "No matches" report; list searched variants + scanned dirs. |
| Ambiguous same-name (`find` in 20 classes) | Group by containing class/file; mark ambiguity; never merge unrelated edges. |
| Cycle (A→B→A) | `visited`-set detection; back-edge rendered distinctly; no infinite walk. |
| Reflection / AOP / dynamic calls | Static-unresolvable → `inferred` "unresolved dynamic" node; agent notes likely links. |
| Missing profile / undetected language | Generic grep tracing (no layers); noted in report; still produces graph. |
| MyBatis dynamic SQL / `@Insert` annotations | Both XML-namespace and annotation-SQL supported; unresolvable → "table unknown". |
| Large monorepo | Scope to `--root`; honor `exclude`; optional `--module` filter. |
| Binary / generated files | Skip. Encoding errors → utf-8 `errors=replace`. |

**Failure semantics (invariants):**
- **Always emit a report** — on any phase failure, output what succeeded + which phase failed; never a blank screen.
- **Confidence labeling** — every edge is `confirmed` (direct grep) or `inferred` (LLM); visually distinct in the diagram.
- **Tool degradation** — `rg` absent → Python `glob`+`re` fallback.

## 12. Testing Strategy

**Fixture:** `tests/fixtures/java-spring/` — tiny synthetic Spring project with known chain:
```
OrderController.queryByStoreNo
  → OrderService.findByStoreNo
    → OrderMapper.selectByStoreNo  →  t_order.store_no  (MyBatis XML)
```
Plus 2 extra callers (ambiguous-name case) + 1 cycle (A→B→A). Keyword: `storeNo`.

**Per-phase unit tests** (pytest, no network, no `dot`):
- `test_discover` — exact expected sites (file/line/occurrence_type); build dirs excluded; no false positives.
- `test_trace` — expected nodes/edges; caller + callee directions; cycle detected; depth cap prunes hop N+1.
- `test_tables` — MyBatis XML + namespace→interface resolves `t_order`; JPA `@Table` resolves; `<select>` → SELECT.
- `test_graph` — assemble + prune; injecting >300 nodes sets `truncated`; layer assignment correct.
- `test_render` — HTML parses; SVG contains expected node labels + edges; single file (no external assets); all sections present; truncation note when cap hit. Structural assertions, not full-HTML diff.

**Profile test:** `test_profile_java` — java-spring profile matches annotations + table sources on fixture.

**End-to-end:** `test_e2e` — subagent runs fixture `storeNo` → `report.html` exists, contains `t_order`, contains 3-layer chain, no crash; plus zero-hit / ambiguous / cycle variants.

## 13. Future / Extension Points

- Additional profiles: `node-express`, `python-sqlalchemy`, `python-django`, `go`.
- Optional Graphviz backend: if `dot` is detected, auto-switch for richer auto-layout (v2).
- Cross-repo tracing (`--root` accepts multiple paths / a workspace file).
- Interactive node click → highlight reachable subgraph (enhancement to the static report).

## 14. Open Questions

None blocking v1. (Defaults captured above: depth 4, max-nodes 300, Java-first, hand-written SVG.)
