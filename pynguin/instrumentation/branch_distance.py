# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides capabilities to perform branch instrumentation."""
import logging
from types import CodeType
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
from bytecode import BasicBlock, Bytecode, Compare, ControlFlowGraph, Instr

from pynguin.analyses.controlflow.cfg import CFG
from pynguin.analyses.controlflow.controldependencegraph import ControlDependenceGraph
from pynguin.analyses.controlflow.dominatortree import DominatorTree
from pynguin.analyses.controlflow.programgraph import ProgramGraphNode
from pynguin.testcase.execution.executiontracer import (
    CodeObjectMetaData,
    ExecutionTracer,
    PredicateMetaData,
)


# pylint:disable=too-few-public-methods
class BranchDistanceInstrumentation:
    """Instruments code objects to enable branch distance tracking.

    General notes:

    When calling a method on an object, the arguments have to be on top of the stack.
    In most cases, we need to rotate the items on the stack with ROT_THREE or ROT_FOUR
    to reorder the elements accordingly.

    A POP_TOP instruction is required after calling a method, because each method
    implicitly returns None."""

    # As of CPython 3.8, there are a few compare ops for which we can't really
    # compute a sensible branch distance. So for now, we just ignore those
    # comparisons and just track their boolean value.
    # TODO(fk) update this to work with the bytecode for CPython 3.9, once it is released.
    _IGNORED_COMPARE_OPS: Set[Compare] = {Compare.EXC_MATCH}

    # Conditional jump operations are the last operation within a basic block
    _JUMP_OP_POS = -1

    # If a conditional jump is based on a comparision, it has to be the second-to-last
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
        self, code: CodeType, parent_code_object_id: Optional[int] = None,
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
        dominator_tree = DominatorTree.compute(cfg)
        # Attributes which store the predicate ids assigned to instrumented nodes.
        node_attributes: Dict[ProgramGraphNode, Dict[str, int]] = dict()
        for node in cfg.nodes:
            predicate_id = self._instrument_node(
                cfg, code_object_id, dominator_tree, node
            )
            if predicate_id is not None:
                node_attributes[node] = {CFG.PREDICATE_ID: predicate_id}
        nx.set_node_attributes(cfg.graph, node_attributes)

    def _instrument_node(
        self,
        cfg: CFG,
        code_object_id: int,
        dominator_tree: DominatorTree,
        node: ProgramGraphNode,
    ) -> Optional[int]:
        """Instrument a single node in the CFG.

        Currently we only instrument conditional jumps and for loops.

        Args:
            cfg: The containing CFG.
            code_object_id: The containing Code Object
            dominator_tree: The dominator tree of the CFG
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
            maybe_compare: Optional[Instr] = node.basic_block[
                self._COMPARE_OP_POS
            ] if len(node.basic_block) > 1 else None
            if isinstance(maybe_jump, Instr):
                if maybe_jump.name == "FOR_ITER":
                    predicate_id = self._instrument_for_loop(
                        cfg, dominator_tree, node, code_object_id
                    )
                elif maybe_jump.is_cond_jump():
                    predicate_id = self._instrument_cond_jump(
                        code_object_id, maybe_compare, node.basic_block
                    )
        return predicate_id

    def _instrument_cond_jump(
        self, code_object_id: int, maybe_compare: Optional[Instr], block: BasicBlock
    ) -> int:
        """Instrument a conditional jump.

        If it is based on a prior comparision, we track
        the compared values, otherwise we just track the truthiness of the value on top
        of the stack.

        Args:
            code_object_id: The id of the containing Code Object.
            maybe_compare: The comparision operation, if any.
            block: The containing basic block.

        Returns:
            The id that was assigned to the predicate.
        """
        if (
            maybe_compare is not None
            and isinstance(maybe_compare, Instr)
            and maybe_compare.name == "COMPARE_OP"
            and maybe_compare.arg
            not in BranchDistanceInstrumentation._IGNORED_COMPARE_OPS
        ):
            return self._instrument_compare_based_conditional_jump(
                block, code_object_id
            )
        return self._instrument_bool_based_conditional_jump(block, code_object_id)

    def _instrument_bool_based_conditional_jump(
        self, block: BasicBlock, code_object_id: int
    ) -> int:
        """Instrument boolean-based conditional jumps.

        We add a call to the tracer which reports the value on which the conditional
        jump will be based.

        Args:
            block: The containing basic block.
            code_object_id: The id of the containing Code Object.

        Returns:
            The id assigned to the predicate.
        """
        lineno = block[self._JUMP_OP_POS].lineno
        predicate_id = self._tracer.register_predicate(
            PredicateMetaData(line_no=lineno, code_object_id=code_object_id)
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
        self, block: BasicBlock, code_object_id: int
    ) -> int:
        """Instrument compare-based conditional jumps.

        We add a call to the tracer which reports the values that will be used
        in the following comparision operation on which the conditional jump is based.

        Args:
            block: The containing basic block.
            code_object_id: The id of the containing Code Object.

        Returns:
            The id assigned to the predicate.
        """
        lineno = block[self._JUMP_OP_POS].lineno
        predicate_id = self._tracer.register_predicate(
            PredicateMetaData(line_no=lineno, code_object_id=code_object_id)
        )
        cmp_op = block[self._COMPARE_OP_POS]
        # Insert instructions right before the comparision.
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
            Instr("LOAD_CONST", cmp_op.arg, lineno=lineno),
            Instr("CALL_METHOD", 4, lineno=lineno),
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
        """Instrument the given code object of a module.

        Args:
            module_code: The code objects of the module

        Returns:
            The instrumented code objects of the module
        """
        for const in module_code.co_consts:
            if isinstance(const, ExecutionTracer):
                # Abort instrumentation, since we have already
                # instrumented this code object.
                assert False, "Tried to instrument already instrumented module."
        return self._instrument_code_recursive(module_code)

    def _instrument_for_loop(
        self,
        cfg: CFG,
        dominator_tree: DominatorTree,
        node: ProgramGraphNode,
        code_object_id: int,
    ) -> int:
        """Transform the for loop whose header is defined in the given node.
        We only transform the underlying bytecode cfg, by partially unrolling the first
        iteration. For this, we add three basic blocks after the loop header:

        The first block is called, if the iterator on which the loop is based
        yields at least one element, in which case we report the boolean value True
        to the tracer, leave the yielded value of the iterator on top of the stack and
        jump to the the regular body of the loop.

        The second block is called, if the iterator on which the loop is based
        does not yield an element, in which case we report the boolean value False
        to the tracer and jump to the exit instruction of the loop.

        The third block acts as the new internal header of the for loop. It consists
        of a copy of the original "FOR_ITER" instruction of the loop.

        The original loop header is changed such that it either falls through to the
        first block or jumps to the second, if no element is yielded.

        Since Python is a structured programming language, there can be no jumps
        directly into the loop that bypass the loop header (e.g., GOTO).
        Jumps which reach the loop header from outside the loop will still target
        the original loop header, so they don't need to be modified.
        Jumps which originate from within the loop (e.g., break or continue) need
        to be redirected to the new internal header (3rd new block).
        We use a dominator tree to find and redirect the jumps of such instructions.

        Args:
            cfg: The CFG that contains the loop
            dominator_tree: The dominator tree of the given CFG.
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
            PredicateMetaData(code_object_id, lineno)
        )
        for_instr_copy = for_instr.copy()
        for_loop_exit = for_instr.arg
        for_loop_body = node.basic_block.next_block

        # pylint:disable=unbalanced-tuple-unpacking
        entered, not_entered, new_header = self._create_consecutive_blocks(
            cfg.bytecode_cfg(), node.basic_block, 3
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

        new_header.append(for_instr_copy)

        # Redirect internal jumps to the new loop header
        for successor in dominator_tree.get_transitive_successors(node):
            if (
                successor.basic_block is not None
                and successor.basic_block[self._JUMP_OP_POS].arg is node.basic_block
            ):
                successor.basic_block[self._JUMP_OP_POS].arg = new_header
        return predicate_id

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
