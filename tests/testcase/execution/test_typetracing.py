#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast
from typing import cast

import pytest

from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.analyses.typesystem import NoneType, UnionType
from pynguin.testcase.execution import (
    ExecutionTracer,
    ReturnTypeObserver,
    TestCaseExecutor,
    TypeTracingObserver,
    TypeTracingTestCaseExecutor,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)


@pytest.mark.parametrize(
    "test_func,return_type",
    [
        ("return_tuple", tuple[int, int]),
        ("return_list", list[int]),
        ("return_dict", dict[str, int]),
        ("return_set", set[str]),
        ("return_int", int),
        ("return_none", type(None)),
    ],
)
def test_type_reconstruction(test_func, return_type):
    test_cluster = generate_test_cluster("tests.fixtures.type_tracing.return_types")
    executor = TestCaseExecutor(ExecutionTracer())
    visitor = AstToTestCaseTransformer(test_cluster, False, EmptyConstantProvider())
    visitor.visit(
        ast.parse("def test_case():\n   var_0 = module_0." + test_func + "()")
    )
    test_case = visitor.testcases[0]
    observer = ReturnTypeObserver(test_cluster)
    executor.add_observer(observer)
    result = executor.execute(test_case)
    assert result.proper_return_type_trace[
        0
    ] == test_cluster.type_system.convert_type_hint(return_type)


def test_type_tracing_observer_separate_proxies_for_args():
    test_cluster = generate_test_cluster("tests.fixtures.type_tracing.guess_params")
    visitor = AstToTestCaseTransformer(test_cluster, False, EmptyConstantProvider())
    visitor.visit(
        ast.parse(
            "def test_case():\n"
            "    int_0 = 0\n"
            "    var_0 = module_0.foo(int_0, int_0, int_0)"
        )
    )
    test_case = visitor.testcases[0]
    executor = TestCaseExecutor(ExecutionTracer())
    observer = TypeTracingObserver(test_cluster)
    executor.add_observer(observer)
    result = executor.execute(test_case)
    assert {"__rmul__"} == set(result.proxy_knowledge[(1, "a")].children.keys())
    assert {"__radd__"} == set(result.proxy_knowledge[(1, "b")].children.keys())
    assert {"__truediv__"} == set(result.proxy_knowledge[(1, "c")].children.keys())


def test_type_tracing_test_case_executor_integration():
    test_cluster = generate_test_cluster("tests.fixtures.type_tracing.guess_params")
    visitor = AstToTestCaseTransformer(test_cluster, False, EmptyConstantProvider())
    visitor.visit(
        ast.parse(
            "def test_case():\n"
            "    int_0 = 0\n"
            "    var_0 = module_0.foo(int_0, int_0, int_0)"
        )
    )
    test_case = visitor.testcases[0]
    executor = TestCaseExecutor(ExecutionTracer())
    t_executor = TypeTracingTestCaseExecutor(executor, test_cluster)
    t_executor.execute(test_case)
    acc = cast(
        GenericCallableAccessibleObject,
        test_cluster.accessible_objects_under_test[0],
    )
    assert "__rmul__" in acc.inferred_signature.usage_trace["a"].children
    assert int in acc.inferred_signature.usage_trace["a"].type_checks
    assert acc.inferred_signature.return_type == UnionType((NoneType(),))
