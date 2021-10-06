#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides classes for various bytecode instrumentations."""
from __future__ import annotations

import json
import logging
from abc import abstractmethod
from types import CodeType
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

from bytecode import BasicBlock, Bytecode, Compare, ControlFlowGraph, Instr

from pynguin.analyses.controlflow.cfg import CFG
from pynguin.analyses.controlflow.controldependencegraph import ControlDependenceGraph
from pynguin.analyses.seeding.constantseeding import DynamicConstantSeeding
from pynguin.testcase.execution.executiontracer import (
    CodeObjectMetaData,
    ExecutionTracer,
    PredicateMetaData,
)

if TYPE_CHECKING:
    from pynguin.analyses.controlflow.programgraph import ProgramGraphNode

CODE_OBJECT_ID_KEY = "code_object_id"


# pylint:disable=too-few-public-methods
class Instrumentation:
    """Abstract base class for bytecode instrumentations.

    General notes:

    When calling a method on an object, the arguments have to be on top of the stack.
    In most cases, we need to rotate the items on the stack with ROT_THREE or ROT_FOUR
    to reorder the elements accordingly.

    A POP_TOP instruction is required after calling a method, because each method
    implicitly returns None."""

    @abstractmethod
    def instrument_module(self, module_code: CodeType) -> CodeType:
        """Instrument the given code object of a module.

        Args:
            module_code: The code object of the module

        Returns:
            The instrumented code object of the module
        """

    @staticmethod
    def _create_consecutive_blocks(
        bytecode_cfg: ControlFlowGraph, first: BasicBlock, amount: int
    ) -> Tuple[BasicBlock, ...]:
        """Split the given basic block into more blocks.

        The blocks are consecutive in the list of basic blocks.

        Args:
            bytecode_cfg: The control-flow graph
            first: The first basic block
            amount: The amount of consecutive blocks that should be created.

        Returns:
            A tuple of consecutive basic blocks
        """
        assert amount > 0, "Amount of created basic blocks must be positive."
        current: BasicBlock = first
        nodes: List[BasicBlock] = []
        # Can be any instruction, as it is discarded anyway.
        dummy_instruction = Instr("POP_TOP")
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


class BranchCoverageInstrumentation(Instrumentation):
    """Instruments code objects to enable tracking branch distances and thus
    branch coverage."""

    # As of CPython 3.8, there are a few compare ops for which we can't really
    # compute a sensible branch distance. So for now, we just ignore those
    # comparisons and just track their boolean value.
    # As of CPython 3.9, this is no longer a compare op but instead
    # a JUMP_IF_NOT_EXC_MATCH, which we also handle as boolean based jump.
    _IGNORED_COMPARE_OPS: Set[Compare] = {Compare.EXC_MATCH}

    # Conditional jump operations are the last operation within a basic block
    _JUMP_OP_POS = -1

    # If a conditional jump is based on a comparison, it has to be the second-to-last
    # instruction within the basic block.
    _COMPARE_OP_POS = -2

    _logger = logging.getLogger(__name__)

    def __init__(self, tracer: ExecutionTracer) -> None:
        self._tracer = tracer

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

    def _instrument_code_recursive(
        self,
        code: CodeType,
        parent_code_object_id: Optional[int] = None,
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
        cdg = ControlDependenceGraph.compute(cfg)
        code_object_id = self._tracer.register_code_object(
            CodeObjectMetaData(
                code_object=code,
                parent_code_object_id=parent_code_object_id,
                cfg=cfg,
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
        self._add_code_object_executed(real_entry_node.basic_block, code_object_id)
        self._instrument_cfg(cfg, code_object_id)
        return self._instrument_inner_code_objects(
            cfg.bytecode_cfg().to_code(), code_object_id
        )

    def _instrument_cfg(self, cfg: CFG, code_object_id: int) -> None:
        """Instrument the bytecode cfg associated with the given CFG.

        Args:
            cfg: The CFG that overlays the bytecode cfg.
            code_object_id: The id of the code object which contains this CFG.
        """
        # Required to transform for loops.
        for node in cfg.nodes:
            predicate_id = self._instrument_node(cfg, code_object_id, node)
            if predicate_id is not None:
                node.predicate_id = predicate_id

    def _instrument_node(
        self,
        cfg: CFG,
        code_object_id: int,
        node: ProgramGraphNode,
    ) -> Optional[int]:
        """Instrument a single node in the CFG.

        Currently we only instrument conditional jumps and for loops.

        Args:
            cfg: The containing CFG.
            code_object_id: The containing Code Object
            node: The node that should be instrumented.

        Returns:
            A predicate id, if the contained a predicate which was instrumented.
        """
        predicate_id: Optional[int] = None
        # Not every block has an associated basic block, e.g. the artificial exit node.
        if not node.is_artificial:
            assert (
                node.basic_block is not None
            ), "Non artificial node does not have a basic block."
            assert len(node.basic_block) > 0, "Empty basic block in CFG."
            maybe_jump: Instr = node.basic_block[self._JUMP_OP_POS]
            maybe_compare: Optional[Instr] = (
                node.basic_block[self._COMPARE_OP_POS]
                if len(node.basic_block) > 1
                else None
            )
            if isinstance(maybe_jump, Instr):
                if maybe_jump.name == "FOR_ITER":
                    predicate_id = self._instrument_for_loop(cfg, node, code_object_id)
                elif maybe_jump.is_cond_jump():
                    predicate_id = self._instrument_cond_jump(
                        code_object_id,
                        maybe_compare,
                        maybe_jump,
                        node.basic_block,
                        node,
                    )
        return predicate_id

    def _instrument_cond_jump(
        self,
        code_object_id: int,
        maybe_compare: Optional[Instr],
        jump: Instr,
        block: BasicBlock,
        node: ProgramGraphNode,
    ) -> int:
        # pylint:disable=too-many-arguments
        """Instrument a conditional jump.

        If it is based on a prior comparison, we track
        the compared values, otherwise we just track the truthiness of the value on top
        of the stack.

        Args:
            code_object_id: The id of the containing Code Object.
            maybe_compare: The comparison operation, if any.
            jump: The jump operation.
            block: The containing basic block.
            node: The associated node from the CFG.

        Returns:
            The id that was assigned to the predicate.
        """
        if (
            maybe_compare is not None
            and isinstance(maybe_compare, Instr)
            and (
                (
                    maybe_compare.name == "COMPARE_OP"
                    and maybe_compare.arg not in self._IGNORED_COMPARE_OPS
                )
                or maybe_compare.name in ("IS_OP", "CONTAINS_OP")
            )
        ):
            return self._instrument_compare_based_conditional_jump(
                block, code_object_id, node
            )
        # Up to 3.9, there was COMPARE_OP EXC_MATCH which was handled below
        # Beginning with 3.9, there is a combined compare+jump op, which is handled
        # here.
        if jump.name == "JUMP_IF_NOT_EXC_MATCH":
            return self._instrument_exception_based_conditional_jump(
                block, code_object_id, node
            )
        return self._instrument_bool_based_conditional_jump(block, code_object_id, node)

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
        lineno = block[self._JUMP_OP_POS].lineno
        predicate_id = self._tracer.register_predicate(
            PredicateMetaData(line_no=lineno, code_object_id=code_object_id, node=node)
        )
        # Insert instructions right before the conditional jump.
        # We duplicate the value on top of the stack and report
        # it to the tracer.
        block[self._JUMP_OP_POS : self._JUMP_OP_POS] = [
            Instr("DUP_TOP", lineno=lineno),
            Instr("LOAD_CONST", self._tracer, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                ExecutionTracer.executed_bool_predicate.__name__,
                lineno=lineno,
            ),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("LOAD_CONST", predicate_id, lineno=lineno),
            Instr("CALL_METHOD", 2, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        return predicate_id

    def _instrument_compare_based_conditional_jump(
        self, block: BasicBlock, code_object_id: int, node: ProgramGraphNode
    ) -> int:
        """Instrument compare-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following comparison operation on which the conditional jump is based.

        Args:
            block: The containing basic block.
            code_object_id: The id of the containing Code Object.
            node: The associated node from the CFG.

        Raises:
            RuntimeError: If an unknown operation is encountered.

        Returns:
            The id assigned to the predicate.
        """
        lineno = block[self._JUMP_OP_POS].lineno
        predicate_id = self._tracer.register_predicate(
            PredicateMetaData(line_no=lineno, code_object_id=code_object_id, node=node)
        )
        operation = block[self._COMPARE_OP_POS]

        if operation.name == "COMPARE_OP":
            compare = operation.arg
        elif operation.name == "IS_OP":
            # Beginning with 3.9, there are separate OPs for various comparisons.
            compare = Compare.IS_NOT if operation.arg else Compare.IS
        elif operation.name == "CONTAINS_OP":
            compare = Compare.NOT_IN if operation.arg else Compare.IN
        else:
            raise RuntimeError(f"Unknown comparison OP {operation}")

        # Insert instructions right before the comparison.
        # We duplicate the values on top of the stack and report
        # them to the tracer.
        block[self._COMPARE_OP_POS : self._COMPARE_OP_POS] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("LOAD_CONST", self._tracer, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                ExecutionTracer.executed_compare_predicate.__name__,
                lineno=lineno,
            ),
            Instr("ROT_FOUR", lineno=lineno),
            Instr("ROT_FOUR", lineno=lineno),
            Instr("LOAD_CONST", predicate_id, lineno=lineno),
            Instr("LOAD_CONST", compare, lineno=lineno),
            Instr("CALL_METHOD", 4, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        return predicate_id

    def _instrument_exception_based_conditional_jump(
        self, block: BasicBlock, code_object_id: int, node: ProgramGraphNode
    ) -> int:
        """Instrument exception-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following exception matching case.

        Args:
            block: The containing basic block.
            code_object_id: The id of the containing Code Object.
            node: The associated node from the CFG.

        Returns:
            The id assigned to the predicate.
        """
        lineno = block[self._JUMP_OP_POS].lineno
        predicate_id = self._tracer.register_predicate(
            PredicateMetaData(line_no=lineno, code_object_id=code_object_id, node=node)
        )
        # Insert instructions right before the conditional jump.
        # We duplicate the values on top of the stack and report
        # them to the tracer.
        block[self._JUMP_OP_POS : self._JUMP_OP_POS] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("LOAD_CONST", self._tracer, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                ExecutionTracer.executed_exception_match.__name__,
                lineno=lineno,
            ),
            Instr("ROT_FOUR", lineno=lineno),
            Instr("ROT_FOUR", lineno=lineno),
            Instr("LOAD_CONST", predicate_id, lineno=lineno),
            Instr("CALL_METHOD", 3, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        return predicate_id

    def _add_code_object_executed(self, block: BasicBlock, code_object_id: int) -> None:
        """Add instructions at the beginning of the given basic block which inform
        the tracer, that the code object with the given id has been entered.

        Args:
            block: The entry basic block of a code object, i.e. the first basic block.
            code_object_id: The id that the tracer has assigned to the code object
                which contains the given basic block.
        """
        # Use line number of first instruction
        lineno = block[0].lineno
        # Insert instructions at the beginning.
        block[0:0] = [
            Instr("LOAD_CONST", self._tracer, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                ExecutionTracer.executed_code_object.__name__,
                lineno=lineno,
            ),
            Instr("LOAD_CONST", code_object_id, lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]

    def instrument_module(self, module_code: CodeType) -> CodeType:
        for const in module_code.co_consts:
            if isinstance(const, ExecutionTracer):
                # Abort instrumentation, since we have already
                # instrumented this code object.
                assert False, "Tried to instrument already instrumented module."
        return self._instrument_code_recursive(module_code)

    def _instrument_for_loop(
        self,
        cfg: CFG,
        node: ProgramGraphNode,
        code_object_id: int,
    ) -> int:
        """Transform the for loop whose header is defined in the given node.
        We only transform the underlying bytecode cfg, by partially unrolling the first
        iteration. For this, we add two basic blocks after the loop header:

        The first block is called, if the iterator on which the loop is based
        yields at least one element, in which case we report the boolean value True
        to the tracer, leave the yielded value of the iterator on top of the stack and
        jump to the the regular body of the loop.

        The second block is called, if the iterator on which the loop is based
        does not yield an element, in which case we report the boolean value False
        to the tracer and jump to the exit instruction of the loop.

        The original loop header is changed such that it either falls through to the
        first block or jumps to the second, if no element is yielded.

        Since Python is a structured programming language, there can be no jumps
        directly into the loop that bypass the loop header (e.g., GOTO).
        Jumps which reach the loop header from outside the loop will still target
        the original loop header, so they don't need to be modified.

        Args:
            cfg: The CFG that contains the loop
            node: The node which contains the header of the for loop.
            code_object_id: The id of the containing Code Object.

        Returns:
            The ID of the instrumented predicate
        """
        assert node.basic_block is not None, "Basic block of for loop cannot be None."
        for_instr = node.basic_block[self._JUMP_OP_POS]
        assert for_instr.name == "FOR_ITER"
        lineno = for_instr.lineno
        predicate_id = self._tracer.register_predicate(
            PredicateMetaData(line_no=lineno, code_object_id=code_object_id, node=node)
        )
        for_loop_exit = for_instr.arg
        for_loop_body = node.basic_block.next_block

        # pylint:disable=unbalanced-tuple-unpacking
        entered, not_entered = self._create_consecutive_blocks(
            cfg.bytecode_cfg(), node.basic_block, 2
        )
        for_instr.arg = not_entered

        entered.extend(
            [
                Instr("LOAD_CONST", self._tracer, lineno=lineno),
                Instr(
                    "LOAD_METHOD",
                    ExecutionTracer.executed_bool_predicate.__name__,
                    lineno=lineno,
                ),
                Instr("LOAD_CONST", True, lineno=lineno),
                Instr("LOAD_CONST", predicate_id, lineno=lineno),
                Instr("CALL_METHOD", 2, lineno=lineno),
                Instr("POP_TOP", lineno=lineno),
                Instr("JUMP_ABSOLUTE", for_loop_body, lineno=lineno),
            ]
        )

        not_entered.extend(
            [
                Instr("LOAD_CONST", self._tracer, lineno=lineno),
                Instr(
                    "LOAD_METHOD",
                    ExecutionTracer.executed_bool_predicate.__name__,
                    lineno=lineno,
                ),
                Instr("LOAD_CONST", False, lineno=lineno),
                Instr("LOAD_CONST", predicate_id, lineno=lineno),
                Instr("CALL_METHOD", 2, lineno=lineno),
                Instr("POP_TOP", lineno=lineno),
                Instr("JUMP_ABSOLUTE", for_loop_exit, lineno=lineno),
            ]
        )

        return predicate_id


# pylint:disable=too-few-public-methods
class DynamicSeedingInstrumentation(Instrumentation):
    """Instruments code objects to enable dynamic constant seeding.

    Supported is collecting values of the types int, float and string.

    Instrumented are the common compare operations (==, !=, <, >, <=, >=) and the string
    methods contained in the STRING_FUNCTION_NAMES list. This means, if one of the
    above operations and methods is used in an if-conditional, corresponding values
    are added to the dynamic constant pool.

    The dynamic pool is implemented in the module constantseeding.py. The dynamicseeding
    module containes methods for managing the dynamic pool during the algorithm
    execution."""

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

    # A list containing the names of all string functions which are instrumented.
    _STRING_FUNCTION_NAMES = [
        "startswith",
        "endswith",
        "isalnum",
        "isalpha",
        "isdecimal",
        "isdigit",
        "isidentifier",
        "islower",
        "isnumeric",
        "isprintable",
        "isspace",
        "istitle",
        "isupper",
    ]

    _logger = logging.getLogger(__name__)

    def __init__(self, dynamic_constant_seeding: DynamicConstantSeeding):
        self._dynamic_constant_seeding = dynamic_constant_seeding

    def _instrument_startswith_function(self, block: BasicBlock) -> None:
        """Instruments the startswith function in bytecode. Stores for the expression
          'string1.startswith(string2)' the
           value 'string2 + string1' in the _dynamic_pool.

        Args:
            block: The basic block where the new instructions are inserted.
        """
        insert_pos = self._STRING_FUNC_POS_WITH_ARG + 2
        lineno = block[insert_pos].lineno
        block[insert_pos:insert_pos] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("ROT_TWO", lineno=lineno),
            Instr("BINARY_ADD", lineno=lineno),
            Instr("LOAD_CONST", self._dynamic_constant_seeding, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                self._dynamic_constant_seeding.add_value.__name__,
                lineno=lineno,
            ),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented startswith function")

    def _instrument_endswith_function(self, block: BasicBlock) -> None:
        """Instruments the endswith function in bytecode. Stores for the expression
         'string1.startswith(string2)' the
           value 'string1 + string2' in the _dynamic_pool.

        Args:
            block: The basic block where the new instructions are inserted.
        """
        insert_pos = self._STRING_FUNC_POS_WITH_ARG + 2
        lineno = block[insert_pos].lineno
        block[insert_pos:insert_pos] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("BINARY_ADD", lineno=lineno),
            Instr("LOAD_CONST", self._dynamic_constant_seeding, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                DynamicConstantSeeding.add_value.__name__,
                lineno=lineno,
            ),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
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
        lineno = block[insert_pos].lineno
        block[insert_pos:insert_pos] = [
            Instr("DUP_TOP", lineno=lineno),
            Instr("LOAD_CONST", self._dynamic_constant_seeding, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                DynamicConstantSeeding.add_value_for_strings.__name__,
                lineno=lineno,
            ),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("LOAD_CONST", function_name, lineno=lineno),
            Instr("CALL_METHOD", 2, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
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
        """Instruments the compare operations in bytecode. Stores the values extracted
         at runtime.

        Args:
            block: The containing basic block.
        """
        lineno = block[self._COMPARE_OP_POS].lineno
        block[self._COMPARE_OP_POS : self._COMPARE_OP_POS] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("LOAD_CONST", self._dynamic_constant_seeding, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                DynamicConstantSeeding.add_value.__name__,
                lineno=lineno,
            ),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
            Instr("LOAD_CONST", self._dynamic_constant_seeding, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                DynamicConstantSeeding.add_value.__name__,
                lineno=lineno,
            ),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        self._logger.debug("Instrumented compare_op")

    def _instrument_inner_code_objects(self, code: CodeType) -> CodeType:
        """Apply the instrumentation to all constants of the given code object.

        Args:
            code: the Code Object that should be instrumented.

        Returns:
            the code object whose constants were instrumented.
        """
        new_consts = []
        for const in code.co_consts:
            if isinstance(const, CodeType):
                # The const is an inner code object
                new_consts.append(self._instrument_code_recursive(const))
            else:
                new_consts.append(const)
        return code.replace(co_consts=tuple(new_consts))

    def _instrument_code_recursive(
        self,
        code: CodeType,
    ) -> CodeType:
        """Instrument the given Code Object recursively.

        Args:
            code: The code object that should be instrumented

        Returns:
            The instrumented code object
        """
        self._logger.debug(
            "Instrumenting Code Object for dynamic seeding for %s", code.co_name
        )
        cfg = CFG.from_bytecode(Bytecode.from_code(code))

        assert cfg.entry_node is not None, "Entry node cannot be None."
        real_entry_node = cfg.get_successors(cfg.entry_node).pop()  # Only one exists!
        assert real_entry_node.basic_block is not None, "Basic block cannot be None."

        self._instrument_cfg(cfg)
        return self._instrument_inner_code_objects(cfg.bytecode_cfg().to_code())

    def _instrument_cfg(self, cfg: CFG) -> None:
        """Instrument the bytecode cfg associated with the given CFG.

        Args:
            cfg: The CFG that overlays the bytecode cfg.
        """
        # Attributes which store the predicate ids assigned to instrumented nodes.
        for node in cfg.nodes:
            self._instrument_node(node)

    def _instrument_node(
        self,
        node: ProgramGraphNode,
    ) -> None:
        """Instrument a single node in the CFG.

        Currently we only instrument conditional jumps and for loops.

        Args:
            node: The node that should be instrumented.
        """
        # Not every block has an associated basic block, e.g. the artificial exit node.
        if not node.is_artificial:
            assert (
                node.basic_block is not None
            ), "Non artificial node does not have a basic block."
            assert len(node.basic_block) > 0, "Empty basic block in CFG."
            maybe_compare: Optional[Instr] = (
                node.basic_block[self._COMPARE_OP_POS]
                if len(node.basic_block) > 1
                else None
            )
            maybe_string_func: Optional[Instr] = (
                node.basic_block[self._STRING_FUNC_POS]
                if len(node.basic_block) > 2
                else None
            )
            maybe_string_func_with_arg: Optional[Instr] = (
                node.basic_block[self._STRING_FUNC_POS_WITH_ARG]
                if len(node.basic_block) > 3
                else None
            )
            if isinstance(maybe_compare, Instr) and maybe_compare.name == "COMPARE_OP":
                self._instrument_compare_op(node.basic_block)
            if (
                isinstance(maybe_string_func, Instr)
                and maybe_string_func.name == "LOAD_METHOD"
                and maybe_string_func.arg in self._STRING_FUNCTION_NAMES
            ):
                self._instrument_string_func(node.basic_block, maybe_string_func.arg)
            if (
                isinstance(maybe_string_func_with_arg, Instr)
                and maybe_string_func_with_arg.name == "LOAD_METHOD"
                and maybe_string_func_with_arg.arg in self._STRING_FUNCTION_NAMES
            ):
                self._instrument_string_func(
                    node.basic_block, maybe_string_func_with_arg.arg
                )

    def instrument_module(self, module_code: CodeType) -> CodeType:
        return self._instrument_code_recursive(module_code)
