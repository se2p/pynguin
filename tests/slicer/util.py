#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
from __future__ import annotations

import importlib.util
import sys

from dataclasses import dataclass
from types import CodeType
from typing import TYPE_CHECKING
from typing import Any

from bytecode.cfg import BasicBlock
from bytecode.instr import _UNSET  # noqa: PLC2701
from bytecode.instr import UNSET
from bytecode.instr import CellVar
from bytecode.instr import FreeVar
from bytecode.instr import Instr

import pynguin.configuration as config

from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import CheckedCoverageInstrumentation
from pynguin.slicer.dynamicslicer import DynamicSlicer
from pynguin.slicer.dynamicslicer import SlicingCriterion
from pynguin.slicer.executionflowbuilder import UniqueInstruction


if TYPE_CHECKING:
    from collections.abc import Callable


if sys.version_info >= (3, 11):
    dummy_code_object = CodeType(0, 0, 0, 0, 0, 0, b"", (), (), (), "", "", "", 0, b"", b"")
else:
    dummy_code_object = CodeType(0, 0, 0, 0, 0, 0, b"", (), (), (), "", "", 0, b"")


@dataclass(frozen=True)
class TracedInstr:
    name: str
    arg: int | str | tuple | FreeVar | CellVar | CodeType | TracedInstr | _UNSET | None = UNSET


def assert_slice_equal(current_slice: list[UniqueInstruction], expected_slice: list[TracedInstr]):
    expected_instrs = "\n".join(f"[{i}] {instr}" for i, instr in enumerate(expected_slice))
    current_instrs = "\n".join(
        f"[{i}] {instr.name} {instr.arg}" for i, instr in enumerate(current_slice)
    )
    general_exception_message = (
        f"Expected ({len(expected_slice)}):\n{expected_instrs}\n\n"
        f"Got ({len(current_slice)}):\n{current_instrs}"
    )
    try:
        for i, (current_instr, expected_instr) in enumerate(
            zip(current_slice, expected_slice, strict=True)
        ):
            assert current_instr.name == expected_instr.name, (
                f"Expected {expected_instr.name} instruction at index {i} but got "
                f"{current_instr.name}\n{general_exception_message}"
            )
            match expected_instr.arg:
                case int() | str() | tuple() | FreeVar() | CellVar() | _UNSET() | None:
                    assert current_instr.arg == expected_instr.arg, (
                        f"Expected argument {expected_instr.arg} at index {i} but got "
                        f"{current_instr.arg}\n{general_exception_message}"
                    )
                case CodeType():
                    assert isinstance(current_instr.arg, CodeType), (
                        f"Expected CodeType argument at index {i} but got "
                        f"{current_instr.arg}\n{general_exception_message}"
                    )
                case TracedInstr(name, arg):
                    assert isinstance(current_instr.arg, BasicBlock), (
                        f"Expected BasicBlock argument at index {i} but got "
                        f"{current_instr.arg}\n{general_exception_message}"
                    )
                    current_block_instr = current_instr.arg[0]
                    assert isinstance(current_block_instr, Instr)
                    assert current_block_instr.name == name, (
                        f"Expected {name} first instruction at index {i} but got "
                        f"{current_block_instr.name}\n{general_exception_message}"
                    )
                    match current_block_instr.arg:
                        case int() | str() | tuple() | _UNSET() | None:
                            assert current_block_instr.arg == arg, (
                                f"Expected argument {arg} in first instruction at index {i} "
                                f"but got {current_block_instr.arg}\n{general_exception_message}"
                            )
                        case BasicBlock():
                            assert isinstance(current_block_instr.arg, BasicBlock), (
                                f"Expected BasicBlock argument in first instruction at index {i} "
                                f"but got {current_block_instr.arg}\n{general_exception_message}"
                            )
    except ValueError:
        assert len(current_slice) == len(expected_slice), general_exception_message


def slice_function_at_return_with_result(
    function: Callable[[], Any],
) -> tuple[list[UniqueInstruction], Any]:
    subject_properties = SubjectProperties()
    instrumentation = CheckedCoverageInstrumentation(subject_properties)
    instrumentation_transformer = InstrumentationTransformer(subject_properties, [instrumentation])

    function.__code__ = instrumentation_transformer.instrument_module(function.__code__)

    with subject_properties.instrumentation_tracer:
        result = function()

    trace = subject_properties.instrumentation_tracer.get_trace()
    known_code_objects = subject_properties.existing_code_objects
    dynamic_slicer = DynamicSlicer(known_code_objects)

    last_traced_instr = trace.executed_instructions[-1]
    slicing_instruction = UniqueInstruction(
        file=last_traced_instr.file,
        name=last_traced_instr.name,
        code_object_id=last_traced_instr.code_object_id,
        node_id=last_traced_instr.node_id,
        code_meta=known_code_objects[last_traced_instr.code_object_id],
        instr_original_index=last_traced_instr.instr_original_index,
        lineno=last_traced_instr.lineno,
    )
    slicing_criterion = SlicingCriterion(slicing_instruction, len(trace.executed_instructions) - 2)

    return dynamic_slicer.slice(
        trace,
        slicing_criterion,
    ), result


def slice_function_at_return(function: Callable[[], Any]) -> list[UniqueInstruction]:
    return slice_function_at_return_with_result(function)[0]


def slice_module_at_return(module_name: str) -> list[UniqueInstruction]:
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]
    subject_properties = SubjectProperties()
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)
            module.func()

        trace = subject_properties.instrumentation_tracer.get_trace()
        known_code_objects = subject_properties.existing_code_objects

        assert known_code_objects
        dynamic_slicer = DynamicSlicer(known_code_objects)
        assert trace.executed_instructions
        last_traced_instr = trace.executed_instructions[-1]
        slicing_instruction = UniqueInstruction(
            file=last_traced_instr.file,
            name=last_traced_instr.name,
            code_object_id=last_traced_instr.code_object_id,
            node_id=last_traced_instr.node_id,
            code_meta=known_code_objects[last_traced_instr.code_object_id],
            instr_original_index=last_traced_instr.instr_original_index,
            lineno=last_traced_instr.lineno,
        )
        slicing_criterion = SlicingCriterion(
            slicing_instruction,
            len(trace.executed_instructions) - 2,
        )
        return dynamic_slicer.slice(trace, slicing_criterion)
