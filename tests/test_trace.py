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
