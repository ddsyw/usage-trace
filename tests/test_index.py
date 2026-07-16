import json

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
        # Insert brandNew *inside* the class body (before its closing brace)
        # so tree-sitter records it as EdgeCaseService.brandNew. A naive
        # append after the file's final '}' parses as a top-level method
        # (empty cls) and would not match the assertion below.
        body = original.rstrip()
        assert body.endswith("}"), "fixture must end with class closing brace"
        mutated = body[:-1] + "\n    public void brandNew() { done(); }\n}\n"
        edge.write_text(mutated)
        idx2 = ProjectIndex.load_or_build(fixture_root, profile, cache_dir=tmp_path)
        assert "EdgeCaseService.brandNew" in idx2.methods
    finally:
        edge.write_text(original)


def test_index_manifest_has_version_and_root_hash(tmp_path, fixture_root, profiles_dir):
    profile, idx = _build_cached(fixture_root, profiles_dir, tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["version"] == 1
    assert manifest["root_hash"] == idx.root_hash
