#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides byte-code instrumentation mechanisms."""

from __future__ import annotations

import logging

from abc import abstractmethod
from types import CodeType
from typing import TYPE_CHECKING
from typing import Protocol

from bytecode import Bytecode
from bytecode import Instr

from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation import tracer
from pynguin.instrumentation import version


if TYPE_CHECKING:
    from pynguin.analyses.constants import DynamicConstantProvider


class InstrumentationAdapter(Protocol):
    """Protocol for byte-code instrumentation adapters.

    General notes:

    A POP_TOP instruction is required after calling a method, because each method
    implicitly returns None.

    This class defines visit_* methods that are called from the
    InstrumentationTransformer. Each subclass should override the visit_* methods
    where it wants to do something.
    """

    def visit_cfg(self, cfg: cf.CFG, code_object_id: int) -> None:
        """Called when the CFG is visited.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
        """
        return

    def visit_node(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        """Called for each basic block node in the CFG.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
        """
        return


class BranchCoverageInstrumentationAdapter(InstrumentationAdapter):
    """Instruments code objects to enable tracking branch distances.

    This results in branch coverage.
    Currently, we only instrument conditional jumps and for loops.
    """

    @abstractmethod
    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:
        """Initialize the branch coverage instrumentation adapter.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
        """

    @abstractmethod
    def visit_for_loop(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument the for-loops.

        We want to instrument each iteration of the for-loop as well as its natural exit.
        The natural exit is when the for-loop ends because there is nothing left to yield.
        Therefore, it is important to be careful not to trigger the tracer if the loop is exited
        by a break or return statement, as this would prevent us from tracing the natural exits.

        Since Python is a structured programming language, there can be no jumps
        directly into the loop that bypass the loop header (e.g., GOTO).
        Jumps which reach the loop header from outside the loop will still target
        the original loop header, so they don't need to be modified.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the for-loop header.
            instr_index: The index of the instruction in the basic block.
        """

    def visit_none_based_conditional_jump(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument none-based conditional jumps.

        It is only used in Python 3.11 and later versions.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the comparison operation.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_compare_based_conditional_jump(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument compare-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following comparison operation on which the conditional jump is based.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the comparison operation.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_exception_based_conditional_jump(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument exception-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following exception matching case.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the conditional jump.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_bool_based_conditional_jump(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument boolean-based conditional jumps.

        We add a call to the tracer which reports the value on which the conditional
        jump will be based.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction that is the conditional jump.
            instr_index: The index of the instruction in the basic block.
        """


class LineCoverageInstrumentationAdapter(InstrumentationAdapter):
    """Instruments code objects to enable tracking of executed lines.

    This results in line coverage.
    """

    @abstractmethod
    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:
        """Initialize the line coverage instrumentation adapter.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
        """

    @abstractmethod
    def visit_line(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instrument a line.

        We add a call to the tracer which reports a line was executed.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The first instruction of a line.
            instr_index: The index of the instruction in the basic block.
        """


class CheckedCoverageInstrumentationAdapter(InstrumentationAdapter):
    """Instruments code objects to enable tracking of executed instructions.

    Special instructions get instrumented differently to track information
    required to calculate the percentage of instructions in a backward slice for
    an assertion, thus checked coverage.

    We instrument memory accesses, control flow instruction and
    attribute access instructions.

    The instruction number in combination with the line number and the filename can
    uniquely identify the traced instruction in the original basic block. Since
    instructions have a fixed length of two bytes since version 3.6, this is rather
    trivial to keep track of.
    """

    @abstractmethod
    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:
        """Initialize the checked coverage instrumentation adapter.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
        """

    @abstractmethod
    def visit_line(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument a line.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_generic(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument generic instructions.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_local_access(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument local variable accesses.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_attr_access(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument attribute accesses.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_subscr_access(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument subscription accesses.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    def visit_slice_access(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument slice accesses.

        It is only used in Python 3.12 and later versions.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_name_access(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument name accesses.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_import_name_access(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument import name accesses.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_global_access(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument global variable accesses.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_deref_access(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument dereferenced variable accesses.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_jump(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument jump instructions.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_call(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument call instructions.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_return(  # noqa: PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Instrument return instructions.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the basic block.
        """


class DynamicSeedingInstrumentationAdapter(InstrumentationAdapter):
    """Instruments code objects to enable dynamic constant seeding.

    Supported is collecting values of the types int, float and string.

    Instrumented are the common compare operations (==, !=, <, >, <=, >=) and the string
    methods contained in the STRING_FUNCTION_NAMES list. This means, if one of the
    above operations and methods is used in an if-conditional, corresponding values
    are added to the dynamic constant pool.

    The dynamic pool is implemented in the module constantseeding.py. The dynamicseeding
    module contains methods for managing the dynamic pool during the algorithm
    execution.
    """

    @abstractmethod
    def __init__(self, dynamic_constant_provider: DynamicConstantProvider) -> None:
        """Initialize the dynamic seeding instrumentation.

        Args:
            dynamic_constant_provider: The dynamic constant provider that is used to
                manage the dynamic constant pool.
        """

    @abstractmethod
    def visit_compare_op(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the compare operations.

        Stores the values extracted at runtime.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_string_function_without_arg(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the isalnum function.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_startswith_function(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the startswith function.

        Stores for the expression 'string1.startswith(string2)' the value
        'string2 + string1' in the _dynamic_pool.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """

    @abstractmethod
    def visit_endswith_function(
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        """Instruments the endswith function.

        Stores for the expression 'string1.startswith(string2)' the value
        'string1 + string2' in the _dynamic_pool.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction to be instrumented.
            instr_index: The index of the instruction in the basic block.
        """


class InstrumentationTransformer:
    """Applies a given list of instrumentation adapters to code objects.

    This class is responsible for traversing all nested code objects and their
    basic blocks and requesting their instrumentation from the given adapters.

    Ideally we would want something like ASM with nested visitors where changes from
    different adapters don't affect each other, but that's a bit of overkill for now.
    """

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        subject_properties: tracer.SubjectProperties,
        instrumentation_adapters: list[InstrumentationAdapter],
    ):
        """Initialize the instrumentation transformer.

        Args:
            subject_properties: The properties of the subject that is being instrumented.
            instrumentation_adapters: The list of instrumentation adapters that should be used.
        """
        self._subject_properties = subject_properties
        self._instrumentation_adapters = instrumentation_adapters

    @property
    def subject_properties(self) -> tracer.SubjectProperties:
        """Get the subject properties that are used for the instrumentation.

        Returns:
            The subject properties that are used for the instrumentation.
        """
        return self._subject_properties

    def instrument_module(self, module_code: CodeType) -> CodeType:
        """Instrument the given code object of a module.

        Args:
            module_code: The code object of the module

        Returns:
            The instrumented code object of the module
        """
        for metadata in self._subject_properties.existing_code_objects.values():
            if metadata.code_object is module_code or metadata.original_code_object is module_code:
                # Abort instrumentation, since we have already
                # instrumented this code object.
                raise AssertionError("Tried to instrument already instrumented module.")

        return self._instrument_code_recursive(module_code)

    def _instrument_code_recursive(
        self,
        code: CodeType,
        parent_code_object_id: int | None = None,
    ) -> CodeType:
        self._logger.debug("Instrumenting Code Object for %s", code.co_name)

        code_object_id = self._subject_properties.create_code_object_id()

        original_bytecode = version.add_for_loop_no_yield_nodes(Bytecode.from_code(code))

        cfg = cf.CFG.from_bytecode(original_bytecode)

        for adapter in self._instrumentation_adapters:
            adapter.visit_cfg(cfg, code_object_id)

        for node in cfg.basic_block_nodes:
            for adapter in self._instrumentation_adapters:
                adapter.visit_node(cfg, code_object_id, node)

        instrumented_code = cfg.bytecode_cfg.to_code()

        code_object = instrumented_code.replace(
            co_consts=tuple(
                self._instrument_code_recursive(const, code_object_id)
                if isinstance(const, CodeType)
                else const
                for const in instrumented_code.co_consts
            )
        )

        original_cfg = cf.CFG.from_bytecode(original_bytecode)

        original_code_object = original_cfg.bytecode_cfg.to_code()

        self._subject_properties.register_code_object(
            code_object_id,
            tracer.CodeObjectMetaData(
                code_object=code_object,
                original_code_object=original_code_object,
                parent_code_object_id=parent_code_object_id,
                cfg=cfg,
                original_cfg=original_cfg,
                cdg=cf.ControlDependenceGraph.compute(cfg),
            ),
        )

        return code_object
