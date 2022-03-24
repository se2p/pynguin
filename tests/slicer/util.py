#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

import importlib.util
import py_compile
import threading
from types import CodeType

from bytecode import BasicBlock, Instr

from pynguin.instrumentation.instrumentation import (
    CheckedCoverageInstrumentation,
    InstrumentationTransformer,
)
from pynguin.slicer.dynamicslicer import DynamicSlice, DynamicSlicer, SlicingCriterion
from pynguin.slicer.instruction import UniqueInstruction
from pynguin.testcase.execution import ExecutionTrace, ExecutionTracer
from pynguin.utils.pyc import Pyc

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


def slice_function_at_return(function: callable) -> DynamicSlice:
    # Setup
    tracer = ExecutionTracer()
    instrumentation = CheckedCoverageInstrumentation(tracer)
    instrumentation_transformer = InstrumentationTransformer(tracer, [instrumentation])

    # Instrument and call example function
    function.__code__ = instrumentation_transformer.instrument_module(function.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    function()

    # Slice
    trace = tracer.get_trace()
    known_code_objects = tracer.get_known_data().existing_code_objects
    dynamic_slicer = DynamicSlicer(trace, known_code_objects)

    # Slicing criterion at return instruction
    last_traced_instr = trace.executed_instructions[-1]
    slicing_instruction = UniqueInstruction(
        last_traced_instr.file,
        last_traced_instr.name,
        lineno=last_traced_instr.lineno,
        code_object_id=last_traced_instr.code_object_id,
        node_id=last_traced_instr.node_id,
        code_meta=known_code_objects.get(last_traced_instr.code_object_id),
        offset=last_traced_instr.offset,
    )
    slicing_criterion = SlicingCriterion(slicing_instruction)
    dynamic_slice = dynamic_slicer.slice(
        trace, slicing_criterion, len(trace.executed_instructions) - 2
    )

    return dynamic_slice


def slice_module_at_return(module_file: str) -> DynamicSlice:
    compiled_file = py_compile.compile(module_file)

    pyc_file = Pyc(compiled_file)
    module_code = pyc_file.get_code_object()

    # Setup
    tracer = ExecutionTracer()
    instrumentation = CheckedCoverageInstrumentation(tracer)
    instrumentation_transformer = InstrumentationTransformer(tracer, [instrumentation])

    # Instrument and call module
    instr_module = instrumentation_transformer.instrument_module(module_code)
    pyc_file.set_code_object(instr_module)
    pyc_file.overwrite()
    tracer.reset()
    tracer.current_test = instr_module.co_name

    spec = importlib.util.spec_from_file_location(module_file[:-3], module_file)
    example_module = importlib.util.module_from_spec(spec)
    # noinspection PyUnresolvedReferences
    spec.loader.exec_module(example_module)

    # Slice
    trace = tracer.get_trace()
    known_code_objects = tracer.get_known_data().existing_code_objects
    dynamic_slicer = DynamicSlicer(trace, known_code_objects)
    checked_trace = ExecutionTrace()

    # Slicing criterion at foo
    last_traced_instr = trace.executed_instructions[-1]
    slicing_instruction = UniqueInstruction(
        last_traced_instr.file,
        last_traced_instr.name,
        lineno=last_traced_instr.lineno,
        code_object_id=last_traced_instr.code_object_id,
        node_id=last_traced_instr.node_id,
        code_meta=known_code_objects.get(last_traced_instr.code_object_id),
        offset=last_traced_instr.offset,
    )
    slicing_criterion = SlicingCriterion(
        slicing_instruction, global_variables={("result", last_traced_instr.file)}
    )
    dynamic_slice = dynamic_slicer.slice(
        checked_trace, slicing_criterion, len(trace.executed_instructions) - 2
    )

    py_compile.compile(module_file, cfile=compiled_file)

    return dynamic_slice


def instrument_module(module_file: str):
    compiled_file = py_compile.compile(module_file)

    pyc_file = Pyc(compiled_file)
    module_code = pyc_file.get_code_object()

    # Setup
    tracer = ExecutionTracer()
    instrumentation = CheckedCoverageInstrumentation(tracer)
    instrumentation_transformer = InstrumentationTransformer(tracer, [instrumentation])

    # Instrument and call module
    instr_module = instrumentation_transformer.instrument_module(module_code)
    pyc_file.set_code_object(instr_module)
    pyc_file.overwrite()


def compile_module(module_file: str) -> str:
    return py_compile.compile(module_file)
