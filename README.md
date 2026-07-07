# codex-find

Trace a keyword through a Java/Spring project and render a single offline HTML report with:

- usage sites
- caller/callee chain
- involved database tables
- a layered SVG diagram

## Quick Start

From this repository root:

```bash
python src/codex_find.py \
  --keyword storeNo \
  --root tests/fixtures/java-spring \
  --out output/storeNo-report.html
```

Open `output/storeNo-report.html` in a browser.

For local development, you can also install the console script in editable mode:

```bash
python3 -m pip install -e ".[dev]"
codex-find --keyword storeNo --root tests/fixtures/java-spring --out output/storeNo-report.html
```

The default profile is `auto`. Java/Spring projects are analyzed with `java-spring`;
plain Java projects are analyzed with `java-generic`.

## Options

```bash
python src/codex_find.py --keyword <identifier> --root <project> [options]
```

- `--profile auto`: language profile, default `auto`; available Java profiles are
  `java-spring` and `java-generic`
- `--depth 4`: call-chain depth, hard-capped in code
- `--max-nodes 300`: maximum rendered graph nodes
- `--variants a,b,c`: extra keyword variants to search
- `--out path/to/report.html`: output path

## Development

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m compileall -q src tests
```

The lower-level phase scripts still exist for debugging:

1. `src/discover.py`
2. `src/trace.py`
3. `src/tables.py`
4. `src/graph.py`
5. `src/render.py`

## Support Matrix

- Java/Spring: keyword usage, call chain, MyBatis XML, MyBatis annotation SQL,
  JPA repository/entity tables, raw SQL files, Java SQL string literals.
- Plain Java: keyword usage, call chain, path-based layers, raw SQL files, Java
  SQL string literals.
- Non-Java languages: not supported for full call-chain tracing yet.
