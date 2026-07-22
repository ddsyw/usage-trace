# P1 设计：tree-sitter 引擎 + 项目索引

**日期：** 2026-07-16
**状态：** 已确认，待实现
**所属路线图：** usage-trace 四阶段升级（P1 引擎 ✅ → P2 UA 风格报告 ✅ → P3 三端打包 ✅ → P4 多语言）

## 背景

usage-trace 是一个把关键词在 Java/Spring 工程中的「使用位置 → 调用链 → 涉及表」串成单文件离线
HTML 报告的 CLI。当前实现（`src/discover.py` → `trace.py` → `tables.py` → `graph.py` → `render.py`）
基于正则与花括号计数，存在三类问题：

1. **性能**：`trace.py` 在 BFS 展开时对每个被调用方法都全树 `grep`（`_resolve_definition`、
   `_callers_of`），同一文件被反复 `read_text`，BFS 用 `list.pop(0)`（O(n²)）。大工程上从秒级劣化到分钟级。
2. **正确性**：方法体边界靠数 `{}`，不识别字符串字面量和块注释（`"}"` 或 `/* } */` 会让深度错位），
   导致方法 end_line / callees / 表解析连锁出错。
3. **架构**：每次查询都全量重扫整个工程，无 scan-once / query-many 能力。

用户已确认：底层解析改用 **tree-sitter**（与 Understand-Anything 的 tree-sitter + LLM 混合架构对齐），
展示层走「重塑离线报告」，三端做 UA 完整打包，最后支持 C#/Python。索引采用文件级 mtime+hash 增量失效。

选 tree-sitter 后，原计划的「性能 / 正确性 / 持久化索引」三件事合并为一个 P1：一次建好 tree-sitter
索引，三件事同时交付；避免先优化正则引擎再推倒重来。

## 目标

- 用 tree-sitter 精确解析 Java 源码（方法 span、字段、调用、继承），消除花括号计数的精度问题。
- 建立 `ProjectIndex`：扫描一次 root，产出符号表 / 调用表 / 字段类型表 / 反向调用索引，并落盘增量复用。
- `trace` 走索引字典查询 + `deque` BFS，移除 walk 内的 per-callee grep，消除主要性能瓶颈。
- 保持 CLI、入口、5 个调试子命令、报告输出全部可用且向后兼容。
- 为 P4 多语言（C#/Python）预留语言注册表接口。

## 非目标（P1 不做）

- 不重塑 HTML 报告（P2）。
- 不新增 C#/Python 解析器（P4）。
- 不新增 dashboard serve 模式（展示方案已定为离线报告）。
- 不动三端打包（P3）。
- 不保留「无 tree-sitter 的正则降级引擎」——tree-sitter 成为分析期硬依赖，避免双引擎维护成本。

## 架构

### 模块布局

```
src/
  index.py          # 新增：ProjectIndex（扫描 / 持久化 / 加载 / 增量失效）
  parsing.py        # 新增：tree-sitter 适配层 + 语言注册表（P1 实现 Java）
  discover.py       # 改：在 index 的文件集上搜关键词，不再全树 grep
  trace.py          # 改：走索引查询 + deque BFS；删除死代码 walk()
  tables.py         # 改：文件/spans 来自 index，SQL 抽取仍走正则
  graph.py          # 不变
  render.py         # 不变（P2 再重塑）
  understand_rules  # 不变
  common.py         # 保留 grep 作为工具/fallback，不再用于 walk
```

### 数据流

```
run(keyword, root, ...):
  index  = ProjectIndex.load_or_build(root, profile)    # 唯一扫描入口
  usages = discover(keyword, profile, variants, index)  # 在 index 文件集上搜关键词
  graph  = trace(usages, index, profile, depth)         # 走索引，不再 grep
  graph  = resolve_tables(graph, index, profile)        # SQL 抽取仍正则，文件/spans 来自 index
  graph  = prune_and_layout(graph, ...)
  render(graph, ...)
```

## 组件设计

### `ProjectIndex`（`src/index.py`）

扫描一次 root，产出内存索引并落盘：

```python
files:           {path: FileEntry(mtime, size, hash, lang)}
methods:         {qual "Cls.method": Method(name, file, start_line, end_line, params, cls)}
methods_by_name: {simple_name: [qual]}        # 被调用方解析
fields:          {cls: {field: type}}          # receiver→类型，替代 _symbol_types
inheritance:     {cls: {supertypes}}           # P1 记录，调用解析可选增强
calls:           [Call(caller_qual, callee_name, receiver, file, line)]
calls_by_callee: {callee_name: [Call]}         # 反向索引，替代 _callers_of 的 grep
layers:          {file: layer}                 # 一次性算好
```

关键方法：

- `ProjectIndex.load_or_build(root, profile)`：入口。有缓存则增量加载，否则全量构建并落盘。
- `build(root, profile)`：遍历源文件（尊重 profile.exclude.dirs），按扩展名选语言解析器，
  填充上述各表；layer 用现有 `classify_layer` 一次性算好缓存。
- `enclosing_method(file, line) -> Method | None`：用 `methods` 的精确 span 定位（取代
  `find_enclosing_unit` 的花括号计数）。
- `resolve_callees(qual) -> list[str]`、`resolve_callers(qual) -> list[str]`：供 trace 使用。

### tree-sitter 适配层（`src/parsing.py`）

语言注册表：`LANGUAGES = {".java": JavaParser}`，P4 追加 `".cs": CSharpParser, ".py": PythonParser`。
每个解析器实现统一接口：

```python
class LanguageParser:
    def parse(self, text: str) -> FileSymbols: ...
```

`FileSymbols` 包含：方法（name, qual, start_line, end_line, params, cls）、字段（cls, name, type）、
继承（cls, supertypes）、调用（caller_qual, callee_name, receiver, file, line）。

P1 的 Java 解析用 tree-sitter-java AST 节点替换现有正则：

| 现有正则做法 | tree-sitter 节点 |
|---|---|
| `find_enclosing_unit`（数 `{}`） | `method_declaration` 的精确 start/end 行 |
| `_callee_refs_in_unit`（正则） | 方法 span 内的 `method_invocation`（name + receiver + line） |
| `_symbol_types`（字段类型正则） | `field_declaration`（name + type，按 class 归属） |
| `_resolve_definition`（grep） | `methods_by_name` 字典查询 |
| `_callers_of`（grep） | `calls_by_callee` 反向索引查询 |

tree-sitter 绑定面向 `tree-sitter>=0.25` + `tree-sitter-java`；具体 query / Parser API
在实现时按当前稳定版钉死（0.25 起 query 构造方式有调整，以实际可用的 API 为准）。

### 调用解析与遍历（`trace.py` 改造）

- 种子：usage site (file, line) → `index.enclosing_method` 精确定位（修复 #6）。
- 向下：`index.calls` 中 `caller_qual` 匹配 → 每个 `callee_name` 经 `methods_by_name` + receiver
  类型（查 `fields`）+ 同类兜底解析到目标 qual；保留现有 `_matches_target_call` 启发式**语义**，
  只把输入从「正则 grep 出的」换成「索引查出的」。
- 向上：`index.calls_by_callee` 反查。
- BFS 全部改用 `collections.deque`（修复 #3）。
- 删除从未被调用的死代码 `walk()`（`trace.py:21-40`）。

### 缓存与增量失效（`.usage-trace/index/`）

```
.usage-trace/index/
  manifest.json          # {root_hash, version, files: {path: {mtime, size, hash}}}
  symbols/<hash>.json    # 每个文件内容 hash 对应的解析结果（未变文件直接复用）
```

- 加载：读 `manifest.json` → 对每个文件先比 `mtime+size`（快路径），再比内容 `hash`（确认）→
  命中则复用对应 `symbols/<hash>.json`，未命中才重解析**该文件**。
- 删除文件 → 丢弃其条目；新增文件 → 加入。
- `root_hash` 变（换工程）→ 整体重建。
- `version` 字段用于索引格式不兼容时整体失效。

### `tables.py` 改造（控制范围）

- 文件来源从 `Path(root).rglob("*.java")` 改为遍历 `index.files`（自动尊重 exclude，不再重扫、不再读 target/build）。
- 方法 spans 改用 `index.methods` 精确值（`_parse_java_sql_literals` 的 body 区间更准）。
- SQL / 表抽取（MyBatis XML、MyBatis 注解、JPA、raw SQL、Java SQL 字符串）**仍走正则**——
  tree-sitter 对这些字符串/XML 语义无帮助，正则反而合适（与 UA「tree-sitter 管代码、LLM/正则管语义」分工同理）。
- 顺带修 `unicode_escape` 解码陷阱（`tables.py:160/264`）：改用不会损坏非 ASCII 字节的安全反转义。

### `discover.py` 改造

- 关键词变体扩展（`keyword_variants`）、`_occurrence_type`、`_code_portion` 注释剥离逻辑保留。
- 搜索对象从「全树 `grep`」改为遍历 `index.files` 的源文件（文本已在索引阶段读入或在此按需读取一次），
  逐行匹配关键词正则。消除子进程 grep 与重复扫描。

## 依赖与兼容

- `pyproject.toml` 新增运行期依赖：`tree-sitter>=0.25`、`tree-sitter-java`（均有预编译 wheel，无需本地编译）。
- tree-sitter 是**分析期硬依赖**，不进报告；报告仍是单文件离线 HTML，无外部资源（约束不变）。
- CLI 参数、`usage-trace` / `codex-find` 入口、5 个 phase 调试子命令全部保持可用。
- 调试子命令（`python -m discover` 等）内部按需构建临时 index，保持可独立运行。

## 测试策略

- **保持绿**：`tests/test_discover.py`、`test_trace.py`、`test_tables.py` 现有断言兼容；
  行为精度提升处（更准的 callees / spans）有意更新断言并注释原因。
- **新增 `tests/test_index.py`**：fixture 解析符号 / 调用正确；缓存 save→load round-trip；
  改一个文件只重解析该文件（通过 manifest 哈希变化验证）。
- **新增 `tests/test_parsing.py`**：针对 #6 的反例——方法体含 `"}"` 字符串、嵌套块注释——
  验证 span 精确（正则必错的用例）。
- **fixture 扩展**：`tests/fixtures/java-spring` 增加一个「字符串花括号 + 块注释」边界文件。
- **回归门**：`pytest` / `ruff check .` / `compileall -q src tests` / `git diff --check` 保持不变。

## 验收标准

1. 全套 `pytest` 通过，`ruff` / `compileall` / `git diff --check` 干净。
2. `tests/test_parsing.py` 中字符串花括号 / 块注释用例通过（证明 #6 已修）。
3. `trace.py` 的 walk 路径内不再有 `grep(` 调用（per-callee 全树 grep 已消除）；BFS 用 `deque`。
4. 二次运行复用索引：仅改动单文件时，`manifest.json` 显示只有该文件重解析。
5. 现有 CLI 冒烟测试输出一致：`usage-trace --keyword storeNo --root tests/fixtures/java-spring` 仍生成报告。
6. 死代码 `walk()` 已删除。

## 风险

- **tree-sitter Python API 版本差异**：0.25 起 `Language` / `Query` 构造方式有变化，实现时以实际
  安装版本的稳定 API 为准，必要时钉死小版本。缓解：`pyproject.toml` 写下限 + 实现时验证。
- **tree-sitter-java wheel 可用性**：主流平台（macOS/Linux x64+arm、Windows）有 wheel；冷门平台可能需源码编译。
  缓解：文档注明平台要求。
- **索引格式演进**：加 `version` 字段整体失效，避免半新半旧缓存。
- **行为微调引发测试断言失败**：精度提升会让部分旧断言不再成立，按「有意更新 + 注释」处理，不视为回归。

## 后续阶段（仅作上下文）

- **P2**：离线 HTML 报告重塑为 UA dashboard 视觉与交互语言（节点详情侧栏、guided tour、模糊搜索、
  complexity/tags、persona 分级、层可视化）。
- **P3**：`.cursor-plugin` / `.claude` / `.codex-plugin` manifest + 统一 `install.sh`(symlink) + 可选 post-commit hook。
- **P4**：接入 `tree-sitter-c-sharp` / `tree-sitter-python`；C# EF(Core)、Python SQLAlchemy 的表解析。
