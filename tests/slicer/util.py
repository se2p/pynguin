#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

import importlib.util
import threading
from types import CodeType

from bytecode import BasicBlock, Instr

import pynguin.configuration as config
from pynguin.instrumentation.instrumentation import (
    CheckedCoverageInstrumentation,
    InstrumentationTransformer,
)
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.slicer.dynamicslicer import DynamicSlicer, SlicingCriterion
from pynguin.slicer.executionflowbuilder import UniqueInstruction
from pynguin.testcase.execution import ExecutionTracer

dummy_code_object = CodeType(0, 0, 0, 0, 0, 0, bytes(), (), (), (), "", "", 0, bytes())


def compare(dynamic_slice: list[UniqueInstruction], expected_slice: list[Instr]):
    expected_copy = expected_slice.copy()
    slice_copy = dynamic_slice.copy()

    for unique_instr in dynamic_slice:
        if (
            isinstance(unique_instr.arg, BasicBlock)
            or isinstance(unique_instr.arg, CodeType)
            or isinstance(unique_instr.arg, tuple)
        ):
            # Don't distinguish arguments for basic blocks, code objects and tuples
            jump_instr = _contains_name_argtype(expected_copy, unique_instr)
            try:
                expected_copy.remove(jump_instr)
                slice_copy.remove(unique_instr)
            except ValueError:
                msg = str(unique_instr) + " not in expected slice\n"
                msg += "Remaining in expected: " + str(expected_copy) + "\n"
                msg += "Remaining in computed: " + str(slice_copy)
                raise ValueError(msg)
        else:
            found_instr = _contains_name_arg(expected_slice, unique_instr)
            if found_instr:
                try:
                    expected_copy.remove(found_instr)
                    slice_copy.remove(unique_instr)
                except ValueError:
                    msg = str(found_instr) + " not in expected slice\n"
                    msg += "Remaining in expected: " + str(expected_copy) + "\n"
                    msg += "Remaining in computed: " + str(slice_copy)
                    raise ValueError(msg)
            else:
                msg = str(unique_instr) + " not in expected slice\n"
                msg += "Remaining in expected: " + str(expected_copy) + "\n"
                msg += "Remaining in computed: " + str(slice_copy)
                raise ValueError(msg)

    if len(expected_copy) != 0:
        raise ValueError("Expected slice has remaining instructions:", expected_copy)
    if len(slice_copy) != 0:
        raise ValueError("Real slice has remaining instructions:", slice_copy)

    return True


def _contains_name_arg(
    instr_list: list[Instr], unique_instr: UniqueInstruction
) -> Instr | None:
    for instr in instr_list:
        if instr.name == unique_instr.name:
            if isinstance(unique_instr.arg, BasicBlock) or isinstance(
                unique_instr.arg, CodeType
            ):
                # Instruction is a jump to a basic block
                return instr
            elif isinstance(unique_instr.arg, tuple) and isinstance(instr.arg, tuple):
                for elem in unique_instr.arg:
                    if elem not in instr.arg:
                        break
                return instr
            elif instr.arg == unique_instr.arg:
                return instr
    return None


def _contains_name_argtype(
    instr_list: list[Instr], unique_instr: UniqueInstruction
) -> Instr | None:
    for instr in instr_list:
        if instr.name == unique_instr.name:
            if isinstance(instr.arg, type(unique_instr.arg)):
                return instr
    return None


def slice_function_at_return(function: callable) -> list[UniqueInstruction]:
    tracer = ExecutionTracer()
    instrumentation = CheckedCoverageInstrumentation(tracer)
    instrumentation_transformer = InstrumentationTransformer(tracer, [instrumentation])

    function.__code__ = instrumentation_transformer.instrument_module(function.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    function()

    trace = tracer.get_trace()
    known_code_objects = tracer.get_known_data().existing_code_objects
    dynamic_slicer = DynamicSlicer(known_code_objects)

    last_traced_instr = trace.executed_instructions[-1]
    slicing_instruction = UniqueInstruction(
        last_traced_instr.file,
        last_traced_instr.name,
        last_traced_instr.code_object_id,
        last_traced_instr.node_id,
        known_code_objects.get(last_traced_instr.code_object_id),
        last_traced_instr.offset,
        lineno=last_traced_instr.lineno,
    )
    slicing_criterion = SlicingCriterion(
        slicing_instruction, len(trace.executed_instructions) - 2
    )
    return dynamic_slicer.slice(
        trace,
        slicing_criterion,
    )


def slice_module_at_return(module_name: str) -> list[UniqueInstruction]:
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)
        module.func()

        trace = tracer.get_trace()
        known_code_objects = tracer.get_known_data().existing_code_objects

        assert known_code_objects
        dynamic_slicer = DynamicSlicer(known_code_objects)
        assert trace.executed_instructions
        last_traced_instr = trace.executed_instructions[-1]
        slicing_instruction = UniqueInstruction(
            last_traced_instr.file,
            last_traced_instr.name,
            last_traced_instr.code_object_id,
            last_traced_instr.node_id,
            known_code_objects.get(last_traced_instr.code_object_id),
            last_traced_instr.offset,
            lineno=last_traced_instr.lineno,
        )
        slicing_criterion = SlicingCriterion(
            slicing_instruction,
            len(trace.executed_instructions) - 2,
        )
        return dynamic_slicer.slice(trace, slicing_criterion)
