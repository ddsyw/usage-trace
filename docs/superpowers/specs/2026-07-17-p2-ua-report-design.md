# P2 设计：UA 风格离线报告

**日期：** 2026-07-17
**状态：** 已确认，待实现
**所属路线图：** usage-trace 四阶段升级（P1 引擎 ✅ → P2 UA 风格报告 ✅ → P3 三端打包 ✅ → **P4 多语言** ✅ ✅）

## 背景

P1 交付了 tree-sitter 引擎 + `ProjectIndex`。当前报告是一个功能完整的三栏离线 HTML
（左：主路径/导览/搜索/层级/Top/层间关系；中：SVG 图 + 工具栏；右：节点详情/全景/表/SQL/使用位置），
但视觉偏朴素，且缺少 Understand-Anything dashboard 的招牌交互：富 NodeInfo 详情面板、persona 自适应、
模糊搜索、主题切换、层级图例。UA 的 dashboard 是 React/ReactFlow SPA（NodeInfo、PersonaSelector、
LayerLegend、SearchBar、ThemePicker、i18n、ELK 布局、louvain 聚类）。

P2 的目标是在「**单文件离线 HTML + 原生 JS、无构建、无 LLM、无外部资源**」约束下，把报告的视觉与交互
对齐 UA dashboard。

## 目标

- 视觉重塑为 UA dashboard 的现代风格（CSS 变量驱动的设计 tokens：配色/字体/间距/阴影/圆角）。
- NodeInfo 富详情面板（UA 招牌）：点节点显示 summary、类型/层级/complexity 徽章、tags、callee/caller 关系（可点跳转）、方法源码片段、关联表。
- Persona 切换（初级/资深/PM）调整详情详略。
- 模糊搜索替代当前子串匹配。
- 明暗主题切换。
- 层级图例（LayerLegend 风格）。
- 报告仍是单文件离线 HTML，无外部资源；不引入构建步骤或 React。

## 非目标（P2 不做）

- 语义/LLM 搜索（离线无 LLM）——只做模糊文本匹配。
- 实时 diff 影响分析（P1 无 diff 概念；属未来）。
- React 重建 / 引入构建链——保持原生 JS 单文件。
- i18n 多语言切换——报告仍中文（UA 的 en/zh/ja/ko/ru locale 切换不在 P2）。
- ELK 力导布局 / louvain 聚类——保留现有分层 SVG 布局。

## 设计

### 1. 视觉重塑（`templates/report.html.tmpl`）

- 引入 CSS 自定义属性作为设计 tokens：调色板（层色 + accent + 中性色）、字体阶、间距阶、阴影、圆角。
- 对齐 UA 的干净/现代/卡片化观感：精炼 header、panel 卡片、节点/边样式、表格。层仍按色编码（Controller/Service/Repository/Entity/SQL/Table/Unknown）。
- 明暗双主题：根元素 `[data-theme="light|dark"]`，每个主题一组 CSS 变量。默认 light。
- 保留现有三栏骨架与响应式断点。

### 2. NodeInfo 详情面板（招牌，`render.py` + 模板 + JS）

节点点击时，右侧详情区显示（字段均来自现有图元数据）：

- **标题行**：qual（或表名），类型徽章（function/table），层级徽章，complexity 徽章（simple/moderate/complex），tags。
- **Summary**：复用 `understand_rules._summary`（已在图节点上）。
- **关系**：callees（下游，可点击跳转聚焦）、callers（上游，可点击）。来自图的 call 边。
- **方法源码**：方法体文本（`lines[start_line-1:end_line]`），带行号 `<pre>`，超长截断（默认 2000 字符）。
- **关联表**（unit 节点）：该单元 references 的表节点；**SQL statements**（table 节点）：来源 statement 列表。

Persona 控制上述区段的显隐与详略。

### 3. 数据模型变化（`render.py`）

`_dashboard_graph_json` 的 payload 中，每个 unit 节点新增 `source` 字段：

```python
# render.py，构建 payload 时
def _method_source(node, max_chars=2000):
    file = node.get("file"); start = node.get("line"); end = node.get("end_line")
    if not (file and start and end): return ""
    try:
        lines = Path(file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    body = "\n".join(lines[start-1:end])
    return body[:max_chars] + ("…" if len(body) > max_chars else "")
```

在 payload 的每个 unit 节点 dict 加 `"source": _method_source(node)`。其余图结构不变，`graph.py`/`tables.py`/`trace.py`/`index.py` 不受影响。

### 4. Persona 选择器

- 三档：`资深`(senior，默认) / `初级`(junior) / `PM`。根元素 `data-persona`，存 `localStorage`。
- 区段可见性规则（NodeInfo）：

| 区段 | PM | 资深 | 初级 |
|---|---|---|---|
| summary | ✓ 简明 | ✓ | ✓ 展开白话 |
| 层级/类型徽章 | ✓ | ✓ | ✓ |
| tags | ✓ | ✓ | ✓ |
| 关系 callees/callers | ✗ | ✓ 全量 | ✓ 简化（仅名称） |
| 方法源码 | ✗ | ✓ | ✓ |
| complexity 徽章 | ✗（太技术） | ✓ | ✗（用「简单/中等/复杂」中文标签） |
| 关联表 / SQL | ✓ | ✓ | ✓ |

顶部工具栏放 persona 切换按钮组。

### 5. 模糊搜索（JS）

替换当前子串匹配为「子序列 + 评分」模糊匹配（匹配节点 label/id/layer/table），结果按分数排序，高亮命中字符。纯 JS 实现，无依赖。

### 6. 明暗主题（JS + CSS）

- 顶部主题切换按钮；切换 `<html data-theme>`；存 `localStorage`。
- 每个 theme 一组 CSS 变量（背景/面板/墨色/层色明度调整）。SVG 节点填色用 `currentColor` 或主题变量。

### 7. 层级图例（`render.py` + 模板）

固定小面板：每个出现的层 → 色块 + 名称 + 计数（复用 `LAYER_CLASSES` 配色与 `_layer_counts`）。与现有 layer tabs 互补（tabs 是过滤器，legend 是说明）。

## 文件影响

- `templates/report.html.tmpl`：大幅重塑（设计 tokens、主题、NodeInfo/persona/search/legend 标记与 JS）。
- `render.py`：新增 `_method_source`、NodeInfo/legend/persona/theme 相关渲染辅助；payload 加 `source`。
- `understand_rules.py`：复用现有 `_summary`/`_complexity`/`_tags`（无需改）。
- `tests/test_render.py`：新增/更新断言（payload 含 `source`；关键区段渲染）。
- 不改 `index.py`/`trace.py`/`tables.py`/`graph.py`/`parsing.py`。

## 验收标准

1. 报告仍为单文件离线 HTML，无外部资源依赖（`grep -c "http" output/*.html` 仅命中示例/注释）。
2. 点击节点：NodeInfo 显示 summary、徽章、tags、关系、源码（资深 persona）。
3. Persona 切换：PM 隐藏源码/关系/complexity；初级展开白话 summary。
4. 模糊搜索：输入乱序子串能命中并排序。
5. 主题切换：明暗切换生效并持久化。
6. 层级图例存在且配色与节点一致。
7. `python3 -m pytest` 全绿（`test_render` 适配）；`ruff`/`compileall`/`git diff --check` 干净。
8. 冒烟：`usage-trace --keyword storeNo --root tests/fixtures/java-spring` 生成报告，人工抽查视觉。

## 测试策略

- **单元（`tests/test_render.py`）**：payload 中 unit 节点含非空 `source`（针对 fixture 的 `OrderService.findByStoreNo` 断言含 `selectByStoreNo`）；NodeInfo/legend 关键标记出现在渲染 HTML；persona 默认 `资深`。
- **视觉**：报告美学为主观，靠人工抽查（冒烟后打开 HTML）。实现者可参考 UA dashboard 观感。
- **回归门**：`pytest`/`ruff check .`/`compileall -q src tests`/`git diff --check`。

## 风险

- **视觉主观**：实现者需在「对齐 UA 现代干净观感」方向上有美学裁量权；spec 给 tokens 与结构，不给像素级样式。
- **源码体积**：大方法 `source` 截断到 2000 字符，payload 不过度膨胀。
- **单文件增长**：模板与 JS 增长可接受（仍单文件，无外部资源）。
- **原生 JS 复杂度**：persona/主题/模糊搜索都用轻量原生 JS，避免引入框架。
