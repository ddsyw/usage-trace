import sys

from codex_find import main, run


def test_run_writes_full_report(fixture_root, tmp_path):
    out = tmp_path / "storeNo-report.html"

    graph = run("storeNo", fixture_root, out=out)

    html = out.read_text(encoding="utf-8")
    assert out.exists()
    assert "OrderController.queryByStoreNo" in html
    assert "OrderService.findByStoreNo" in html
    assert "OrderMapper.selectByStoreNo" in html
    assert "t_order" in html
    assert graph["meta"]["counts"]["tables"] == 1


def test_main_writes_report_from_args(fixture_root, tmp_path, monkeypatch):
    out = tmp_path / "report.html"
    monkeypatch.setattr(sys, "argv", [
        "codex_find.py",
        "--keyword", "storeNo",
        "--root", str(fixture_root),
        "--out", str(out),
    ])

    main()

    assert out.exists()
    assert "t_order" in out.read_text(encoding="utf-8")
