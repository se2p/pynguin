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
from typing import Set, Optional, Tuple, List, Dict

import networkx as nx
from bytecode import Instr, Bytecode, Compare, BasicBlock, ControlFlowGraph

from pynguin.analyses.controlflow.cfg import CFG
from pynguin.analyses.controlflow.controldependencegraph import ControlDependenceGraph
from pynguin.analyses.controlflow.dominatortree import DominatorTree
from pynguin.analyses.controlflow.programgraph import ProgramGraphNode
from pynguin.instrumentation.basis import TRACER_NAME
from pynguin.testcase.execution.executiontracer import (
    ExecutionTracer,
    CodeObjectMetaData,
    PredicateMetaData,
)


# pylint:disable=too-few-public-methods
class BranchDistanceInstrumentation:
    """Instruments code objects to enable branch distance tracking."""

    # As of CPython 3.8, there are a few compare ops for which we can't really
    # compute a sensible branch distance. So for now, we just ignore those
    # comparisons and just track the result.
    # TODO(fk) update this to work with the bytecode for CPython 3.9, once it is released.
    _IGNORED_COMPARE_OPS: Set[Compare] = {Compare.EXC_MATCH}

    _logger = logging.getLogger(__name__)

    def __init__(self, tracer: ExecutionTracer) -> None:
        self._tracer = tracer

    def _instrument_inner_code_objects(
        self, code: CodeType, parent_code_object_id: int
    ) -> CodeType:
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
        add_global_tracer: bool = False,
        parent_code_object_id: Optional[int] = None,
    ) -> CodeType:
        """Instrument the given CodeType recursively."""
        # TODO(fk) Change instrumentation to make use of a visitor pattern, similar to ASM in Java.
        # The instrumentation loop is already getting really big...
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
        dominator_tree = DominatorTree.compute(cfg)
        assert cfg.entry_node is not None, "Entry node cannot be None."
        assert cfg.entry_node.basic_block is not None, "Entry node cannot be None."
        self._add_code_object_entered(cfg.entry_node.basic_block, code_object_id)
        if add_global_tracer:
            self._add_tracer_to_globals(cfg.entry_node.basic_block)
        node_attributes: Dict[ProgramGraphNode, Dict[str, int]] = dict()
        for node in cfg.nodes:
            # Not every block has an associated basic block, e.g. the artificial exit node.
            if node.basic_block is not None and len(node.basic_block) > 0:
                maybe_jump: Instr = node.basic_block[-1]
                maybe_previous: Optional[Instr] = node.basic_block[-2] if len(
                    node.basic_block
                ) > 1 else None
                if isinstance(maybe_jump, Instr) and maybe_jump.name == "FOR_ITER":
                    node_attributes[node] = {
                        CFG.PREDICATE_ID: self._transform_for_loop(
                            cfg, dominator_tree, node, code_object_id
                        )
                    }
                elif isinstance(maybe_jump, Instr) and maybe_jump.is_cond_jump():
                    if (
                        maybe_previous is not None
                        and isinstance(maybe_previous, Instr)
                        and maybe_previous.name == "COMPARE_OP"
                        and maybe_previous.arg
                        not in BranchDistanceInstrumentation._IGNORED_COMPARE_OPS
                    ):
                        node_attributes[node] = {
                            CFG.PREDICATE_ID: self._add_cmp_predicate(
                                node.basic_block, code_object_id
                            )
                        }
                    else:
                        node_attributes[node] = {
                            CFG.PREDICATE_ID: self._add_bool_predicate(
                                node.basic_block, code_object_id
                            )
                        }
        # Store predicate ids in nodes.
        nx.set_node_attributes(cfg.graph, node_attributes)
        return self._instrument_inner_code_objects(
            cfg.bytecode_cfg().to_code(), code_object_id
        )

    def _add_bool_predicate(self, block: BasicBlock, code_object_id: int) -> int:
        lineno = block[-1].lineno
        predicate_id = self._tracer.register_predicate(
            PredicateMetaData(line_no=lineno, code_object_id=code_object_id)
        )
        block[-1:-1] = [
            Instr("DUP_TOP", lineno=lineno),
            Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                ExecutionTracer.passed_bool_predicate.__name__,
                lineno=lineno,
            ),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("LOAD_CONST", predicate_id, lineno=lineno),
            Instr("CALL_METHOD", 2, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        return predicate_id

    def _add_cmp_predicate(self, block: BasicBlock, code_object_id: int) -> int:
        lineno = block[-1].lineno
        predicate_id = self._tracer.register_predicate(
            PredicateMetaData(line_no=lineno, code_object_id=code_object_id)
        )
        cmp_op = block[-2]
        block[-2:-2] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                ExecutionTracer.passed_cmp_predicate.__name__,
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

    @staticmethod
    def _add_code_object_entered(block: BasicBlock, code_object_id: int) -> int:
        lineno = block[0].lineno
        block[0:0] = [
            Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
            Instr(
                "LOAD_METHOD",
                ExecutionTracer.entered_code_object.__name__,
                lineno=lineno,
            ),
            Instr("LOAD_CONST", code_object_id, lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        return code_object_id

    def _add_tracer_to_globals(self, block: BasicBlock) -> None:
        """Add the tracer to the globals."""
        lineno = block[0].lineno
        block[0:0] = [
            Instr("LOAD_CONST", self._tracer, lineno=lineno),
            Instr("STORE_GLOBAL", TRACER_NAME, lineno=lineno),
        ]

    def instrument_module(self, module_code: CodeType) -> CodeType:
        """Instrument the given code object of a module."""
        for const in module_code.co_consts:
            if isinstance(const, ExecutionTracer):
                # Abort instrumentation, since we have already
                # instrumented this code object.
                assert False, "Tried to instrument already instrumented module."
        return self._instrument_code_recursive(module_code, True)

    def _transform_for_loop(
        self,
        cfg: CFG,
        dominator_tree: DominatorTree,
        node: ProgramGraphNode,
        code_object_id: int,
    ) -> int:
        """Transform the for loop that is defined in the given node.
        We only transform the underlying bytecode cfg, by partially unrolling the first
        iteration.
        """
        assert node.basic_block is not None, "Basic block of for loop cannot be None."
        for_instr = node.basic_block[-1]
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
                Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
                Instr(
                    "LOAD_METHOD",
                    ExecutionTracer.passed_bool_predicate.__name__,
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
                Instr("LOAD_GLOBAL", TRACER_NAME, lineno=lineno),
                Instr(
                    "LOAD_METHOD",
                    ExecutionTracer.passed_bool_predicate.__name__,
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
                and successor.basic_block[-1].arg is node.basic_block
            ):
                successor.basic_block[-1].arg = new_header
        return predicate_id

    @staticmethod
    def _create_consecutive_blocks(
        bytecode_cfg: ControlFlowGraph, first: BasicBlock, amount: int
    ) -> Tuple[BasicBlock, ...]:
        """Split the given basic block into more blocks, which are
        consecutive in the list of basic blocks.
        :param amount: The amount of consecutive blocks that should be created."""
        assert amount > 0, "Amount of created basic blocks must be positive."
        current: BasicBlock = first
        nodes: List[BasicBlock] = []
        dummy_instruction = Instr("RETURN_VALUE")
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
