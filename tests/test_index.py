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
    from index import INDEX_VERSION
    assert manifest["version"] == INDEX_VERSION
    assert manifest["root_hash"] == idx.root_hash


def test_index_invalidates_blobs_on_version_mismatch(tmp_path, fixture_root, profiles_dir):
    import json

    from index import INDEX_VERSION
    profile, idx = _build_cached(fixture_root, profiles_dir, tmp_path)
    # Poison one blob with a method a real parse would never produce.
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    any_path = next(iter(manifest["files"]))
    digest = manifest["files"][any_path]["hash"]
    blob_path = tmp_path / "symbols" / f"{digest}.json"
    blob = json.loads(blob_path.read_text())
    blob["methods"].append({"name": "poisoned", "qual": "Poisoned.poisoned", "file": any_path,
                            "start_line": 1, "end_line": 1, "params": {}, "cls": "Poisoned"})
    blob_path.write_text(json.dumps(blob))
    # Simulate a future version bump: manifest claims an older version.
    manifest["version"] = INDEX_VERSION + 1
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    idx2 = ProjectIndex.load_or_build(fixture_root, profile, cache_dir=tmp_path)
    assert "Poisoned.poisoned" not in idx2.methods  # stale blob discarded → rebuilt fresh

    # The on-disk poisoned blob must also be gone, otherwise a subsequent
    # cache hit (manifest rewritten by idx2 to INDEX_VERSION + matching hash)
    # would reload the stale blob. This third load is what the regression
    # actually catches; without the fix idx2 re-parses fresh in memory but
    # _save skips the still-existing poisoned blob, so idx3 picks it up.
    idx3 = ProjectIndex.load_or_build(fixture_root, profile, cache_dir=tmp_path)
    assert "Poisoned.poisoned" not in idx3.methods


def test_resolve_inherited_and_this_field(tmp_path, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    (tmp_path / "Base.java").write_text(
        "public class Base { void run(String storeNo) {} }\n", encoding="utf-8")
    (tmp_path / "Child.java").write_text(
        "public class Child extends Base {\n"
        "  private Helper helper;\n"
        "  void entry(String storeNo) { run(storeNo); super.run(storeNo); this.helper.go(storeNo); }\n"
        "}\n"
        "class Helper { void go(String storeNo) {} }\n",
        encoding="utf-8")
    idx = ProjectIndex()
    idx.build(tmp_path, profile)
    assert idx.resolve_callee_targets("Child.entry", "run", None) == ["Base.run"]
    assert idx.resolve_callee_targets("Child.entry", "run", "super") == ["Base.run"]
    assert idx.resolve_callee_targets("Child.entry", "go", "helper") == ["Helper.go"]


def test_resolve_static_class_name(tmp_path, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    (tmp_path / "U.java").write_text(
        "public class U { void entry(String storeNo) { Util.fmt(storeNo); } }\n"
        "class Util { static String fmt(String storeNo) { return storeNo; } }\n",
        encoding="utf-8")
    idx = ProjectIndex()
    idx.build(tmp_path, profile)
    assert idx.resolve_callee_targets("U.entry", "fmt", "Util") == ["Util.fmt"]
