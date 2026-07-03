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
