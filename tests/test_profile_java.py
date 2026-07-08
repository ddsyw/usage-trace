from common import load_profile


def test_profile_loads(profiles_dir):
    p = load_profile("java-spring", profiles_dir)
    assert p["profile"] == "java-spring"
    assert "pom.xml" in p["detect"]["files"]


def test_java_generic_profile_loads(profiles_dir):
    p = load_profile("java-generic", profiles_dir)
    assert p["profile"] == "java-generic"
    assert "pom.xml" in p["detect"]["files"]
    assert "java_sql_literals" in p["table_sources"]
    assert "mybatis" in p["table_sources"]


def test_profile_layers_ordered(profiles_dir):
    p = load_profile("java-spring", profiles_dir)
    names = [L["name"] for L in p["layers"]]
    assert names == ["Controller", "Service", "Repository"]


def test_profile_table_sources(profiles_dir):
    p = load_profile("java-spring", profiles_dir)
    ts = p["table_sources"]
    assert "mybatis" in ts and "jpa" in ts
    assert ts["mybatis"]["namespace_to_interface"] is True
