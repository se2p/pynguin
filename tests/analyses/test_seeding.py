#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

import pynguin.configuration as config
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import parse_seed_module
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)


@pytest.fixture
def parameters_test_cluster():
    config.configuration.module_name = "tests.fixtures.grammar.parameters"
    return generate_test_cluster("tests.fixtures.grammar.parameters")


@pytest.fixture
def dummy_test_cluster():
    config.configuration.module_name = (
        "tests.fixtures.seeding.initialpopulationseeding.dummycontainer"
    )
    return generate_test_cluster("tests.fixtures.seeding.initialpopulationseeding.dummycontainer")


# ---------------------------------------------------------------------------
# Parameter mapping round-trip (positional-only / *args / **kwargs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("testcase_seed", "expected_code"),
    [
        (
            "def test_case_0():\n"
            "    float_0 = 1.1\n"
            "    var_0 = module_0.positional_only(float_0)\n",
            "var_0 = 1.1\nvar_1 = parameters_.positional_only(var_0)\n",
        ),
        (
            "def test_case_0():\n"
            "    float_0 = 1.1\n"
            "    int_0 = 42\n"
            "    list_0 = []\n"
            '    str_0 = "test"\n'
            '    bytes_0 = b"key"\n'
            '    str_1 = "value"\n'
            "    dict_0 = {bytes_0: str_1}\n"
            "    var_0 = module_0.all_params(float_0, int_0, *list_0, "
            "param4=str_0, **dict_0)\n",
            (
                "var_0 = 1.1\n"
                "var_1 = 42\n"
                "var_2 = []\n"
                'var_3 = "test"\n'
                'var_4 = b"key"\n'
                'var_5 = "value"\n'
                "var_6 = {var_4: var_5}\n"
                "var_7 = parameters_.all_params(var_0, var_1, *var_2, "
                "param4=var_3, **var_6)\n"
            ),
        ),
        (
            "def test_case_0():\n    float_0 = 1.1\n    module_0.positional_only(float_0)\n",
            "var_0 = 1.1\nparameters_.positional_only(var_0)\n",
        ),
    ],
)
def test_parameter_mapping_roundtrip(parameters_test_cluster, testcase_seed, expected_code):
    source = "import tests.fixtures.grammar.parameters as module_0\n\n\n" + testcase_seed
    testcases = parse_seed_module(source, parameters_test_cluster, create_assertions=False)
    assert len(testcases) == 1
    assert testcases[0].to_code() == expected_code


def test_parameter_mapping_call_is_resolved(parameters_test_cluster):
    source = (
        "import tests.fixtures.grammar.parameters as module_0\n\n\n"
        "def test_case_0():\n"
        "    float_0 = 1.1\n"
        "    var_0 = module_0.positional_only(float_0)\n"
    )
    testcases = parse_seed_module(source, parameters_test_cluster, create_assertions=False)
    call_stmt = testcases[0].statements()[-1]
    assert isinstance(call_stmt.accessible, GenericFunction)
    assert call_stmt.accessible.function_name == "positional_only"


def test_keyword_argument_call_is_resolved(parameters_test_cluster):
    """A call using a keyword argument (``param4=...``) must still resolve.

    ``param4`` is a parameter name, not a variable read; regression test for the
    admission check incorrectly requiring keyword names to be known variables.
    """
    source = (
        "import tests.fixtures.grammar.parameters as module_0\n\n\n"
        "def test_case_0():\n"
        "    float_0 = 1.1\n"
        "    int_0 = 42\n"
        "    list_0 = []\n"
        '    str_0 = "test"\n'
        "    dict_0 = {}\n"
        "    var_0 = module_0.all_params(float_0, int_0, *list_0, "
        "param4=str_0, **dict_0)\n"
    )
    testcases = parse_seed_module(source, parameters_test_cluster, create_assertions=False)
    assert len(testcases) == 1
    call_stmt = testcases[0].statements()[-1]
    assert isinstance(call_stmt.accessible, GenericFunction)
    assert call_stmt.accessible.function_name == "all_params"


# ---------------------------------------------------------------------------
# SUT-alias normalization is applied module-wide, not just per function
# ---------------------------------------------------------------------------


def test_module_level_import_shared_across_functions_is_normalized(dummy_test_cluster):
    """A shared, module-level SUT import must be normalized for every function.

    This is the shape of both hand-written seed files and Pynguin's own
    exported suites, unlike LLM-flattened code where the import is hoisted
    into every individual test function.
    """
    source = (
        "import tests.fixtures.seeding.initialpopulationseeding.dummycontainer "
        "as module0\n\n\n"
        "def seed_test_case0():\n"
        "    var0 = [1, 2, 3]\n"
        "    var1 = module0.i_take_list(var0)\n"
        "    assert var1 == 'not empty!'\n\n\n"
        "def seed_test_case1():\n"
        "    var0 = []\n"
        "    var1 = module0.i_take_list(var0)\n"
        "    assert var1 == 'empty!'\n"
    )
    testcases = parse_seed_module(source, dummy_test_cluster, create_assertions=True)
    assert len(testcases) == 2
    for testcase in testcases:
        assert "module0" not in testcase.to_code()
        assert "dummycontainer_.i_take_list(" in testcase.to_code()
        call_stmt = testcase.statements()[-1]
        assert isinstance(call_stmt.accessible, GenericFunction)
        assert len(call_stmt.assertions) == 1


def test_constructor_and_method_calls_are_resolved(dummy_test_cluster):
    source = (
        "import tests.fixtures.seeding.initialpopulationseeding.dummycontainer "
        "as module0\n\n\n"
        "def seed_test_case0():\n"
        "    var0 = 10\n"
        "    var1 = module0.Simple(var0)\n"
        "    var2 = [1, 2, 3]\n"
        "    var3 = var1.do_something(var2)\n"
        "    assert var3 == 'not empty!'\n"
    )
    testcases = parse_seed_module(source, dummy_test_cluster, create_assertions=True)
    assert len(testcases) == 1
    statements = testcases[0].statements()
    assert isinstance(statements[1].accessible, GenericConstructor)
    assert isinstance(statements[3].accessible, GenericMethod)
    assert statements[3].assertions[0].object == "not empty!"


def test_non_sut_local_class_is_not_resolved_and_testcase_is_dropped(dummy_test_cluster):
    source = "class NoPrimitive:\n    pass\n\n\ndef seed_test_case_1():\n    var0 = NoPrimitive()\n"
    testcases = parse_seed_module(source, dummy_test_cluster, create_assertions=True)
    assert testcases == []


def test_unparsable_module_returns_empty_list(dummy_test_cluster):
    testcases = parse_seed_module("def test_broken(:\n", dummy_test_cluster, create_assertions=True)
    assert testcases == []


def test_only_test_and_seed_test_prefixed_functions_are_considered(dummy_test_cluster):
    source = "def helper():\n    var0 = 1\n\n\ndef test_0():\n    var0 = 1\n"
    testcases = parse_seed_module(source, dummy_test_cluster, create_assertions=False)
    assert len(testcases) == 1
