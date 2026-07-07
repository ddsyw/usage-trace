def test_fixture_files_exist(fixture_root):
    expected = [
        "pom.xml",
        "src/main/java/com/example/controller/OrderController.java",
        "src/main/java/com/example/service/OrderService.java",
        "src/main/java/com/example/service/StoreService.java",
        "src/main/java/com/example/mapper/OrderMapper.java",
        "src/main/resources/mapper/OrderMapper.xml",
    ]
    for rel in expected:
        assert (fixture_root / rel).exists(), f"missing fixture file: {rel}"


def test_fixture_store_no_chain_present(fixture_root):
    # The known chain the whole test-suite depends on.
    ctrl = (fixture_root / "src/main/java/com/example/controller/OrderController.java").read_text()
    svc = (fixture_root / "src/main/java/com/example/service/OrderService.java").read_text()
    mp = (fixture_root / "src/main/resources/mapper/OrderMapper.xml").read_text()
    assert "queryByStoreNo" in ctrl and "storeNo" in ctrl
    assert "findByStoreNo" in svc and "storeNo" in svc
    assert "selectByStoreNo" in mp and "t_order" in mp and "store_no" in mp


def test_pyproject_declares_console_script(profiles_dir):
    text = (profiles_dir.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "codex-find"' in text
    assert 'codex-find = "codex_find:main"' in text
