from common import load_profile
from discover import discover
from index import ProjectIndex
from trace import HARD_DEPTH_CAP, trace


def test_trace_builds_graph_around_usage(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(fixture_root, profile)
    usages = discover("storeNo", profile, None, idx)
    g = trace(usages, idx, profile, depth=4)

    ids = {n["id"] for n in g["nodes"]}
    assert "OrderService.findByStoreNo" in ids
    edge_pairs = {(e["from"], e["to"]) for e in g["edges"]}
    assert ("OrderService.findByStoreNo", "OrderMapper.selectByStoreNo") in edge_pairs


def test_trace_depth_hard_cap_default():
    assert HARD_DEPTH_CAP == 8



def test_trace_this_field_chain(tmp_path, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    (tmp_path / "controller").mkdir()
    (tmp_path / "service").mkdir()
    (tmp_path / "mapper").mkdir()
    (tmp_path / "controller/OrderController.java").write_text(
        "package c;\n"
        "@org.springframework.web.bind.annotation.RestController\n"
        "public class OrderController {\n"
        "  private final OrderService orderService;\n"
        "  public Object queryByStoreNo(String storeNo) {\n"
        "    return this.orderService.findByStoreNo(storeNo);\n"
        "  }\n"
        "}\n", encoding="utf-8")
    (tmp_path / "service/OrderService.java").write_text(
        "package s;\n"
        "@org.springframework.stereotype.Service\n"
        "public class OrderService {\n"
        "  private final OrderMapper orderMapper;\n"
        "  public Object findByStoreNo(String storeNo) {\n"
        "    return this.orderMapper.selectByStoreNo(storeNo);\n"
        "  }\n"
        "}\n", encoding="utf-8")
    (tmp_path / "mapper/OrderMapper.java").write_text(
        "package m;\n"
        "public interface OrderMapper { Object selectByStoreNo(String storeNo); }\n",
        encoding="utf-8")
    idx = ProjectIndex()
    idx.build(tmp_path, profile)
    usages = discover("storeNo", profile, None, idx)
    g = trace(usages, idx, profile, depth=4)
    edge_pairs = {(e["from"], e["to"]) for e in g["edges"]}
    assert ("OrderController.queryByStoreNo", "OrderService.findByStoreNo") in edge_pairs
    assert ("OrderService.findByStoreNo", "OrderMapper.selectByStoreNo") in edge_pairs
