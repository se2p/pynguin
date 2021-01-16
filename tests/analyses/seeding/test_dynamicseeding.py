import importlib
import os

import pytest

from unittest.mock import MagicMock
from pynguin.analyses.seeding.dynamicseeding import DynamicSeeding
from pynguin.analyses.seeding.dynamicseedinginstrumentation import DynamicSeedingInstrumentation


@pytest.fixture()
def dynamic_seeding():
    dynamic_seeding = DynamicSeeding()
    DynamicSeeding()._dynamic_pool = {
                "int": set(),
                "float": set(),
                "string": set()
            }
    return dynamic_seeding


@pytest.fixture()
def fixture_dir():
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "fixtures",
        "seeding",
        "dynamicseeding",
    )


@pytest.fixture()
def dummy_module():
    dummy_module = importlib.import_module("tests.fixtures.seeding.dynamicseeding.dynamicseedingdummies")
    dummy_module = importlib.reload(dummy_module)
    return dummy_module


def test_singleton():
    dynamic_seeding_1 = DynamicSeeding()
    dynamic_seeding_2 = DynamicSeeding()
    assert dynamic_seeding_1 is dynamic_seeding_2


def test_isalnum_instrumentation_true(dummy_module, dynamic_seeding):
    instr = DynamicSeedingInstrumentation()
    dummy_module.isalnum_test.__code__ = instr.instrument_module(dummy_module.isalnum_test.__code__)
    res = dummy_module.isalnum_test("alnumtest")

    assert res == 0
    assert DynamicSeeding().has_strings == True
    assert "alnumtest" in DynamicSeeding()._dynamic_pool["string"]
    assert "alnumtest!" in DynamicSeeding()._dynamic_pool["string"]


def test_isalnum_instrumentation_false(dummy_module, dynamic_seeding):
    instr = DynamicSeedingInstrumentation()
    dummy_module.isalnum_test.__code__ = instr.instrument_module(dummy_module.isalnum_test.__code__)
    res = dummy_module.isalnum_test("alnum_test")

    assert res == 1
    assert DynamicSeeding().has_strings == True
    assert "alnum_test" in DynamicSeeding()._dynamic_pool["string"]
    assert "isalnum" in DynamicSeeding()._dynamic_pool["string"]
