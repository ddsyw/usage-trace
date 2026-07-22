import json
import sys
from pathlib import Path

from common import load_profile
from discover import keyword_variants, layer_of, discover, main
from index import ProjectIndex


def test_variants_cover_forms():
    v = keyword_variants("storeNo")
    assert "storeNo" in v and "store_no" in v and "STORE_NO" in v and "StoreNo" in v


def test_layer_of_by_path_hint():
    layers = [{"name": "Controller", "path_hint": "controller"},
              {"name": "Service", "path_hint": "service"},
              {"name": "Repository", "path_hint": "(mapper|repository|dao)"}]
    assert layer_of("pkg/service/OrderService.java", layers) == "Service"
    assert layer_of("pkg/mapper/OrderMapper.java", layers) == "Repository"
    assert layer_of("pkg/util/Helper.java", layers) == "Other"


def test_layer_of_by_annotation_match_when_path_is_generic():
    layers = [{"name": "Service", "match": "@Service", "path_hint": "service"}]
    assert layer_of("pkg/app/OrderLogic.java", layers, "@Service\nclass OrderLogic {}") == "Service"


def test_discovers_fixture_sites(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(fixture_root, profile)
    sites = discover("storeNo", profile, None, idx)
    files = {Path(s["file"]).name for s in sites}
    assert "OrderController.java" in files
    assert "OrderService.java" in files
    assert "OrderMapper.java" in files
    s = sites[0]
    assert set(s) == {"file", "line", "col", "occurrence_type", "layer", "snippet"}
    assert any(s["layer"] == "Service" and "OrderService" in s["file"] for s in sites)


def test_discover_ignores_comment_only_matches(fixture_root, profiles_dir):
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(fixture_root, profile)
    sites = discover("storeNo", profile, None, idx)
    assert not any("Same method name" in s["snippet"] for s in sites)


def test_main_honors_extra_variants(tmp_path, profiles_dir, monkeypatch, capsys):
    source = tmp_path / "Example.java"
    source.write_text(
        "package demo;\n"
        "public class Example {\n"
        "  public Object query(String shopCode) { return shopCode; }\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", [
        "discover.py",
        "--keyword", "storeNo",
        "--variants", "shopCode",
        "--root", str(tmp_path),
        "--profile", "java-spring",
    ])

    main()

    sites = json.loads(capsys.readouterr().out)
    assert len(sites) == 2  # param + return (word-boundary multi-hit per line)
    assert all(s["snippet"] == "public Object query(String shopCode) { return shopCode; }" for s in sites)
    assert {s["col"] for s in sites} == {sites[0]["col"], sites[1]["col"]}


def test_discover_word_boundary_skips_substrings(tmp_path, profiles_dir):
    source = tmp_path / "Id.java"
    source.write_text(
        "public class IdentityService {\n"
        "  void voidMethod(String validId) { int identity = 1; int id = 2; }\n"
        "}\n",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(tmp_path, profile)
    sites = discover("id", profile, None, idx)
    assert len(sites) == 1
    # Only the standalone variable `id`, not IdentityService / validId / identity.
    raw = source.read_text().splitlines()[sites[0]["line"] - 1]
    assert raw[sites[0]["col"] - 1:sites[0]["col"] + 1] == "id"
    assert "identity" not in raw[max(0, sites[0]["col"] - 4):sites[0]["col"] + 6]


def test_layer_of_ignores_hyphenated_project_name():
    """``common-entry-service`` must not match path_hint ``service``."""
    layers = [{"name": "Controller", "path_hint": "controller"},
              {"name": "Service", "path_hint": "service", "match": "@Service"},
              {"name": "Repository", "path_hint": "(mapper|repository|dao)",
               "match": "@Repository|@Mapper"}]
    dao = ("/work/common-entry-service/entry-dao/src/main/java/"
           "com/leyantech/entry/dao/repository/bible/BibleTemplateEntryDao.java")
    text = "@Repository\npublic interface BibleTemplateEntryDao {}"
    assert layer_of(dao, layers, text) == "Repository"
    svc = "/work/common-entry-service/entry-core/src/main/java/com/x/service/impl/FooService.java"
    assert layer_of(svc, layers, "@Service\nclass FooService {}") == "Service"


def test_variants_include_camel_plural():
    v = keyword_variants("storeNo")
    assert "storeNos" in v and "StoreNos" in v


def test_discover_matches_camelcase_embedded_and_plural(tmp_path, profiles_dir):
    source = tmp_path / "Api.java"
    source.write_text(
        "public class Api {\n"
        "  void transferTemplate(List<String> storeNos, String entryName) {}\n"
        "  List x = dao.queryListByEntryNameAndStoreNo(storeNos.get(0));\n"
        "  String y = req.getStoreNo();\n"
        "}\n",
        encoding="utf-8",
    )
    profile = load_profile("java-spring", profiles_dir)
    idx = ProjectIndex()
    idx.build(tmp_path, profile)
    sites = discover("storeNo", profile, None, idx)
    snippets = " | ".join(s["snippet"] for s in sites)
    assert "storeNos" in snippets
    assert any("getStoreNo" in s["snippet"] for s in sites)
    assert any("AndStoreNo" in s["snippet"] for s in sites)
