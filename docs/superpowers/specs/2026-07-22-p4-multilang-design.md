# P4 设计：多语言（Python / C#）

**日期：** 2026-07-22  
**状态：** ✅ 基础交付  
**所属路线图：** usage-trace 四阶段升级（P1 ✅ → P2 ✅ → P3 ✅ → **P4 多语言** ✅ 基础）

## 目标

在保持「单文件离线 HTML + 无外部资源」约束下，把引擎从 Java-only 扩展到：

| 语言 | 解析器 | Profile | 表解析 |
|------|--------|---------|--------|
| Java | tree-sitter-java（既有） | java-spring / java-generic | MyBatis / JPA / SQL 字面量 |
| Python | tree-sitter-python | python-sqlalchemy / python-generic | SQLAlchemy `__tablename__` + SQL 字面量 |
| C# | tree-sitter-c-sharp | csharp-ef / csharp-generic | EF Core `[Table]` / `ToTable` / `DbSet` + SQL 字面量 |

## 扩展点

- `parsing.LANGUAGES`：后缀 → `LanguageParser`
- `index._SOURCE_EXTS = tuple(LANGUAGES.keys())`
- `INDEX_VERSION` 升到 4（源扩展变化使旧缓存失效）
- `usage_trace.detect_profile_name`：按标记文件与源内容自动选 profile
- `tables.resolve_tables`：新增 `sqlalchemy` / `ef_core` / `python_sql_literals` / `csharp_sql_literals`

## 非目标（本基础版）

- 完整 ORM 关系图 / migration 解析
- 多语言 monorepo 的混合主语言精细检测（当前按 Java → Python → C# 优先级）
- 其他语言（Go/TS/…）

## 验收

- fixture `tests/fixtures/python-sqlalchemy` 对 `store_no` 产出调用链 + `orders` 表
- fixture `tests/fixtures/csharp-ef` 对 `storeNo` 产出调用链 + `orders` 表
- `python3 -m pytest` 全绿；依赖含 `tree-sitter-python` / `tree-sitter-c-sharp`
