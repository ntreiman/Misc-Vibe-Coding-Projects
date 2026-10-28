import os
import sys

import pytest

ADDIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ToolSnap")
DATA_DIR = os.path.join(ADDIN_DIR, "data")
if ADDIN_DIR not in sys.path:
    sys.path.insert(0, ADDIN_DIR)

from core import inventory, paramcsv, rules  # noqa: E402


@pytest.fixture(scope="session")
def tools():
    return inventory.load(os.path.join(DATA_DIR, "shop_tools.json"))


@pytest.fixture(scope="session")
def params():
    return paramcsv.values(paramcsv.load(os.path.join(DATA_DIR, "fastener_parameters.csv")))


@pytest.fixture(scope="session")
def ruleset():
    return rules.load(os.path.join(DATA_DIR, "snap_rules.json"))
