from common import load_profile
from discover import discover
from trace import walk, find_enclosing_unit, trace


# ---- walk: cycle + depth (pure, no fixture) ----

def test_walk_detects_cycle_and_terminates():
    graph = {"A": ["B"], "B": ["A"]}

    def neighbors(node, direction):
        return graph.get(node, [])

    reached, edges = walk(["A"], neighbors, depth=4)
    assert reached == {"A", "B"}
    assert ("A", "B", "confirmed") in edges
    assert ("B", "A", "inferred") in edges  # back-edge to visited node


def test_walk_respects_depth():
    chain = {"A": ["B"], "B": ["C"], "C": ["D"], "D": ["E"], "E": []}

    def neighbors(node, direction):
        return chain.get(node, [])

    reached, _ = walk(["A"], neighbors, depth=2)
    assert reached == {"A", "B", "C"}  # 2 hops: A->B->C


def test_walk_depth_hard_cap():
    chain = {f"n{i}": [f"n{i+1}"] for i in range(20)}
    chain["n20"] = []

    def neighbors(node, direction):
        return chain.get(node, [])

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


def test_trace_avoids_same_name_false_edges_and_duplicates(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    usages = discover("storeNo", fixture_root, profile)
    g = trace(usages, fixture_root, profile, depth=4)
    edges = {(e["from"], e["to"], e["kind"], e["confidence"]) for e in g["edges"]}

    assert len(edges) == len(g["edges"])
    assert (
        "OrderController.queryByStoreNo",
        "OrderService.findByStoreNo",
        "call",
        "confirmed",
    ) in edges
    assert (
        "OrderService.findByStoreNo",
        "OrderMapper.selectByStoreNo",
        "call",
        "confirmed",
    ) in edges
    assert not any(
        e["to"] == "StoreService.findByStoreNo" and e["from"] != "StoreService.findByStoreNo"
        for e in g["edges"]
    )


def test_trace_resolves_mapper_methods_with_param_annotations(tmp_path, profiles_dir):
    java_dir = tmp_path / "src/main/java/com/example"
    (java_dir / "service").mkdir(parents=True)
    (java_dir / "mapper").mkdir(parents=True)
    (java_dir / "service/StoreService.java").write_text(
        """package com.example.service;
import com.example.mapper.StoreMapper;
public class StoreService {
  private final StoreMapper storeMapper;
  public Object getStoreInfoByStoreNo(String storeNo) {
    return this.storeMapper.selectByStoreNo(storeNo);
  }
}
""",
        encoding="utf-8",
    )
    (java_dir / "mapper/StoreMapper.java").write_text(
        """package com.example.mapper;
import org.apache.ibatis.annotations.Param;
public interface StoreMapper {
  Object selectByStoreNo(@Param("storeNo") String storeNo);
}
""",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    usages = discover("storeNo", tmp_path, profile)

    g = trace(usages, tmp_path, profile, depth=2)

    labels = {n["label"] for n in g["nodes"]}
    assert "StoreMapper.selectByStoreNo" in labels
    assert any(
        e["from"] == "StoreService.getStoreInfoByStoreNo"
        and e["to"] == "StoreMapper.selectByStoreNo"
        for e in g["edges"]
    )


def test_trace_uses_annotation_match_for_layer(tmp_path, profiles_dir):
    source = tmp_path / "src/main/java/com/example/app/OrderLogic.java"
    source.parent.mkdir(parents=True)
    source.write_text(
        "package com.example.app;\n"
        "@org.springframework.stereotype.Service\n"
        "public class OrderLogic {\n"
        "  public Object findByStoreNo(String storeNo) {\n"
        "    return storeNo;\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    usages = discover("storeNo", tmp_path, profile)

    g = trace(usages, tmp_path, profile, depth=1)

    node = next(n for n in g["nodes"] if n["label"] == "OrderLogic.findByStoreNo")
    assert node["layer"] == "Service"
