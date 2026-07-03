from pathlib import Path

from common import load_profile
from discover import keyword_variants, layer_of, discover


def test_variants_cover_forms():
    v = keyword_variants("storeNo")
    assert "storeNo" in v and "store_no" in v and "STORE_NO" in v and "StoreNo" in v


def test_layer_of_by_path_hint():
    layers = [{"name": "Controller", "path_hint": "controller"},
              {"name": "Service", "path_hint": "service"},
              {"name": "Repository", "path_hint": "(mapper|repository|dao)"}]
    assert layer_of("pkg/service/OrderService.java", layers) == "Service"
    assert layer_of("pkg/mapper/OrderMapper.java", layers) == "Repository"
    assert layer_of("pkg/util/Helper.java", layers) == "Unknown"


def test_discovers_fixture_sites(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    sites = discover("storeNo", fixture_root, profile)
    files = {Path(s["file"]).name for s in sites}
    assert "OrderController.java" in files
    assert "OrderService.java" in files
    assert "OrderMapper.java" in files
    s = sites[0]
    assert set(s) == {"file", "line", "col", "occurrence_type", "layer", "snippet"}
    assert any(s["layer"] == "Service" and "OrderService" in s["file"] for s in sites)
