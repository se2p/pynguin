#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
import inspect
import sys
from collections import defaultdict
from typing import Any, Callable, Dict
from unittest.mock import MagicMock

import pytest
from bytecode import Bytecode, Instr, Label

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereferenceimpl as vri
from pynguin.analyses.controlflow.cfg import CFG
from pynguin.analyses.controlflow.programgraph import ProgramGraphNode
from pynguin.setup.testcluster import TestCluster
from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericField,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.statistics.statistics import StatisticsTracker
from tests.fixtures.accessibles.accessible import SomeType, simple_function

# -- FIXTURES --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_configuration():
    """Automatically reset the configuration singleton"""
    config.INSTANCE = config.Configuration(
        algorithm=config.Algorithm.RANDOOPY,
        project_path="",
        output_path="",
        module_name="",
    )


@pytest.fixture(scope="function")
def test_case_mock():
    return MagicMock(tc.TestCase)


@pytest.fixture(scope="function")
def variable_reference_mock():
    return MagicMock(vri.VariableReferenceImpl)


@pytest.fixture(scope="session")
def provide_imported_modules() -> Dict[str, Any]:
    module_names = [
        "tests.fixtures.examples.basket",
        "tests.fixtures.examples.dummies",
        "tests.fixtures.examples.monkey",
        "tests.fixtures.examples.private_methods",
        "tests.fixtures.examples.triangle",
    ]
    modules = {m.split(".")[-1]: importlib.import_module(m) for m in module_names}
    return modules


@pytest.fixture(scope="session")
def provide_callables_from_fixtures_modules(
    provide_imported_modules,
) -> Dict[str, Callable]:
    def inspect_member(member):
        try:
            return (
                inspect.isclass(member)
                or inspect.ismethod(member)
                or inspect.isfunction(member)
            )
        except BaseException:
            return False

    members = []
    for _, module in provide_imported_modules.items():
        for member in inspect.getmembers(module, inspect_member):
            members.append(member)
    callables_ = {k: v for (k, v) in members}
    return callables_


@pytest.fixture()
def constructor_mock() -> GenericConstructor:
    return GenericConstructor(
        owner=SomeType,
        inferred_signature=InferredSignature(
            signature=inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        name="y",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=float,
                    ),
                ]
            ),
            return_type=type(None),
            parameters={"y": float},
        ),
    )


@pytest.fixture()
def method_mock() -> GenericMethod:
    return GenericMethod(
        owner=SomeType,
        method=SomeType.simple_method,
        inferred_signature=InferredSignature(
            signature=inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        name="x",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=int,
                    ),
                ]
            ),
            return_type=float,
            parameters={"x": int},
        ),
    )


@pytest.fixture()
def function_mock() -> GenericFunction:
    return GenericFunction(
        function=simple_function,
        inferred_signature=InferredSignature(
            signature=inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        name="z",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=float,
                    ),
                ]
            ),
            return_type=float,
            parameters={"z": float},
        ),
    )


@pytest.fixture()
def field_mock() -> GenericField:
    return GenericField(owner=SomeType, field="y", field_type=float)


@pytest.fixture
def short_test_case(constructor_mock):
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, 5)
    constructor_stmt = param_stmt.ConstructorStatement(
        test_case, constructor_mock, [int_stmt.return_value]
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_stmt)
    return test_case


@pytest.fixture(autouse=True)
def reset_test_cluster():
    TestCluster._instance = None


@pytest.fixture(autouse=True)
def reset_statistics_tracker():
    StatisticsTracker._instance = None


@pytest.fixture(scope="module")
def conditional_jump_example_bytecode() -> Bytecode:
    label_else = Label()
    label_print = Label()
    byte_code = Bytecode(
        [
            Instr("LOAD_NAME", "print"),
            Instr("LOAD_NAME", "test"),
            Instr("POP_JUMP_IF_FALSE", label_else),
            Instr("LOAD_CONST", "yes"),
            Instr("JUMP_FORWARD", label_print),
            label_else,
            Instr("LOAD_CONST", "no"),
            label_print,
            Instr("CALL_FUNCTION", 1),
            Instr("LOAD_CONST", None),
            Instr("RETURN_VALUE"),
        ]
    )
    return byte_code


@pytest.fixture(scope="module")
def small_control_flow_graph() -> CFG:
    cfg = CFG(MagicMock())
    entry = ProgramGraphNode(index=0)
    n2 = ProgramGraphNode(index=2)
    n3 = ProgramGraphNode(index=3)
    n4 = ProgramGraphNode(index=4)
    n5 = ProgramGraphNode(index=5)
    n6 = ProgramGraphNode(index=6)
    exit_node = ProgramGraphNode(index=sys.maxsize)
    cfg.add_node(entry)
    cfg.add_node(n2)
    cfg.add_node(n3)
    cfg.add_node(n4)
    cfg.add_node(n5)
    cfg.add_node(n6)
    cfg.add_node(exit_node)
    cfg.add_edge(entry, n6)
    cfg.add_edge(n6, n5)
    cfg.add_edge(n5, n4)
    cfg.add_edge(n5, n3)
    cfg.add_edge(n4, n2)
    cfg.add_edge(n3, n2)
    cfg.add_edge(n2, exit_node)
    return cfg


@pytest.fixture(scope="module")
def larger_control_flow_graph() -> CFG:
    graph = CFG(MagicMock())
    entry = ProgramGraphNode(index=-sys.maxsize)
    n_1 = ProgramGraphNode(index=1)
    n_2 = ProgramGraphNode(index=2)
    n_3 = ProgramGraphNode(index=3)
    n_5 = ProgramGraphNode(index=5)
    n_100 = ProgramGraphNode(index=100)
    n_110 = ProgramGraphNode(index=110)
    n_120 = ProgramGraphNode(index=120)
    n_130 = ProgramGraphNode(index=130)
    n_140 = ProgramGraphNode(index=140)
    n_150 = ProgramGraphNode(index=150)
    n_160 = ProgramGraphNode(index=160)
    n_170 = ProgramGraphNode(index=170)
    n_180 = ProgramGraphNode(index=180)
    n_190 = ProgramGraphNode(index=190)
    n_200 = ProgramGraphNode(index=200)
    n_210 = ProgramGraphNode(index=210)
    n_300 = ProgramGraphNode(index=300)
    n_exit = ProgramGraphNode(index=sys.maxsize)
    graph.add_node(entry)
    graph.add_node(n_1)
    graph.add_node(n_2)
    graph.add_node(n_3)
    graph.add_node(n_5)
    graph.add_node(n_100)
    graph.add_node(n_110)
    graph.add_node(n_120)
    graph.add_node(n_130)
    graph.add_node(n_140)
    graph.add_node(n_150)
    graph.add_node(n_160)
    graph.add_node(n_170)
    graph.add_node(n_180)
    graph.add_node(n_190)
    graph.add_node(n_200)
    graph.add_node(n_210)
    graph.add_node(n_300)
    graph.add_node(n_exit)
    graph.add_edge(entry, n_1)
    graph.add_edge(n_1, n_2)
    graph.add_edge(n_2, n_3)
    graph.add_edge(n_3, n_5)
    graph.add_edge(n_5, n_100)
    graph.add_edge(n_100, n_110)
    graph.add_edge(n_110, n_120, label="true")
    graph.add_edge(n_120, n_130)
    graph.add_edge(n_130, n_140)
    graph.add_edge(n_140, n_150, label="true")
    graph.add_edge(n_150, n_160)
    graph.add_edge(n_160, n_170, label="false")
    graph.add_edge(n_170, n_180)
    graph.add_edge(n_180, n_190)
    graph.add_edge(n_160, n_190, label="true")
    graph.add_edge(n_190, n_140)
    graph.add_edge(n_140, n_200, label="false")
    graph.add_edge(n_200, n_210)
    graph.add_edge(n_210, n_110)
    graph.add_edge(n_110, n_300, label="false")
    graph.add_edge(n_300, n_exit)
    return graph


# -- CONFIGURATIONS AND EXTENSIONS FOR PYTEST ------------------------------------------


def pytest_addoption(parser):
    group = parser.getgroup("pynguin")
    group.addoption(
        "--integration", action="store_true", help="Run integration tests.",
    )
    group.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="Include slow tests in test run",
    )
    group.addoption(
        "--owl",
        action="store",
        type=str,
        default=None,
        metavar="fixture",
        help="Run tests using a specific fixture",
    )


def pytest_runtest_setup(item):
    if "integration" in item.keywords and not item.config.getvalue("integration"):
        pytest.skip("need --integration option to run")


def pytest_collection_modifyitems(items, config):
    """Deselect tests marked as slow if --slow is set."""
    if config.option.slow:
        return

    selected_items = []
    deselected_items = []

    for item in items:
        if item.get_closest_marker("slow"):
            deselected_items.append(item)
        else:
            selected_items.append(item)

    config.hook.pytest_deselected(items=deselected_items)
    items[:] = selected_items


class Turtle:
    """Plugin for adding markers to slow running tests."""

    def __init__(self, config):
        self._config = config
        self._durations = defaultdict(dict)
        self._durations.update(
            self._config.cache.get("cache/turtle", defaultdict(dict))
        )
        self._slow = 5.0

    def pytest_runtest_logreport(self, report):
        self._durations[report.nodeid][report.when] = report.duration

    @pytest.mark.tryfirst
    def pytest_collection_modifyitems(self, session, config, items):
        for item in items:
            duration = sum(self._durations[item.nodeid].values())
            if duration > self._slow:
                item.add_marker(pytest.mark.turtle)

    def pytest_sessionfinish(self, session):
        cached_durations = self._config.cache.get("cache/turtle", defaultdict(dict))
        cached_durations.update(self._durations)
        self._config.cache.set("cache/turtle", cached_durations)

    def pytest_configure(self, config):
        config.addinivalue_line("markers", "turtle: marker for slow running tests")


class Owl:
    """Plugin for running tests using a specific fixture."""

    def __init__(self, config):
        self._config = config

    def pytest_collection_modifyitems(self, items, config):
        if not config.option.owl:
            return

        selected_items = []
        deselected_items = []

        for item in items:
            if config.option.owl in getattr(item, "fixturenames", ()):
                selected_items.append(item)
            else:
                deselected_items.append(item)

        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items


def pytest_configure(config):
    config.pluginmanager.register(Turtle(config), "turtle")
    config.pluginmanager.register(Owl(config), "owl")
