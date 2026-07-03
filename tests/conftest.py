import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
# Make src/ importable as top-level modules (common, discover, ...).
sys.path.insert(0, str(ROOT.parent / "src"))


@pytest.fixture
def fixture_root():
    return ROOT / "fixtures" / "java-spring"


@pytest.fixture
def profiles_dir():
    return ROOT.parent / "profiles"
