from pathlib import Path

from common import load_profile
from index import ProjectIndex, _SOURCE_EXTS
from parsing import CSharpParser, LANGUAGES, PythonParser
from usage_trace import detect_profile_name, run

ROOT = Path(__file__).resolve().parent.parent
PY_FIX = ROOT / "tests" / "fixtures" / "python-sqlalchemy"
CS_FIX = ROOT / "tests" / "fixtures" / "csharp-ef"
PROFILES = ROOT / "profiles"


def test_languages_registry_includes_py_and_cs():
    assert ".py" in LANGUAGES and ".cs" in LANGUAGES and ".java" in LANGUAGES
    assert ".py" in _SOURCE_EXTS and ".cs" in _SOURCE_EXTS


def test_python_parser_methods_and_calls():
    src = (PY_FIX / "app" / "services" / "order_service.py").read_text(encoding="utf-8")
    fs = PythonParser().parse(src, "order_service.py")
    quals = {m.qual for m in fs.methods}
    assert "OrderService.find_by_store_no" in quals
    assert "OrderRepository.select_by_store_no" in quals
    calls = {(c.caller_qual, c.callee_name, c.receiver) for c in fs.calls}
    assert ("OrderService.find_by_store_no", "find_orders", "repo") in calls


def test_csharp_parser_methods_and_calls():
    src = (CS_FIX / "src" / "Services" / "OrderService.cs").read_text(encoding="utf-8")
    fs = CSharpParser().parse(src, "OrderService.cs")
    quals = {m.qual for m in fs.methods}
    assert "OrderService.FindByStoreNo" in quals
    assert any(c.callee_name == "FindOrders" and c.receiver == "repo" for c in fs.calls)


def test_detect_profile_multilang():
    assert detect_profile_name(PY_FIX) == "python-sqlalchemy"
    assert detect_profile_name(CS_FIX) == "csharp-ef"
    assert detect_profile_name(ROOT / "tests" / "fixtures" / "java-spring") == "java-spring"


def test_python_end_to_end_store_no():
    result = run(
        "store_no",
        PY_FIX,
        "auto",
        depth=4,
        max_nodes=100,
        out=ROOT / ".usage-trace" / "p4-python-store_no-report.html",
    )
    units = {n["id"] for n in result["nodes"] if n["kind"] == "unit"}
    tables = {n["table"] for n in result["nodes"] if n["kind"] == "table"}
    assert "OrderService.find_by_store_no" in units
    assert "OrderApi.get_order" in units
    assert "orders" in tables
    assert result["meta"]["profile"] == "python-sqlalchemy"


def test_csharp_end_to_end_store_no():
    result = run(
        "storeNo",
        CS_FIX,
        "auto",
        depth=4,
        max_nodes=100,
        out=ROOT / ".usage-trace" / "p4-csharp-storeNo-report.html",
    )
    units = {n["id"] for n in result["nodes"] if n["kind"] == "unit"}
    tables = {n["table"] for n in result["nodes"] if n["kind"] == "table"}
    assert "OrderController.Get" in units
    assert "OrderService.FindByStoreNo" in units
    assert "orders" in tables
    assert result["meta"]["profile"] == "csharp-ef"


def test_profiles_exist():
    for name in ("python-generic", "python-sqlalchemy", "csharp-generic", "csharp-ef"):
        profile = load_profile(name, PROFILES)
        assert profile.get("profile") == name
        assert "layers" in profile


def test_index_builds_python_sources():
    profile = load_profile("python-sqlalchemy", PROFILES)
    idx = ProjectIndex().build(PY_FIX, profile)
    assert any(p.endswith(".py") for p in idx.files)
    assert "OrderService.find_by_store_no" in idx.methods
