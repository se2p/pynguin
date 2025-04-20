#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

import importlib.util
import threading

from types import CodeType

from bytecode import BasicBlock
from bytecode import Instr

import pynguin.configuration as config

from pynguin.instrumentation.instrumentation import CheckedCoverageInstrumentation
from pynguin.instrumentation.instrumentation import InstrumentationTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.slicer.dynamicslicer import DynamicSlicer
from pynguin.slicer.dynamicslicer import SlicingCriterion
from pynguin.slicer.executionflowbuilder import UniqueInstruction


dummy_code_object = CodeType(0, 0, 0, 0, 0, 0, b"", (), (), (), "", "", 0, b"")


def compare(dynamic_slice: list[UniqueInstruction], expected_slice: list[Instr]):
    expected_copy = expected_slice.copy()
    slice_copy = dynamic_slice.copy()

    for unique_instr in dynamic_slice:
        if isinstance(unique_instr.arg, BasicBlock | CodeType | tuple):
            # Don't distinguish arguments for basic blocks, code objects and tuples
            jump_instr = _contains_name_argtype(expected_copy, unique_instr)
            try:
                expected_copy.remove(jump_instr)
                slice_copy.remove(unique_instr)
            except ValueError as err:  # pragma: no cover
                msg = str(unique_instr) + " not in expected slice\n"
                msg += "Remaining in expected: " + str(expected_copy) + "\n"
                msg += "Remaining in computed: " + str(slice_copy)
                raise ValueError(msg) from err
        else:
            found_instr = _contains_name_arg(expected_slice, unique_instr)
            if found_instr:
                try:
                    expected_copy.remove(found_instr)
                    slice_copy.remove(unique_instr)
                except ValueError as err:  # pragma: no cover
                    msg = str(found_instr) + " not in expected slice\n"
                    msg += "Remaining in expected: " + str(expected_copy) + "\n"
                    msg += "Remaining in computed: " + str(slice_copy)
                    raise ValueError(msg) from err
            else:  # pragma: no cover
                msg = str(unique_instr) + " not in expected slice\n"
                msg += "Remaining in expected: " + str(expected_copy) + "\n"
                msg += "Remaining in computed: " + str(slice_copy)
                raise ValueError(msg)

    if len(expected_copy) != 0:
        raise ValueError(
            "Expected slice has remaining instructions:", expected_copy
        )  # pragma: no cover
    if len(slice_copy) != 0:
        raise ValueError("Real slice has remaining instructions:", slice_copy)  # pragma: no cover

    return True


def _contains_name_arg(instr_list: list[Instr], unique_instr: UniqueInstruction) -> Instr | None:
    for instr in instr_list:
        if instr.name == unique_instr.name:
            if isinstance(unique_instr.arg, BasicBlock | CodeType):
                # Instruction is a jump to a basic block
                return instr  # pragma: no cover
            if isinstance(unique_instr.arg, tuple) and isinstance(instr.arg, tuple):
                for elem in unique_instr.arg:  # pragma: no cover
                    if elem not in instr.arg:
                        break
                return instr  # pragma: no cover
            if instr.arg == unique_instr.arg:
                return instr
    return None  # pragma: no cover


def _contains_name_argtype(
    instr_list: list[Instr], unique_instr: UniqueInstruction
) -> Instr | None:
    for instr in instr_list:
        if instr.name == unique_instr.name and isinstance(instr.arg, type(unique_instr.arg)):
            return instr
    return None  # pragma: no cover


def slice_function_at_return(function: callable) -> list[UniqueInstruction]:
    tracer = ExecutionTracer()
    instrumentation = CheckedCoverageInstrumentation(tracer)
    instrumentation_transformer = InstrumentationTransformer(tracer, [instrumentation])

    function.__code__ = instrumentation_transformer.instrument_module(function.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    function()

    trace = tracer.get_trace()
    known_code_objects = tracer.get_subject_properties().existing_code_objects
    dynamic_slicer = DynamicSlicer(known_code_objects)

    last_traced_instr = trace.executed_instructions[-1]
    slicing_instruction = UniqueInstruction(
        file=last_traced_instr.file,
        name=last_traced_instr.name,
        code_object_id=last_traced_instr.code_object_id,
        node_id=last_traced_instr.node_id,
        code_meta=known_code_objects.get(last_traced_instr.code_object_id),
        offset=last_traced_instr.offset,
        lineno=last_traced_instr.lineno,
    )
    slicing_criterion = SlicingCriterion(slicing_instruction, len(trace.executed_instructions) - 2)
    return dynamic_slicer.slice(
        trace,
        slicing_criterion,
    )


def slice_module_at_return(module_name: str) -> list[UniqueInstruction]:
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)
        module.func()

        trace = tracer.get_trace()
        known_code_objects = tracer.get_subject_properties().existing_code_objects

        assert known_code_objects
        dynamic_slicer = DynamicSlicer(known_code_objects)
        assert trace.executed_instructions
        last_traced_instr = trace.executed_instructions[-1]
        slicing_instruction = UniqueInstruction(
            file=last_traced_instr.file,
            name=last_traced_instr.name,
            code_object_id=last_traced_instr.code_object_id,
            node_id=last_traced_instr.node_id,
            code_meta=known_code_objects.get(last_traced_instr.code_object_id),
            offset=last_traced_instr.offset,
            lineno=last_traced_instr.lineno,
        )
        slicing_criterion = SlicingCriterion(
            slicing_instruction,
            len(trace.executed_instructions) - 2,
        )
        return dynamic_slicer.slice(trace, slicing_criterion)
