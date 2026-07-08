import sys
import subprocess

from codex_find import run as compat_run
from usage_trace import main, run


def _write_generic_java_project(root):
    (root / "pom.xml").write_text("<project></project>\n", encoding="utf-8")
    api_dir = root / "src/main/java/demo/api"
    service_dir = root / "src/main/java/demo/service"
    dao_dir = root / "src/main/java/demo/dao"
    api_dir.mkdir(parents=True)
    service_dir.mkdir(parents=True)
    dao_dir.mkdir(parents=True)
    (api_dir / "OrderApi.java").write_text(
        """package demo.api;

import demo.service.OrderService;

public class OrderApi {
    private final OrderService orderService;

    public OrderApi(OrderService orderService) {
        this.orderService = orderService;
    }

    public Object queryByStoreNo(String storeNo) {
        return orderService.findByStoreNo(storeNo);
    }
}
""",
        encoding="utf-8",
    )
    (service_dir / "OrderService.java").write_text(
        """package demo.service;

import demo.dao.OrderDao;

public class OrderService {
    private final OrderDao orderDao;

    public OrderService(OrderDao orderDao) {
        this.orderDao = orderDao;
    }

    public Object findByStoreNo(String storeNo) {
        return orderDao.selectByStoreNo(storeNo);
    }
}
""",
        encoding="utf-8",
    )
    (dao_dir / "OrderDao.java").write_text(
        """package demo.dao;

public class OrderDao {
    public Object selectByStoreNo(String storeNo) {
        String sql = "SELECT * FROM t_order WHERE store_no = ?";
        return sql;
    }
}
""",
        encoding="utf-8",
    )


def test_run_writes_full_report(fixture_root, tmp_path):
    out = tmp_path / "storeNo-report.html"

    graph = run("storeNo", fixture_root, out=out)

    html = out.read_text(encoding="utf-8")
    assert out.exists()
    assert "OrderController.queryByStoreNo" in html
    assert "OrderService.findByStoreNo" in html
    assert "OrderMapper.selectByStoreNo" in html
    assert "OrderMapper.xml" in html
    assert "XML / SQL 来源" in html
    assert "t_order" in html
    assert graph["meta"]["counts"]["tables"] == 1


def test_usage_trace_import_prefers_local_trace_module(tmp_path):
    src_dir = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src")
    code = (
        "import sys; "
        f"sys.path.append({src_dir!r}); "
        "import usage_trace; "
        "print(usage_trace.HARD_DEPTH_CAP)"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "8"


def test_run_defaults_to_usage_trace_directory(fixture_root, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    run("storeNo", fixture_root)

    out = tmp_path / ".usage-trace" / "storeNo-report.html"
    assert out.exists()
    assert not (tmp_path / "output" / "storeNo-report.html").exists()
    assert "t_order" in out.read_text(encoding="utf-8")


def test_legacy_codex_find_import_still_runs(fixture_root, tmp_path):
    out = tmp_path / "legacy-report.html"

    graph = compat_run("storeNo", fixture_root, out=out)

    assert out.exists()
    assert graph["meta"]["counts"]["tables"] == 1


def test_run_supports_generic_java_project_with_auto_profile(tmp_path):
    _write_generic_java_project(tmp_path)
    out = tmp_path / "generic-report.html"

    graph = run("storeNo", tmp_path, out=out)

    html = out.read_text(encoding="utf-8")
    assert "OrderApi.queryByStoreNo" in html
    assert "OrderService.findByStoreNo" in html
    assert "OrderDao.selectByStoreNo" in html
    assert "t_order" in html
    assert graph["meta"]["profile"] == "java-generic"
    assert graph["meta"]["counts"]["tables"] == 1


def test_main_writes_report_from_args(fixture_root, tmp_path, monkeypatch):
    out = tmp_path / "report.html"
    monkeypatch.setattr(sys, "argv", [
        "usage_trace.py",
        "--keyword", "storeNo",
        "--root", str(fixture_root),
        "--out", str(out),
    ])

    main()

    assert out.exists()
    assert "t_order" in out.read_text(encoding="utf-8")
