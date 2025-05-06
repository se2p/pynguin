#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for various bytecode instrumentations."""

from __future__ import annotations

import builtins
import enum
import json
import logging

from dataclasses import dataclass
from types import CodeType
from typing import TYPE_CHECKING

from bytecode import UNSET
from bytecode import BasicBlock
from bytecode import Bytecode
from bytecode import ControlFlowGraph
from bytecode import Instr

import pynguin.instrumentation.tracer as tr
import pynguin.utils.opcodes as op

from pynguin.analyses.constants import DynamicConstantProvider
from pynguin.analyses.controlflow import CFG
from pynguin.analyses.controlflow import ControlDependenceGraph


if TYPE_CHECKING:
    from pynguin.analyses.controlflow import ProgramGraphNode

CODE_OBJECT_ID_KEY = "code_object_id"


@enum.unique
class PynguinCompare(enum.IntEnum):
    """Enum of all compare operations.

    Previously we were able to use a similar enum from the bytecode library,
    because upto 3.8, there was only a single compare op. With 3.9+, there are now some
    separate compare ops, e.g., IS_OP or CONTAINS_OP. Therefore, we recreate the
    original enum here and map these new ops back.
    """

    LT = 0
    LE = 1
    EQ = 2
    NE = 3
    GT = 4
    GE = 5
    IN = 6
    NOT_IN = 7
    IS = 8
    IS_NOT = 9
    EXC_MATCH = 10


@dataclass
class CodeObjectMetaData:
    """Stores meta data of a code object."""

    # The raw code object.
    code_object: CodeType

    # Id of the parent code object, if any
    parent_code_object_id: int | None

    # CFG of this Code Object
    cfg: CFG

    # copy of the CFG of this code object before the instrumentation worked on it
    original_cfg: CFG

    # CDG of this Code Object
    cdg: ControlDependenceGraph

    def __getstate__(self) -> dict:
        return {
            "code_object": self.code_object,
            "parent_code_object_id": self.parent_code_object_id,
            "cfg": self.cfg,
            "original_cfg": self.original_cfg,
            "cdg": self.cdg,
        }

    def __setstate__(self, state: dict) -> None:
        self.code_object = state["code_object"]
        self.parent_code_object_id = state["parent_code_object_id"]
        self.cfg = state["cfg"]
        self.original_cfg = state["original_cfg"]
        self.cdg = state["cdg"]


@dataclass
class PredicateMetaData:
    """Stores meta data of a predicate."""

    # Line number where the predicate is defined.
    line_no: int

    # Id of the code object where the predicate was defined.
    code_object_id: int

    # The node in the program graph, that defines this predicate.
    node: ProgramGraphNode


class ArtificialInstr(Instr):
    """Marker subclass of an instruction.

    Used to distinguish between original instructions and instructions that were
    inserted by the instrumentation.
    """


class InstrumentationAdapter:
    """Abstract base class for bytecode instrumentation adapters.

    General notes:

    When calling a method on an object, the arguments have to be on top of the stack.
    In most cases, we need to rotate the items on the stack with ROT_THREE or ROT_FOUR
    to reorder the elements accordingly.

    A POP_TOP instruction is required after calling a method, because each method
    implicitly returns None.

    This class defines visit_* methods that are called from the
    InstrumentationTransformer. Each subclass should override the visit_* methods
    where it wants to do something.
    """

    # TODO(fk) make this more fine grained? e.g. visit_line, visit_compare etc.
    #  Or use sub visitors?

    def visit_entry_node(self, basic_block: BasicBlock, code_object_id: int) -> None:
        """Called when we visit the entry node of a code object.

        Args:
            basic_block: The basic block of the entry node.
            code_object_id: The code object id of the containing code object.
        """

    def visit_node(
        self,
        cfg: CFG,
        code_object_id: int,
        node: ProgramGraphNode,
        basic_block: BasicBlock,
    ) -> None:
        """Called for each non-artificial node, i.e., nodes that have a basic block.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            basic_block: The basic block associated with the node.
        """

    @staticmethod
    def _create_consecutive_blocks(
        bytecode_cfg: ControlFlowGraph, first: BasicBlock, amount: int
    ) -> tuple[BasicBlock, ...]:
        """Split the given basic block into more blocks.

        The blocks are consecutive in the list of basic blocks, e.g., to allow
        fall-through

        Args:
            bytecode_cfg: The control-flow graph
            first: The first basic block
            amount: The amount of consecutive blocks that should be created.

        Returns:
            A tuple of consecutive basic blocks
        """
        assert amount > 0, "Amount of created basic blocks must be positive."
        current: BasicBlock = first
        nodes: list[BasicBlock] = []
        # Can be any instruction, as it is discarded anyway.
        dummy_instruction = ArtificialInstr("POP_TOP")
        for _ in range(amount):
            # Insert dummy instruction, which we can use to split off another block
            current.insert(0, dummy_instruction)
            current = bytecode_cfg.split_block(current, 1)
            nodes.append(current)

        # Move instructions back to first block.
        first.clear()
        first.extend(current)
        # Clear instructions in all created blocks.
        for node in nodes:
            node.clear()
        return tuple(nodes)

    @staticmethod
    def map_instr_positions(basic_block: BasicBlock) -> dict[int, int]:
        """Other instrumentations may add artificial instructions.

        Create a mapping that maps original locations to their locations.

        Args:
            basic_block: The block that should be mapped.

        Returns:
            A mapping from original instructions positions to their new positions.
        """
        orig_idx = 0
        mapping = {}
        for idx, instr in enumerate(basic_block):
            if isinstance(instr, ArtificialInstr):
                continue
            mapping[orig_idx] = idx
            orig_idx += 1
        return mapping


class InstrumentationTransformer:
    """Applies a given list of instrumentation adapters to code objects.

    This class is responsible for traversing all nested code objects and their
    basic blocks and requesting their instrumentation from the given adapters.

    Ideally we would want something like ASM with nested visitors where changes from
    different adapters don't affect each other, but that's a bit of overkill for now.
    """

    _logger = logging.getLogger(__name__)

    def __init__(  # noqa: D107
        self,
        instrumentation_tracer: tr.InstrumentationExecutionTracer,
        instrumentation_adapters: list[InstrumentationAdapter],
    ):
        self._instrumentation_adapters = instrumentation_adapters
        self._instrumentation_tracer = instrumentation_tracer

    @property
    def instrumentation_tracer(self) -> tr.InstrumentationExecutionTracer:
        """Get the tracer that is used for the instrumentation.

        Returns:
            The tracer that is used for the instrumentation.
        """
        return self._instrumentation_tracer

    def instrument_module(self, module_code: CodeType) -> CodeType:
        """Instrument the given code object of a module.

        Args:
            module_code: The code object of the module

        Returns:
            The instrumented code object of the module
        """
        for const in module_code.co_consts:
            if isinstance(const, str) and CODE_OBJECT_ID_KEY in const:
                # Abort instrumentation, since we have already
                # instrumented this code object.
                raise AssertionError("Tried to instrument already instrumented module.")
        return self._instrument_code_recursive(module_code)

    def _instrument_code_recursive(
        self,
        code: CodeType,
        parent_code_object_id: int | None = None,
    ) -> CodeType:
        """Instrument the given Code Object recursively.

        Args:
            code: The code object that should be instrumented
            parent_code_object_id: The ID of the optional parent code object

        Returns:
            The instrumented code object
        """
        self._logger.debug("Instrumenting Code Object for %s", code.co_name)
        cfg = CFG.from_bytecode(Bytecode.from_code(code))
        original_cfg = CFG.from_bytecode(Bytecode.from_code(code))
        cdg = ControlDependenceGraph.compute(cfg)
        code_object_id = self._instrumentation_tracer.register_code_object(
            CodeObjectMetaData(
                code_object=code,
                parent_code_object_id=parent_code_object_id,
                cfg=cfg,
                original_cfg=original_cfg,
                cdg=cdg,
            )
        )
        # Overwrite/Set docstring to carry tagging information, i.e.,
        # the code object id. Convert to JSON string because I'm not sure where this
        # value might be used in CPython.
        cfg.bytecode_cfg().docstring = json.dumps({CODE_OBJECT_ID_KEY: code_object_id})
        assert cfg.entry_node is not None, "Entry node cannot be None."
        real_entry_node = cfg.get_successors(cfg.entry_node).pop()  # Only one exists!
        assert real_entry_node.basic_block is not None, "Basic block cannot be None."
        for adapter in self._instrumentation_adapters:
            adapter.visit_entry_node(real_entry_node.basic_block, code_object_id)
        self._instrument_cfg(cfg, code_object_id)
        return self._instrument_inner_code_objects(cfg.bytecode_cfg().to_code(), code_object_id)

    def _instrument_inner_code_objects(
        self, code: CodeType, parent_code_object_id: int
    ) -> CodeType:
        """Apply the instrumentation to all constants of the given code object.

        Args:
            code: the Code Object that should be instrumented.
            parent_code_object_id: the id of the parent code object, if any.

        Returns:
            the code object whose constants were instrumented.
        """
        new_consts = []
        for const in code.co_consts:
            if isinstance(const, CodeType):
                # The const is an inner code object
                new_consts.append(
                    self._instrument_code_recursive(
                        const, parent_code_object_id=parent_code_object_id
                    )
                )
            else:
                new_consts.append(const)
        return code.replace(co_consts=tuple(new_consts))

    def _instrument_cfg(self, cfg: CFG, code_object_id: int) -> None:
        """Instrument the bytecode cfg associated with the given CFG.

        Args:
            cfg: The CFG that overlays the bytecode cfg.
            code_object_id: The id of the code object which contains this CFG.
        """
        for node in cfg.nodes:
            if node.is_artificial:
                # Artificial nodes don't have a basic block, so we don't need to
                # instrument anything.
                continue
            assert node.basic_block is not None, "Non artificial node does not have a basic block."
            for adapter in self._instrumentation_adapters:
                adapter.visit_node(cfg, code_object_id, node, node.basic_block)


class BranchCoverageInstrumentation(InstrumentationAdapter):
    """Instruments code objects to enable tracking branch distances.

    This results in branch coverage.
    """

    # Jump operations are the last operation within a basic block
    _JUMP_OP_POS = -1

    # If a conditional jump is based on a comparison, it has to be the second-to-last
    # instruction within the basic block.
    _COMPARE_OP_POS = -2

    _logger = logging.getLogger(__name__)

    def __init__(  # noqa: D107
        self, instrumentation_tracer: tr.InstrumentationExecutionTracer
    ) -> None:
        self._instrumentation_tracer = instrumentation_tracer

    def visit_node(
        self,
        cfg: CFG,
        code_object_id: int,
        node: ProgramGraphNode,
        basic_block: BasicBlock,
    ) -> None:
        """Instrument a single node in the CFG.

        Currently, we only instrument conditional jumps and for loops.

        Args:
            cfg: The containing CFG.
            code_object_id: The containing Code Object
            node: The node that should be instrumented.
            basic_block: The basic block of the node that should be instrumented.
        """
        assert len(basic_block) > 0, "Empty basic block in CFG."
        maybe_jump: Instr = basic_block[self._JUMP_OP_POS]  # type: ignore[assignment]
        orig_instructions_positions = InstrumentationAdapter.map_instr_positions(basic_block)
        maybe_compare_idx: int | None = orig_instructions_positions.get(
            len(orig_instructions_positions) + self._COMPARE_OP_POS
        )
        if isinstance(maybe_jump, Instr):
            predicate_id: int | None = None
            if maybe_jump.opcode == op.FOR_ITER:
                predicate_id = self._instrument_for_loop(
                    cfg=cfg,
                    node=node,
                    basic_block=basic_block,
                    code_object_id=code_object_id,
                )
            elif maybe_jump.is_cond_jump():
                predicate_id = self._instrument_cond_jump(
                    code_object_id=code_object_id,
                    maybe_compare_idx=maybe_compare_idx,
                    jump=maybe_jump,
                    block=basic_block,
                    node=node,
                )
            if predicate_id is not None:
                node.predicate_id = predicate_id

    def _instrument_cond_jump(
        self,
        code_object_id: int,
        maybe_compare_idx: int | None,
        jump: Instr,
        block: BasicBlock,
        node: ProgramGraphNode,
    ) -> int:
        """Instrument a conditional jump.

        If it is based on a prior comparison, we track
        the compared values, otherwise we just track the truthiness of the value on top
        of the stack.

        Args:
            code_object_id: The id of the containing Code Object.
            maybe_compare_idx: The index of the comparison operation, if any.
            jump: The jump operation.
            block: The containing basic block.
            node: The associated node from the CFG.

        Returns:
            The id that was assigned to the predicate.
        """
        maybe_compare = None if maybe_compare_idx is None else block[maybe_compare_idx]
        if (
            maybe_compare is not None
            and isinstance(maybe_compare, Instr)
            and maybe_compare.opcode in op.OP_COMPARE
        ):
            assert maybe_compare_idx is not None
            return self._instrument_compare_based_conditional_jump(
                block=block,
                code_object_id=code_object_id,
                compare_idx=maybe_compare_idx,
                node=node,
            )
        if jump.opcode == op.JUMP_IF_NOT_EXC_MATCH:
            return self._instrument_exception_based_conditional_jump(
                basic_block=block, code_object_id=code_object_id, node=node
            )
        return self._instrument_bool_based_conditional_jump(
            block=block, code_object_id=code_object_id, node=node
        )

    def _instrument_bool_based_conditional_jump(
        self, block: BasicBlock, code_object_id: int, node: ProgramGraphNode
    ) -> int:
        """Instrument boolean-based conditional jumps.

        We add a call to the tracer which reports the value on which the conditional
        jump will be based.

        Args:
            block: The containing basic block.
            code_object_id: The id of the containing Code Object.
            node: The associated node from the CFG.

        Returns:
            The id assigned to the predicate.
        """
        lineno = block[self._JUMP_OP_POS].lineno  # type: ignore[union-attr]
        predicate_id = self._instrumentation_tracer.register_predicate(
            PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )
        # Insert instructions right before the conditional jump.
        # We duplicate the value on top of the stack and report
        # it to the tracer.
        block[self._JUMP_OP_POS : self._JUMP_OP_POS] = [
            ArtificialInstr("DUP_TOP", lineno=lineno),
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "executed_bool_predicate",
                lineno=lineno,
            ),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            ArtificialInstr("CALL_METHOD", 2, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        return predicate_id

    def _instrument_compare_based_conditional_jump(
        self,
        block: BasicBlock,
        compare_idx: int,
        code_object_id: int,
        node: ProgramGraphNode,
    ) -> int:
        """Instrument compare-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following comparison operation on which the conditional jump is based.

        Args:
            block: The containing basic block.
            compare_idx: The index of the comparison index
            code_object_id: The id of the containing Code Object.
            node: The associated node from the CFG.

        Raises:
            RuntimeError: If an unknown operation is encountered.

        Returns:
            The id assigned to the predicate.
        """
        lineno = block[self._JUMP_OP_POS].lineno  # type: ignore[union-attr]
        predicate_id = self._instrumentation_tracer.register_predicate(
            PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )
        operation = block[compare_idx]

        match operation.name:  # type: ignore[union-attr]
            case "COMPARE_OP":
                compare = int(operation.arg)  # type: ignore[arg-type,union-attr]
            case "IS_OP":
                # Beginning with 3.9, there are separate OPs for various comparisons.
                # Map them back to the old operations, so we can use the enum from the
                # bytecode library.
                compare = (
                    PynguinCompare.IS_NOT.value
                    if operation.arg  # type: ignore[union-attr]
                    else PynguinCompare.IS.value
                )
            case "CONTAINS_OP":
                compare = (
                    PynguinCompare.NOT_IN.value
                    if operation.arg  # type: ignore[union-attr]
                    else PynguinCompare.IN.value
                )
            case _:
                raise RuntimeError(f"Unknown comparison OP {operation}")

        # Insert instructions right before the comparison.
        # We duplicate the values on top of the stack and report
        # them to the tracer.
        block[compare_idx:compare_idx] = [
            ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "executed_compare_predicate",
                lineno=lineno,
            ),
            ArtificialInstr("ROT_FOUR", lineno=lineno),
            ArtificialInstr("ROT_FOUR", lineno=lineno),
            ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            ArtificialInstr("LOAD_CONST", compare, lineno=lineno),
            ArtificialInstr("CALL_METHOD", 4, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        return predicate_id

    def _instrument_exception_based_conditional_jump(
        self, basic_block: BasicBlock, code_object_id: int, node: ProgramGraphNode
    ) -> int:
        """Instrument exception-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following exception matching case.

        Args:
            basic_block: The containing basic block.
            code_object_id: The id of the containing Code Object.
            node: The associated node from the CFG.

        Returns:
            The id assigned to the predicate.
        """
        lineno = basic_block[self._JUMP_OP_POS].lineno  # type: ignore[union-attr]
        predicate_id = self._instrumentation_tracer.register_predicate(
            PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )
        # Insert instructions right before the conditional jump.
        # We duplicate the values on top of the stack and report
        # them to the tracer.
        basic_block[self._JUMP_OP_POS : self._JUMP_OP_POS] = [
            ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "executed_exception_match",
                lineno=lineno,
            ),
            ArtificialInstr("ROT_FOUR", lineno=lineno),
            ArtificialInstr("ROT_FOUR", lineno=lineno),
            ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            ArtificialInstr("CALL_METHOD", 3, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        return predicate_id

    def visit_entry_node(self, basic_block: BasicBlock, code_object_id: int) -> None:
        """Add instructions at the beginning of the given basic block.

        The added instructions inform the tracer, that the code object with the given id
        has been entered.

        Args:
            basic_block: The entry basic block of a code object, i.e. the first basic
                block.
            code_object_id: The id that the tracer has assigned to the code object
                which contains the given basic block.
        """
        # Use line number of first instruction
        lineno = basic_block[0].lineno  # type: ignore[union-attr]
        # Insert instructions at the beginning.
        basic_block[0:0] = [
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "executed_code_object",
                lineno=lineno,
            ),
            ArtificialInstr("LOAD_CONST", code_object_id, lineno=lineno),
            ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]

    def _instrument_for_loop(
        self,
        cfg: CFG,
        node: ProgramGraphNode,
        basic_block: BasicBlock,
        code_object_id: int,
    ) -> int:
        """Transform the for loop whose header is defined in the given node.

        We only transform the underlying bytecode cfg, by partially unrolling the first
        iteration. For this, we add two basic blocks after the loop header:

        The first block is called, if the iterator on which the loop is based
        yields at least one element, in which case we report the boolean value True
        to the tracer, leave the yielded value of the iterator on top of the stack and
        jump to the regular body of the loop.

        The second block is called, if the iterator on which the loop is based
        does not yield an element, in which case we report the boolean value False
        to the tracer and jump to the exit instruction of the loop.

        The original loop header is changed such that it either falls through to the
        first block or jumps to the second, if no element is yielded.

        Since Python is a structured programming language, there can be no jumps
        directly into the loop that bypass the loop header (e.g., GOTO).
        Jumps which reach the loop header from outside the loop will still target
        the original loop header, so they don't need to be modified.

        Attention! These changes to the control flow are not reflected in the high level
        CFG, but only in the bytecode CFG.

        Args:
            cfg: The CFG that contains the loop
            node: The node which contains the header of the for loop.
            basic_block: The basic block of the node.
            code_object_id: The id of the containing Code Object.

        Returns:
            The ID of the instrumented predicate
        """
        for_instr = basic_block[self._JUMP_OP_POS]
        assert for_instr.opcode == op.FOR_ITER  # type: ignore[union-attr]
        lineno = for_instr.lineno  # type: ignore[union-attr]
        predicate_id = self._instrumentation_tracer.register_predicate(
            PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )
        for_loop_exit = for_instr.arg  # type: ignore[union-attr]
        for_loop_body = basic_block.next_block

        entered, not_entered = self._create_consecutive_blocks(cfg.bytecode_cfg(), basic_block, 2)
        # TODO(fk) for_instr is not artificial but we changed it
        #  How to deal with this?
        for_instr.arg = not_entered  # type: ignore[union-attr]

        entered.extend([
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "executed_bool_predicate",
                lineno=lineno,
            ),
            ArtificialInstr("LOAD_CONST", arg=True, lineno=lineno),
            ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            ArtificialInstr("CALL_METHOD", arg=2, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
            ArtificialInstr(
                "JUMP_ABSOLUTE",
                for_loop_body,  # type: ignore[arg-type]
                lineno=lineno,
            ),
        ])

        not_entered.extend([
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "executed_bool_predicate",
                lineno=lineno,
            ),
            ArtificialInstr("LOAD_CONST", arg=False, lineno=lineno),
            ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            ArtificialInstr("CALL_METHOD", arg=2, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
            ArtificialInstr("JUMP_ABSOLUTE", for_loop_exit, lineno=lineno),
        ])

        return predicate_id


class LineCoverageInstrumentation(InstrumentationAdapter):
    """Instruments code objects to enable tracking of executed lines.

    This results in line coverage.
    """

    _logger = logging.getLogger(__name__)

    def __init__(  # noqa: D107
        self, instrumentation_tracer: tr.InstrumentationExecutionTracer
    ) -> None:
        self._instrumentation_tracer = instrumentation_tracer

    def visit_node(  # noqa: D102
        self,
        cfg: CFG,
        code_object_id: int,
        node: ProgramGraphNode,
        basic_block: BasicBlock,
    ) -> None:
        #  iterate over instructions after the fist one in BB,
        #  put new instructions in the block for each line
        file_name = cfg.bytecode_cfg().filename
        lineno = None
        instr_index = 0
        while instr_index < len(basic_block):
            if basic_block[instr_index].lineno != lineno:  # type: ignore[union-attr]
                lineno = basic_block[instr_index].lineno  # type: ignore[union-attr]
                line_id = self._instrumentation_tracer.register_line(
                    code_object_id,
                    file_name,
                    lineno,  # type: ignore[arg-type]
                )
                instr_index += (  # increment by the amount of instructions inserted
                    self.instrument_line(
                        basic_block,
                        instr_index,
                        line_id,
                        lineno,  # type: ignore[arg-type]
                    )
                )
            instr_index += 1

    def instrument_line(
        self, block: BasicBlock, instr_index: int, line_id: int, lineno: int
    ) -> int:
        """Instrument instructions of a new line.

        We add a call to the tracer which reports a line was executed.

        Args:
            block: The basic block containing the instrumented line.
            instr_index: the index of the instr
            line_id: The id of the line that is visited.
            lineno: The line number of the instrumented line.

        Returns:
            The number of instructions inserted into the block
        """
        inserted_instructions = [
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_line_visit",
                lineno=lineno,
            ),
            ArtificialInstr("LOAD_CONST", line_id, lineno=lineno),
            ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        # Insert instructions at the beginning.
        block[instr_index:instr_index] = inserted_instructions
        return len(inserted_instructions)


class CheckedCoverageInstrumentation(InstrumentationAdapter):
    """Instruments code objects to enable tracking of executed instructions.

    Special instructions get instrumented differently to track information
    required to calculate the percentage of instructions in a backward slice for
    an assertion, thus checked coverage.
    """

    _logger = logging.getLogger(__name__)

    def __init__(  # noqa: D107
        self, instrumentation_tracer: tr.InstrumentationExecutionTracer
    ) -> None:
        self._instrumentation_tracer = instrumentation_tracer

    def visit_node(  # noqa: C901
        self,
        cfg: CFG,
        code_object_id: int,
        node: ProgramGraphNode,
        basic_block: BasicBlock,
    ) -> None:
        """Instrument a single node in the CFG.

        We instrument memory accesses, control flow instruction and
        attribute access instructions.

        The instruction number in combination with the line number and the filename can
        uniquely identify the traced instruction in the original bytecode. Since
        instructions have a fixed length of two bytes since version 3.6, this is rather
        trivial to keep track of.

        Args:
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            basic_block: The basic block associated with the node.
        """
        assert len(basic_block) > 0, "Empty basic block in CFG."
        offset = node.offset

        file_name = cfg.bytecode_cfg().filename
        new_block_instructions: list[Instr] = []
        lineno = None

        for instr in basic_block:
            # do not instrument instructions that were added by the instrumentation
            if isinstance(instr, ArtificialInstr):
                new_block_instructions.append(instr)
                continue

            # register all lines available
            if (
                instr.lineno != lineno  # type: ignore[union-attr]
                and file_name != "<ast>"
            ):
                lineno = instr.lineno  # type: ignore[union-attr]
                self._instrumentation_tracer.register_line(
                    code_object_id,
                    file_name,
                    lineno,  # type: ignore[arg-type]
                )

            # Perform the actual instrumentation
            match instr.opcode:  # type: ignore[union-attr]
                case opcode if opcode in (
                    op.OP_UNARY + op.OP_BINARY + op.OP_INPLACE + op.OP_COMPARE
                ):
                    self._instrument_generic(
                        new_block_instructions,
                        code_object_id,
                        node.index,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_LOCAL_ACCESS:
                    self._instrument_local_access(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_NAME_ACCESS:
                    self._instrument_name_access(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_GLOBAL_ACCESS:
                    self._instrument_global_access(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_DEREF_ACCESS:
                    self._instrument_deref_access(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_ATTR_ACCESS:
                    self._instrument_attr_access(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_SUBSCR_ACCESS:
                    self._instrument_subscr_access(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_ABSOLUTE_JUMP + op.OP_RELATIVE_JUMP:
                    self._instrument_jump(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        cfg,
                        file_name,
                    )
                case opcode if opcode in op.OP_CALL:
                    self._instrument_call(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_RETURN:
                    self._instrument_return(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case opcode if opcode in op.OP_IMPORT_NAME:
                    self._instrument_import_name_access(
                        code_object_id,
                        node.index,
                        new_block_instructions,
                        instr,  # type: ignore[arg-type]
                        offset,
                        file_name,
                    )
                case _:
                    # Un-traced instruction retrieved during analysis
                    new_block_instructions.append(instr)  # type: ignore[arg-type]

            offset += 2

        basic_block.clear()
        basic_block.extend(new_block_instructions)

    def _instrument_generic(  # noqa: PLR0917
        self,
        new_block_instructions: list[Instr],
        code_object_id: int,
        node_id: int,
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        # Call tracing method
        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_generic",
                lineno=instr.lineno,
            ),
            # Load arguments
            # Current module
            ArtificialInstr("LOAD_CONST", file_name, lineno=instr.lineno),
            # Code object id
            ArtificialInstr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            ArtificialInstr("LOAD_CONST", node_id, lineno=instr.lineno),
            # Instruction opcode
            ArtificialInstr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            ArtificialInstr(
                "LOAD_CONST",
                instr.lineno,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # Instruction number of access
            ArtificialInstr("LOAD_CONST", offset, lineno=instr.lineno),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 6, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
            # Original instruction
            instr,
        ])

    def _instrument_local_access(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        if instr.opcode in {op.LOAD_FAST, op.STORE_FAST}:
            # Original instruction before instrumentation
            new_block_instructions.append(instr)

        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_memory_access",
                lineno=instr.lineno,
            ),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args(code_object_id, node_id, offset, instr.arg, instr, file_name)
        )

        new_block_instructions.extend([
            # Argument address
            ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            ArtificialInstr("LOAD_FAST", instr.arg, lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            ArtificialInstr("LOAD_FAST", instr.arg, lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode == op.DELETE_FAST:
            # Original instruction after instrumentation
            # (otherwise we can not read it anymore)
            new_block_instructions.append(instr)

    def _instrument_attr_access(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        if instr.opcode in {
            op.LOAD_ATTR,
            op.DELETE_ATTR,
            op.IMPORT_FROM,
            op.LOAD_METHOD,
        }:
            # Duplicate top of stack to access attribute
            new_block_instructions.append(ArtificialInstr("DUP_TOP", lineno=instr.lineno))
        elif instr.opcode == op.STORE_ATTR:
            new_block_instructions.extend([
                # Execute actual store instruction
                ArtificialInstr("DUP_TOP", lineno=instr.lineno),
                ArtificialInstr("ROT_THREE", lineno=instr.lineno),
                instr,
            ])

        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_attribute_access",
                lineno=instr.lineno,
            ),
            # A method occupies two slots on top of the stack
            # -> move third up and keep order of upper two
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args_with_prop(code_object_id, node_id, offset, instr.arg, instr, file_name)
        )

        new_block_instructions.extend([
            # TOS is object ref -> duplicate for determination of source address,
            # argument address and argument_type
            ArtificialInstr("DUP_TOP", lineno=instr.lineno),
            ArtificialInstr("DUP_TOP", lineno=instr.lineno),
            # Determine source address
            #   Load lookup method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer.__class__,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "attribute_lookup",
                lineno=instr.lineno,
            ),
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            #   Load attribute name (second argument)
            ArtificialInstr("LOAD_CONST", instr.arg, lineno=instr.lineno),
            #   Call lookup method
            ArtificialInstr("CALL_METHOD", 2, lineno=instr.lineno),
            # Determine argument address
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            ArtificialInstr("LOAD_ATTR", arg=instr.arg, lineno=instr.lineno),
            ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Determine argument type
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            ArtificialInstr("LOAD_ATTR", arg=instr.arg, lineno=instr.lineno),
            ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 10, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode in {
            op.LOAD_ATTR,
            op.DELETE_ATTR,
            op.IMPORT_FROM,
            op.LOAD_METHOD,
        }:
            # Original instruction: we need to load the attribute afterwards
            new_block_instructions.append(instr)

    def _instrument_subscr_access(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        if instr.opcode == op.STORE_SUBSCR:
            new_block_instructions.extend([
                # Execute actual store instruction
                ArtificialInstr("ROT_TWO", lineno=instr.lineno),
                ArtificialInstr("DUP_TOP", lineno=instr.lineno),
                ArtificialInstr("ROT_FOUR", lineno=instr.lineno),
                ArtificialInstr("ROT_TWO", lineno=instr.lineno),
                instr,
            ])
        elif instr.opcode == op.DELETE_SUBSCR:
            new_block_instructions.extend([
                # Execute delete instruction
                ArtificialInstr("ROT_TWO", lineno=instr.lineno),
                ArtificialInstr("DUP_TOP", lineno=instr.lineno),
                ArtificialInstr("ROT_THREE", lineno=instr.lineno),
                ArtificialInstr("ROT_THREE", lineno=instr.lineno),
                instr,
            ])
        elif instr.opcode == op.BINARY_SUBSCR:
            new_block_instructions.extend([
                # Execute access afterwards, prepare stack
                ArtificialInstr("DUP_TOP_TWO", lineno=instr.lineno),
                ArtificialInstr("POP_TOP", lineno=instr.lineno),
            ])

        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_attribute_access",
                lineno=instr.lineno,
            ),
            # A method occupies two slots on top of the stack
            # -> move third up and keep order of upper two
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args_with_prop(code_object_id, node_id, offset, "None", instr, file_name)
        )

        new_block_instructions.extend([
            # Source object address
            ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # No arg address
            ArtificialInstr(
                "LOAD_CONST",
                None,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # No arg type
            ArtificialInstr(
                "LOAD_CONST",
                None,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 10, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode == op.BINARY_SUBSCR:
            new_block_instructions.append(instr)

    def _instrument_name_access(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        if instr.opcode in {op.STORE_NAME, op.LOAD_NAME, op.IMPORT_NAME}:
            # Original instruction at before instrumentation
            new_block_instructions.append(instr)

        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_memory_access",
                lineno=instr.lineno,
            ),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args(code_object_id, node_id, offset, instr.arg, instr, file_name)
        )

        new_block_instructions.extend([
            # Argument address
            ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            ArtificialInstr("LOAD_NAME", instr.arg, lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            ArtificialInstr("LOAD_NAME", instr.arg, lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])
        if instr.opcode == op.DELETE_NAME:
            # Original instruction after instrumentation
            # (otherwise we can not read it anymore)
            new_block_instructions.append(instr)

    def _instrument_import_name_access(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        new_block_instructions.extend([
            # Execute actual instruction and duplicate module reference on TOS
            instr,
            ArtificialInstr("DUP_TOP"),
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_memory_access",
                lineno=instr.lineno,
            ),
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            ArtificialInstr("ROT_THREE", lineno=instr.lineno),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args_with_prop(code_object_id, node_id, offset, instr.arg, instr, file_name)
        )

        new_block_instructions.extend([
            ArtificialInstr("DUP_TOP", lineno=instr.lineno),
            # Argument address
            ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

    def _instrument_global_access(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        if instr.opcode in {op.STORE_GLOBAL, op.LOAD_GLOBAL}:
            # Original instruction before instrumentation
            new_block_instructions.append(instr)

        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_memory_access",
                lineno=instr.lineno,
            ),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args(code_object_id, node_id, offset, instr.arg, instr, file_name)
        )

        new_block_instructions.extend([
            # Argument address
            ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            ArtificialInstr("LOAD_GLOBAL", instr.arg, lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            ArtificialInstr("LOAD_GLOBAL", instr.arg, lineno=instr.lineno),
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode == op.DELETE_GLOBAL:
            # Original instruction after instrumentation
            # (otherwise we can not read it anymore)
            new_block_instructions.append(instr)

    def _instrument_deref_access(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        # Load instruction
        if instr.opcode == op.LOAD_CLASSDEREF:
            load_instr = ArtificialInstr("LOAD_CLASSDEREF", instr.arg, lineno=instr.lineno)
        else:
            load_instr = ArtificialInstr("LOAD_DEREF", instr.arg, lineno=instr.lineno)

        if instr.opcode in {op.STORE_DEREF, op.LOAD_DEREF, op.LOAD_CLASSDEREF}:
            # Original instruction before instrumentation
            new_block_instructions.append(instr)

        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_memory_access",
                lineno=instr.lineno,
            ),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args(
                code_object_id,
                node_id,
                offset,
                instr.arg.name,  # type: ignore[union-attr]
                instr,
                file_name,
            )
        )

        new_block_instructions.extend([
            # Argument address
            ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            load_instr,
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            load_instr,
            ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode == op.DELETE_DEREF:
            # Original instruction after instrumentation
            # (otherwise we can not read it anymore)
            new_block_instructions.append(instr)

    def _instrument_jump(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        cfg: CFG,
        file_name: str,
    ) -> None:
        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # references method in the ExecutionTracer by name
            # to avoid circular import
            ArtificialInstr("LOAD_METHOD", "track_jump", lineno=instr.lineno),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args(
                code_object_id,
                node_id,
                offset,
                cfg.bytecode_cfg().get_block_index(instr.arg),  # type: ignore[arg-type]
                instr,
                file_name,
            )
        )

        new_block_instructions.extend([
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 7, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

        new_block_instructions.append(instr)

    def _instrument_call(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        # Trace argument only for calls with integer arguments
        argument = instr.arg if isinstance(instr.arg, int) and instr.arg != UNSET else None

        # Call tracing method
        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # references method in the ExecutionTracer by name
            # to avoid circular import
            ArtificialInstr("LOAD_METHOD", "track_call", lineno=instr.lineno),
        ])

        # Load arguments
        new_block_instructions.extend(
            self._load_args(code_object_id, node_id, offset, argument, instr, file_name)
        )

        new_block_instructions.extend([
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 7, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

        new_block_instructions.append(instr)

    def _instrument_return(  # noqa: PLR0917
        self,
        code_object_id: int,
        node_id: int,
        new_block_instructions: list[Instr],
        instr: Instr,
        offset: int,
        file_name: str,
    ) -> None:
        new_block_instructions.extend([
            # Load tracing method
            ArtificialInstr(
                "LOAD_CONST",
                self._instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                # references method in the ExecutionTracer by name
                # to avoid circular import
                "track_return",
                lineno=instr.lineno,
            ),
            # Load arguments
            # Current module
            ArtificialInstr("LOAD_CONST", file_name, lineno=instr.lineno),
            # Code object id
            ArtificialInstr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            ArtificialInstr("LOAD_CONST", node_id, lineno=instr.lineno),
            # Instruction opcode
            ArtificialInstr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            ArtificialInstr(
                "LOAD_CONST",
                instr.lineno,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # Instruction number of access
            ArtificialInstr("LOAD_CONST", offset, lineno=instr.lineno),
            # Call tracing method
            ArtificialInstr("CALL_METHOD", 6, lineno=instr.lineno),
            ArtificialInstr("POP_TOP", lineno=instr.lineno),
        ])

        # Original instruction after instrumentation
        # (otherwise we do not reach instrumented code)
        new_block_instructions.append(instr)

    @staticmethod
    def _load_args(  # noqa: PLR0917
        code_object_id: int,
        node_id: int,
        offset: int,
        arg,
        instr: Instr,
        file_name: str,
    ) -> list[ArtificialInstr]:
        instructions = [
            # Current module
            ArtificialInstr("LOAD_CONST", file_name, lineno=instr.lineno),
            # Code object id
            ArtificialInstr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            ArtificialInstr("LOAD_CONST", node_id, lineno=instr.lineno),
            # Instruction opcode
            ArtificialInstr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            ArtificialInstr(
                "LOAD_CONST",
                instr.lineno,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # Instruction number of access
            ArtificialInstr("LOAD_CONST", offset, lineno=instr.lineno),
            # Argument name
            ArtificialInstr("LOAD_CONST", arg, lineno=instr.lineno),
        ]

        return instructions  # noqa: RET504

    @staticmethod
    def _load_args_with_prop(  # noqa: PLR0917
        code_object_id: int,
        node_id: int,
        offset: int,
        arg,
        instr: Instr,
        file_name: str,
    ) -> list[ArtificialInstr]:
        instructions = [
            # Load arguments
            #   Current module
            ArtificialInstr("LOAD_CONST", file_name, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Code object id
            ArtificialInstr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Basic block id
            ArtificialInstr("LOAD_CONST", node_id, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Instruction opcode
            ArtificialInstr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Line number of access
            ArtificialInstr(
                "LOAD_CONST",
                instr.lineno,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Instruction number of access
            ArtificialInstr("LOAD_CONST", offset, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Argument name
            ArtificialInstr("LOAD_CONST", arg, lineno=instr.lineno),
            ArtificialInstr("ROT_TWO", lineno=instr.lineno),
        ]

        return instructions  # noqa: RET504


class DynamicSeedingInstrumentation(InstrumentationAdapter):
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

    # Compare operations are only followed by one jump operation, hence they are on the
    # second to last position of the block.
    _COMPARE_OP_POS = -2

    #  If one of the considered string functions needing no argument is used in the if
    #  statement, it will be loaded in the third last position. After it comes the
    #  call of the method and the jump operation.
    _STRING_FUNC_POS = -3

    # If one of the considered string functions needing one argument is used in the if
    # statement, it will be loaded in the fourth last position. After it comes the
    # load of the argument, the call of the method and the jump
    # operation.
    _STRING_FUNC_POS_WITH_ARG = -4

    _logger = logging.getLogger(__name__)

    def __init__(  # noqa: D107
        self, dynamic_constant_provider: DynamicConstantProvider
    ):
        self._dynamic_constant_provider = dynamic_constant_provider

    def visit_node(  # noqa: D102
        self,
        cfg: CFG,
        code_object_id: int,
        node: ProgramGraphNode,
        basic_block: BasicBlock,
    ) -> None:
        assert len(basic_block) > 0, "Empty basic block in CFG."
        maybe_compare: Instr | None = (
            basic_block[self._COMPARE_OP_POS]  # type: ignore[assignment]
            if len(basic_block) > 1
            else None
        )
        maybe_string_func: Instr | None = (
            basic_block[self._STRING_FUNC_POS]  # type: ignore[assignment]
            if len(basic_block) > 2
            else None
        )
        maybe_string_func_with_arg: Instr | None = (
            basic_block[self._STRING_FUNC_POS_WITH_ARG]  # type: ignore[assignment]
            if len(basic_block) > 3
            else None
        )
        if isinstance(maybe_compare, Instr) and maybe_compare.opcode == op.COMPARE_OP:
            self._instrument_compare_op(basic_block)
        if (
            isinstance(maybe_string_func, Instr)
            and maybe_string_func.opcode == op.LOAD_METHOD
            and maybe_string_func.arg in DynamicConstantProvider.STRING_FUNCTION_LOOKUP
        ):
            self._instrument_string_func(
                basic_block,
                maybe_string_func.arg,  # type: ignore[arg-type]
            )
        if (
            isinstance(maybe_string_func_with_arg, Instr)
            and maybe_string_func_with_arg.opcode == op.LOAD_METHOD
            and maybe_string_func_with_arg.arg in {"startswith", "endswith"}
        ):
            self._instrument_string_func(
                basic_block,
                maybe_string_func_with_arg.arg,  # type: ignore[arg-type]
            )

    def _instrument_startswith_function(self, block: BasicBlock) -> None:
        """Instruments the startswith function in bytecode.

        Stores for the expression 'string1.startswith(string2)' the value
        'string2 + string1' in the _dynamic_pool.

        Args:
            block: The basic block where the new instructions are inserted.
        """
        insert_pos = self._STRING_FUNC_POS_WITH_ARG + 2
        lineno = block[insert_pos].lineno  # type: ignore[union-attr]
        block[insert_pos:insert_pos] = [
            ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            ArtificialInstr("ROT_TWO", lineno=lineno),
            ArtificialInstr("BINARY_ADD", lineno=lineno),
            ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value.__name__,
                lineno=lineno,
            ),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented startswith function")

    def _instrument_endswith_function(self, block: BasicBlock) -> None:
        """Instruments the endswith function in bytecode.

        Stores for the expression 'string1.startswith(string2)' the value
        'string1 + string2' in the _dynamic_pool.

        Args:
            block: The basic block where the new instructions are inserted.
        """
        insert_pos = self._STRING_FUNC_POS_WITH_ARG + 2
        lineno = block[insert_pos].lineno  # type: ignore[union-attr]
        block[insert_pos:insert_pos] = [
            ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            ArtificialInstr("BINARY_ADD", lineno=lineno),
            ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value.__name__,
                lineno=lineno,
            ),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented endswith function")

    def _instrument_string_function_without_arg(
        self, block: BasicBlock, function_name: str
    ) -> None:
        """Instruments the isalnum function in bytecode.

        Args:
            block: The basic block where the new instructions are inserted.
            function_name: The name of the function
        """
        insert_pos = self._STRING_FUNC_POS_WITH_ARG + 2
        lineno = block[insert_pos].lineno  # type: ignore[union-attr]
        block[insert_pos:insert_pos] = [
            ArtificialInstr("DUP_TOP", lineno=lineno),
            ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value_for_strings.__name__,
                lineno=lineno,
            ),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("LOAD_CONST", function_name, lineno=lineno),
            ArtificialInstr("CALL_METHOD", 2, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented string function")

    def _instrument_string_func(self, block: BasicBlock, function_name: str) -> None:
        """Calls the corresponding instrumentation method for the given function_name.

        Args:
            block: The block to instrument.
            function_name: The name of the function for which the method will be called.

        """
        if function_name == "startswith":
            self._instrument_startswith_function(block)
        elif function_name == "endswith":
            self._instrument_endswith_function(block)
        else:
            self._instrument_string_function_without_arg(block, function_name)

    def _instrument_compare_op(self, block: BasicBlock) -> None:
        """Instruments the compare operations in bytecode.

        Stores the values extracted at runtime.

        Args:
            block: The containing basic block.
        """
        lineno = block[self._COMPARE_OP_POS].lineno  # type: ignore[union-attr]
        block[self._COMPARE_OP_POS : self._COMPARE_OP_POS] = [
            ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value.__name__,
                lineno=lineno,
            ),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
            ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value.__name__,
                lineno=lineno,
            ),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("ROT_THREE", lineno=lineno),
            ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        self._logger.debug("Instrumented compare_op")
