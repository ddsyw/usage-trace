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
