# This file is part of the Pynguin automated unit test generation framework.
# Copyright (C) 2019–2026 Pynguin Contributors
# SPDX-License-Identifier: MIT

"""Integration tests for excluding TYPE_CHECKING blocks from instrumentation and coverage."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pynguin.instrumentation.machinery import InstrumentationTransformer
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.instrumentation.version import (
    BranchCoverageInstrumentation,
    LineCoverageInstrumentation,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def subject_properties() -> SubjectProperties:
    """Fixture providing a fresh SubjectProperties instance.

    Returns:
        A new SubjectProperties object.
    """
    return SubjectProperties()


def test_type_checking_blocks_excluded_from_instrumentation(
    subject_properties: SubjectProperties,
    tmp_path: Path,
) -> None:
    """Verify that TYPE_CHECKING guards, stubs, and decorated functions are not instrumented.

    Args:
        subject_properties: The SubjectProperties fixture.
        tmp_path: Pytest temporary directory fixture.
    """
    source = (
        "from typing import TYPE_CHECKING, overload\n"  # 1
        "import typing as t\n"  # 2
        "import typing_extensions as te\n"  # 3
        "\n"  # 4
        "if TYPE_CHECKING:\n"  # 5
        "    from foo import Bar\n"  # 6
        "    def stub_func(x: int) -> int:\n"  # 7
        "        if x > 0:\n"  # 8
        "            return 1\n"  # 9
        "        return 0\n"  # 10
        "\n"  # 11
        "if t.TYPE_CHECKING:\n"  # 12
        "    @overload\n"  # 13
        "    def overloaded(val: int) -> int:\n"  # 14
        "        if val > 10:\n"  # 15
        "            return val\n"  # 16
        "        return 0\n"  # 17
        "\n"  # 18
        "if te.TYPE_CHECKING:\n"  # 19
        "    class TypeStub:\n"  # 20
        "        def stub_method(self) -> None:\n"  # 21
        "            pass\n"  # 22
        "\n"  # 23
        "if TYPE_CHECKING:\n"  # 24
        "    ResolvedType = int\n"  # 25
        "else:\n"  # 26
        "    flag = bool(1)\n"  # 27
        "    if flag:\n"  # 28
        "        ResolvedType = str\n"  # 29
        "    else:\n"  # 30
        "        ResolvedType = bytes\n"  # 31
        "\n"  # 32
        "def runtime_function(x: int) -> int:\n"  # 33
        "    if x > 0:\n"  # 34
        "        return x\n"  # 35
        "    return -x\n"  # 36
    )
    test_file = tmp_path / "type_checking_module.py"
    test_file.write_text(source)

    line_instr = LineCoverageInstrumentation(subject_properties)
    branch_instr = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [line_instr, branch_instr])

    code = compile(source, str(test_file), "exec")
    transformer.instrument_code(code)

    registered_lines = {
        meta.line_number
        for meta in subject_properties.existing_lines.values()
        if isinstance(meta.line_number, int)
    }

    # Lines inside if TYPE_CHECKING: must NOT be registered as line coverage goals
    type_checking_lines = set(range(5, 11)) | set(range(12, 18)) | set(range(19, 23)) | {24, 25}
    assert registered_lines.isdisjoint(type_checking_lines)

    # Runtime lines must be registered as line coverage goals
    assert 27 in registered_lines
    assert 28 in registered_lines
    assert 29 in registered_lines
    assert 31 in registered_lines
    assert 33 in registered_lines
    assert 34 in registered_lines
    assert 35 in registered_lines
    assert 36 in registered_lines

    # Predicates inside if TYPE_CHECKING: (e.g. line 8, 15) and TYPE_CHECKING itself (5, 12, 19, 24)
    # must NOT be registered as branch coverage goals
    predicate_lines = {
        meta.line_no
        for pid, meta in subject_properties.existing_predicates.items()
        if pid in subject_properties.coverage_predicates
    }
    assert predicate_lines.isdisjoint(type_checking_lines)

    # Predicates in runtime code (line 28 in else, line 34 in runtime_function) must be goals
    assert 28 in predicate_lines
    assert 34 in predicate_lines

    # Stubs inside TYPE_CHECKING must not be registered as code objects
    code_object_names = {
        meta.code_object.co_name for meta in subject_properties.existing_code_objects.values()
    }
    assert "stub_func" not in code_object_names
    assert "overloaded" not in code_object_names
    assert "TypeStub" not in code_object_names
    assert "stub_method" not in code_object_names

    # Runtime code objects must be registered
    assert "runtime_function" in code_object_names


def test_type_checking_runtime_execution_coverage(
    subject_properties: SubjectProperties,
    tmp_path: Path,
) -> None:
    """Verify that executing instrumented module with TYPE_CHECKING tracks coverage cleanly.

    Args:
        subject_properties: The SubjectProperties fixture.
        tmp_path: Pytest temporary directory fixture.
    """
    source = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from typing import Sequence\n"
        "    def stub() -> None:\n"
        "        pass\n"
        "else:\n"
        "    Sequence = list\n"
        "\n"
        "def compute(val: int) -> int:\n"
        "    if val > 0:\n"
        "        return val * 2\n"
        "    return 0\n"
    )
    test_file = tmp_path / "runtime_type_checking.py"
    test_file.write_text(source)

    line_instr = LineCoverageInstrumentation(subject_properties)
    branch_instr = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(subject_properties, [line_instr, branch_instr])

    code = compile(source, str(test_file), "exec")
    instrumented_code = transformer.instrument_code(code)

    module_scope: dict[str, object] = {}
    with subject_properties.instrumentation_tracer:
        exec(instrumented_code, module_scope)  # noqa: S102
        compute_fn = module_scope["compute"]
        assert callable(compute_fn)
        compute_fn(5)
        compute_fn(-1)

    trace = subject_properties.instrumentation_tracer.get_trace()
    subject_properties.validate_execution_trace(trace)

    # Both true and false branches of compute's if val > 0 should be covered
    compute_predicates = [
        pid for pid, meta in subject_properties.existing_predicates.items() if meta.line_no == 10
    ]
    assert len(compute_predicates) == 1
    pred_id = compute_predicates[0]
    assert (pred_id, 0.0) in trace.true_distances.items()
    assert (pred_id, 0.0) in trace.false_distances.items()
