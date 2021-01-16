import importlib
import os

import pytest

from pynguin.analyses.seeding.dynamicseeding import DynamicSeeding
from pynguin.analyses.seeding.dynamicseedinginstrumentation import DynamicSeedingInstrumentation


@pytest.fixture()
def instr():
    instr = DynamicSeedingInstrumentation()
    return instr


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


def test_compare_op_int(instr, dummy_module, dynamic_seeding):
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(dummy_module.compare_op_dummy.__code__)
    res = dummy_module.compare_op_dummy(10, 11)

    assert res == 1
    assert 10 in DynamicSeeding()._dynamic_pool["int"]
    assert 11 in DynamicSeeding()._dynamic_pool["int"]


def test_compare_op_float(instr, dummy_module, dynamic_seeding):
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(dummy_module.compare_op_dummy.__code__)
    res = dummy_module.compare_op_dummy(1.0, 2.5)

    assert res == 1
    assert 1.0 in DynamicSeeding()._dynamic_pool["float"]
    assert 2.5 in DynamicSeeding()._dynamic_pool["float"]


def test_compare_op_string(instr, dummy_module, dynamic_seeding):
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(dummy_module.compare_op_dummy.__code__)
    res = dummy_module.compare_op_dummy("abc", "def")

    assert res == 1
    assert "abc" in DynamicSeeding()._dynamic_pool["string"]
    assert "def" in DynamicSeeding()._dynamic_pool["string"]


def test_compare_op_other_type(instr, dummy_module, dynamic_seeding):
    dummy_module.compare_op_dummy.__code__ = instr.instrument_module(dummy_module.compare_op_dummy.__code__)
    res = dummy_module.compare_op_dummy(True, "def")

    assert res == 1
    assert DynamicSeeding().has_ints is False
    assert DynamicSeeding().has_floats is False
    assert DynamicSeeding().has_strings is True
    assert "def" in DynamicSeeding()._dynamic_pool["string"]


def test_startswith_function(instr, dummy_module, dynamic_seeding):
    dummy_module.startswith_dummy.__code__ = instr.instrument_module(dummy_module.startswith_dummy.__code__)
    res = dummy_module.startswith_dummy("abc", "ab")

    assert res == 0
    assert DynamicSeeding().has_strings is True
    assert "ababc" in DynamicSeeding()._dynamic_pool["string"]


def test_endswith_function(instr, dummy_module, dynamic_seeding):
    dummy_module.endswith_dummy.__code__ = instr.instrument_module(dummy_module.endswith_dummy.__code__)
    res = dummy_module.endswith_dummy("abc", "bc")

    assert res == 0
    assert DynamicSeeding().has_strings is True
    assert "abcbc" in DynamicSeeding()._dynamic_pool["string"]


def test_isalnum_instrumentation_true(instr, dummy_module, dynamic_seeding):
    dummy_module.isalnum_dummy.__code__ = instr.instrument_module(dummy_module.isalnum_dummy.__code__)
    res = dummy_module.isalnum_dummy("alnumtest")

    assert res == 0
    assert DynamicSeeding().has_strings is True
    assert "alnumtest" in DynamicSeeding()._dynamic_pool["string"]
    assert "alnumtest!" in DynamicSeeding()._dynamic_pool["string"]


def test_isalnum_instrumentation_false(instr, dummy_module, dynamic_seeding):
    dummy_module.isalnum_dummy.__code__ = instr.instrument_module(dummy_module.isalnum_dummy.__code__)
    res = dummy_module.isalnum_dummy("alnum_test")

    assert res == 1
    assert DynamicSeeding().has_strings is True
    assert "alnum_test" in DynamicSeeding()._dynamic_pool["string"]
    assert "isalnum" in DynamicSeeding()._dynamic_pool["string"]


def test_add_other_type_to_string_function(instr ,dummy_module, dynamic_seeding):
    dummy_module.isalnum_dummy.__code__ = instr.instrument_module(dummy_module.isalnum_dummy.__code__)
    res = dummy_module.isalnum_dummy(True)

    assert res == 2
    assert DynamicSeeding().has_strings is False
    assert DynamicSeeding().has_ints is False
    assert DynamicSeeding().has_floats is False

