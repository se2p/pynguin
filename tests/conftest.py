#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import importlib
import inspect
import sys
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from bytecode import Bytecode, Instr, Label
from dotenv import load_dotenv

import pynguin.assertion.assertion as ass
import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao
import pynguin.utils.statistics.stats as stat
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import ModuleTestCluster, generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.analyses.typesystem import InferredSignature, Instance, NoneType, TypeInfo, TypeSystem
from pynguin.instrumentation.controlflow import CFG, BasicBlockNode
from pynguin.instrumentation.tracer import ExecutionTrace, SubjectProperties
from pynguin.testcase.execution import ExecutionResult, TestCaseExecutor
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericField,
    GenericFunction,
    GenericMethod,
)
from tests.fixtures.accessibles.accessible import SomeType, simple_function

# -- FIXTURES --------------------------------------------------------------------------
from tests.fixtures.linecoverage.list import ListTest
from tests.fixtures.linecoverage.plus import Plus

load_dotenv()


@pytest.fixture(autouse=True)
def reset_configuration():
    """Automatically reset the configuration singleton."""
    config.configuration = config.Configuration(
        algorithm=config.Algorithm.RANDOM,
        project_path="",
        test_case_output=config.TestCaseOutputConfiguration(output_path=""),
        module_name="",
    )
    # Easier to put this here than to have it scattered in all tests.
    config.configuration.test_creation.none_weight = 0
    config.configuration.test_creation.any_weight = 0
    config.configuration.test_creation.use_random_object_for_call = 0.0


@pytest.fixture
def test_case_mock():
    return MagicMock(tc.TestCase)


@pytest.fixture
def default_test_case():
    return dtc.DefaultTestCase(ModuleTestCluster(0))


@pytest.fixture
def variable_reference_mock():
    return MagicMock(vr.Reference)


@pytest.fixture(scope="session")
def provide_imported_modules() -> dict[str, Any]:
    module_names = [
        "tests.fixtures.examples.basket",
        "tests.fixtures.examples.dummies",
        "tests.fixtures.examples.monkey",
        "tests.fixtures.examples.private_methods",
        "tests.fixtures.examples.triangle",
    ]
    return {m.split(".")[-1]: importlib.import_module(m) for m in module_names}


@pytest.fixture(scope="session")
def provide_callables_from_fixtures_modules(
    provide_imported_modules,
) -> dict[str, Callable]:
    def inspect_member(member):
        return inspect.isclass(member) or inspect.ismethod(member) or inspect.isfunction(member)

    members = []
    for module in provide_imported_modules.values():
        for member in inspect.getmembers(module, inspect_member):
            members.append(member)  # noqa: PERF402
    return dict(members)


@pytest.fixture
def constructor_mock(type_system) -> GenericConstructor:
    return GenericConstructor(
        owner=TypeInfo(SomeType),
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
            original_return_type=NoneType(),
            original_parameters={"y": Instance(TypeInfo(float))},
            type_system=type_system,
        ),
    )


@pytest.fixture
def method_mock(type_system) -> GenericMethod:
    return GenericMethod(
        owner=TypeInfo(SomeType),
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
            original_return_type=Instance(TypeInfo(float)),
            original_parameters={"x": Instance(TypeInfo(int))},
            type_system=type_system,
        ),
    )


@pytest.fixture
def function_mock(type_system) -> GenericFunction:
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
            original_return_type=Instance(TypeInfo(float)),
            original_parameters={"z": Instance(TypeInfo(float))},
            type_system=type_system,
        ),
    )


@pytest.fixture
def lambda_mock(type_system) -> GenericFunction:
    # NOTE: module.py changes the lambda name, so we assume that at this point they are
    # already renamed
    just_z = lambda z: z  # noqa: E731
    just_z.__name__ = "just_z"
    return GenericFunction(
        function=just_z,
        inferred_signature=InferredSignature(
            signature=inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        name="z",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=int,
                    ),
                ]
            ),
            original_return_type=Instance(TypeInfo(int)),
            original_parameters={"z": Instance(TypeInfo(int))},
            type_system=type_system,
        ),
    )


weighted_avg = lambda x, y, w1, w2: (x * w1 + y * w2) / (w1 + w2)  # noqa: E731


@pytest.fixture
def lambda_mock_complex(type_system) -> GenericFunction:
    # NOTE: module.py changes the lambda name, so we assume that at this point they are
    # already renamed
    weighted_avg.__name__ = "weighted_avg"
    return GenericFunction(
        function=weighted_avg,
        inferred_signature=InferredSignature(
            signature=inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        name="x",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=complex,
                    ),
                    inspect.Parameter(
                        name="y",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=complex,
                    ),
                    inspect.Parameter(
                        name="w1",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=float,
                    ),
                    inspect.Parameter(
                        name="w2",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=float,
                    ),
                ]
            ),
            original_return_type=Instance(TypeInfo(complex)),
            original_parameters={
                "x": Instance(TypeInfo(complex)),
                "y": Instance(TypeInfo(complex)),
                "w1": Instance(TypeInfo(float)),
                "w2": Instance(TypeInfo(float)),
            },
            type_system=type_system,
        ),
    )


@pytest.fixture
def field_mock() -> GenericField:
    return GenericField(owner=TypeInfo(SomeType), field="y", field_type=Instance(TypeInfo(float)))


@pytest.fixture
def type_system():
    return TypeSystem()


@pytest.fixture
def short_test_case(constructor_mock):
    test_case = dtc.DefaultTestCase(ModuleTestCluster(0))
    int_stmt = stmt.IntPrimitiveStatement(test_case, 5)
    constructor_stmt = stmt.ConstructorStatement(
        test_case, constructor_mock, {"y": int_stmt.ret_val}
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_stmt)
    return test_case


@pytest.fixture(autouse=True)
def reset_statistics_tracker():
    stat.reset()


if sys.version_info >= (3, 14):

    @pytest.fixture(scope="module")
    def conditional_jump_example_bytecode() -> Bytecode:
        label_else = Label()
        label_print = Label()
        return Bytecode([
            Instr("LOAD_NAME", "print"),
            Instr("LOAD_NAME", "test"),
            Instr("POP_JUMP_IF_FALSE", label_else),
            Instr("LOAD_CONST", "yes"),
            Instr("JUMP_FORWARD", label_print),
            label_else,
            Instr("LOAD_CONST", "no"),
            label_print,
            Instr("CALL", 1),
            Instr("RETURN_VALUE"),
        ])

elif sys.version_info >= (3, 12):

    @pytest.fixture(scope="module")
    def conditional_jump_example_bytecode() -> Bytecode:
        label_else = Label()
        label_print = Label()
        return Bytecode([
            Instr("LOAD_NAME", "print"),
            Instr("LOAD_NAME", "test"),
            Instr("POP_JUMP_IF_FALSE", label_else),
            Instr("LOAD_CONST", "yes"),
            Instr("JUMP_FORWARD", label_print),
            label_else,
            Instr("LOAD_CONST", "no"),
            label_print,
            Instr("CALL", 1),
            Instr("RETURN_CONST", None),
        ])

elif sys.version_info >= (3, 11):

    @pytest.fixture(scope="module")
    def conditional_jump_example_bytecode() -> Bytecode:
        label_else = Label()
        label_print = Label()
        return Bytecode([
            Instr("LOAD_NAME", "print"),
            Instr("LOAD_NAME", "test"),
            Instr("POP_JUMP_FORWARD_IF_FALSE", label_else),
            Instr("LOAD_CONST", "yes"),
            Instr("JUMP_FORWARD", label_print),
            label_else,
            Instr("LOAD_CONST", "no"),
            label_print,
            Instr("PRECALL", 1),
            Instr("CALL", 1),
            Instr("LOAD_CONST", None),
            Instr("RETURN_VALUE"),
        ])

else:

    @pytest.fixture(scope="module")
    def conditional_jump_example_bytecode() -> Bytecode:
        label_else = Label()
        label_print = Label()
        return Bytecode([
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
        ])


@pytest.fixture(scope="module")
def small_control_flow_graph() -> CFG:
    cfg = CFG(MagicMock())

    n0 = BasicBlockNode(index=0, basic_block=MagicMock())
    n1 = BasicBlockNode(index=1, basic_block=MagicMock())
    n2 = BasicBlockNode(index=2, basic_block=MagicMock())
    n3 = BasicBlockNode(index=3, basic_block=MagicMock())
    n4 = BasicBlockNode(index=4, basic_block=MagicMock())
    n5 = BasicBlockNode(index=5, basic_block=MagicMock())

    cfg.add_node(n0)
    cfg.add_node(n1)
    cfg.add_node(n2)
    cfg.add_node(n3)
    cfg.add_node(n4)
    cfg.add_node(n5)

    cfg.add_edge(n0, n5)
    cfg.add_edge(n5, n4)
    cfg.add_edge(n4, n3)
    cfg.add_edge(n4, n2)
    cfg.add_edge(n3, n1)
    cfg.add_edge(n2, n1)

    CFG._insert_dummy_nodes(cfg)

    return cfg


@pytest.fixture(scope="module")
def yield_control_flow_graph() -> CFG:
    cfg = CFG(MagicMock())

    y_assign_0_node = BasicBlockNode(index=0, basic_block=MagicMock())
    y_eq_0_node = BasicBlockNode(index=1, basic_block=MagicMock())
    yield_y_node = BasicBlockNode(index=2, basic_block=MagicMock())  # yield_y_node, 2
    jmp_node = BasicBlockNode(index=3, basic_block=MagicMock())

    cfg.add_node(y_assign_0_node)
    cfg.add_node(y_eq_0_node)
    cfg.add_node(yield_y_node)
    cfg.add_node(jmp_node)

    cfg.add_edge(y_assign_0_node, y_eq_0_node)
    cfg.add_edge(y_eq_0_node, yield_y_node, label="True")
    cfg.add_edge(y_eq_0_node, jmp_node, label="False")
    cfg.add_edge(yield_y_node, jmp_node)

    CFG._insert_dummy_nodes(cfg)

    return cfg


@pytest.fixture(scope="module")
def larger_control_flow_graph() -> CFG:  # noqa: PLR0914, PLR0915
    cfg = CFG(MagicMock())

    n_1 = BasicBlockNode(index=1, basic_block=MagicMock())
    n_2 = BasicBlockNode(index=2, basic_block=MagicMock())
    n_3 = BasicBlockNode(index=3, basic_block=MagicMock())
    n_5 = BasicBlockNode(index=5, basic_block=MagicMock())
    n_100 = BasicBlockNode(index=100, basic_block=MagicMock())
    n_110 = BasicBlockNode(index=110, basic_block=MagicMock())
    n_120 = BasicBlockNode(index=120, basic_block=MagicMock())
    n_130 = BasicBlockNode(index=130, basic_block=MagicMock())
    n_140 = BasicBlockNode(index=140, basic_block=MagicMock())
    n_150 = BasicBlockNode(index=150, basic_block=MagicMock())
    n_160 = BasicBlockNode(index=160, basic_block=MagicMock())
    n_170 = BasicBlockNode(index=170, basic_block=MagicMock())
    n_180 = BasicBlockNode(index=180, basic_block=MagicMock())
    n_190 = BasicBlockNode(index=190, basic_block=MagicMock())
    n_200 = BasicBlockNode(index=200, basic_block=MagicMock())
    n_210 = BasicBlockNode(index=210, basic_block=MagicMock())
    n_300 = BasicBlockNode(index=300, basic_block=MagicMock())

    cfg.add_node(n_1)
    cfg.add_node(n_2)
    cfg.add_node(n_3)
    cfg.add_node(n_5)
    cfg.add_node(n_100)
    cfg.add_node(n_110)
    cfg.add_node(n_120)
    cfg.add_node(n_130)
    cfg.add_node(n_140)
    cfg.add_node(n_150)
    cfg.add_node(n_160)
    cfg.add_node(n_170)
    cfg.add_node(n_180)
    cfg.add_node(n_190)
    cfg.add_node(n_200)
    cfg.add_node(n_210)
    cfg.add_node(n_300)

    cfg.add_edge(n_1, n_2)
    cfg.add_edge(n_2, n_3)
    cfg.add_edge(n_3, n_5)
    cfg.add_edge(n_5, n_100)
    cfg.add_edge(n_100, n_110)
    cfg.add_edge(n_110, n_120, label="true")
    cfg.add_edge(n_120, n_130)
    cfg.add_edge(n_130, n_140)
    cfg.add_edge(n_140, n_150, label="true")
    cfg.add_edge(n_150, n_160)
    cfg.add_edge(n_160, n_170, label="false")
    cfg.add_edge(n_170, n_180)
    cfg.add_edge(n_180, n_190)
    cfg.add_edge(n_160, n_190, label="true")
    cfg.add_edge(n_190, n_140)
    cfg.add_edge(n_140, n_200, label="false")
    cfg.add_edge(n_200, n_210)
    cfg.add_edge(n_210, n_110)
    cfg.add_edge(n_110, n_300, label="false")

    CFG._insert_dummy_nodes(cfg)

    return cfg


@pytest.fixture
def plus_test_with_object_assertion() -> tc.TestCase:
    """Generated testcase.

    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(var_0)
    assert int_1 == 46.
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]
    test_case.statements[-1].add_assertion(
        ass.ObjectAssertion(test_case.statements[-1].ret_val, 46)
    )
    return test_case


@pytest.fixture
def plus_test_with_float_assertion() -> tc.TestCase:
    """Generated testcase.

    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
    assert int_1 == pytest.approx(46, rel=0.01, abs=0.01).
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]
    test_case.statements[-1].add_assertion(ass.FloatAssertion(test_case.statements[-1].ret_val, 46))
    return test_case


@pytest.fixture
def plus_test_with_type_name_assertion() -> tc.TestCase:
    """Generated testcase.

    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
    assert int_1 is not None.
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]

    test_case.statements[-1].add_assertion(
        ass.TypeNameAssertion(test_case.statements[-1].ret_val, "builtins", "int")
    )
    return test_case


@pytest.fixture
def exception_test_with_except_assertion() -> tc.TestCase:
    """Generated testcase.

    exception_test_0 = module_0.ExceptionTest()
    with pytest.raises(RuntimeError):
        var_0 = exception_test_0.throw().
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.exception")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    exception_test_0 = module_0.ExceptionTest()
    var_0 = exception_test_0.throw()
"""
        )
    )
    test_case = transformer.testcases[0]

    test_case.statements[-1].add_assertion(
        ass.ExceptionAssertion(
            module=RuntimeError.__module__,
            exception_type_name=RuntimeError.__name__,
        ),
    )
    return test_case


@pytest.fixture
def list_test_with_len_assertion() -> tc.TestCase:
    """Generated testcase.

    list_test_0 = module_0.ListTest()
    assert len(list_test_0.attribute) == 3.
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.list")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    list_test_0 = module_0.ListTest()
"""
        )
    )
    test_case = transformer.testcases[0]
    test_case.statements[-1].add_assertion(
        ass.CollectionLengthAssertion(
            vr.FieldReference(
                test_case.statements[-1].ret_val,
                gao.GenericField(TypeInfo(ListTest), "attribute", Instance(TypeInfo(list))),
            ),
            3,
        )
    )
    return test_case


@pytest.fixture
def plus_test_with_multiple_assertions():
    """Generated testcase.

    int_0 = 42
    assert int_0 == 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
    assert int_1 == pytest.approx(46, rel=0.01, abs=0.01)
    assert plus_0.calculations == 1.
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]

    test_case.statements[0].add_assertion(ass.ObjectAssertion(test_case.statements[0].ret_val, 42))
    test_case.statements[-1].add_assertion(ass.FloatAssertion(test_case.statements[-1].ret_val, 46))
    test_case.statements[-1].add_assertion(
        ass.ObjectAssertion(
            vr.FieldReference(
                test_case.statements[1].ret_val,
                gao.GenericField(TypeInfo(Plus), "calculations", Instance(TypeInfo(int))),
            ),
            1,
        )
    )
    return test_case


@pytest.fixture
def result() -> ExecutionResult:
    result = ExecutionResult()
    result.num_executed_statements = 1
    return result


@pytest.fixture
def result_mock() -> MagicMock:
    return MagicMock(ExecutionResult)


@pytest.fixture
def subject_properties() -> SubjectProperties:
    return SubjectProperties()


@pytest.fixture
def executor_mock(subject_properties: SubjectProperties) -> MagicMock:
    executor = MagicMock(TestCaseExecutor)
    executor.subject_properties.return_value = subject_properties
    return executor


@pytest.fixture
def execution_trace() -> ExecutionTrace:
    return ExecutionTrace()


# -- CONFIGURATIONS AND EXTENSIONS FOR PYTEST ------------------------------------------
