#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides enums for opcode numbers of instructions in bytecode for Python 3.10."""

from __future__ import annotations

import builtins
import logging

from opcode import opmap
from opcode import opname
from opcode import stack_effect as opcode_stack_effect
from typing import TYPE_CHECKING

from bytecode.cfg import BasicBlock
from bytecode.instr import _UNSET
from bytecode.instr import UNSET
from bytecode.instr import Instr
from bytecode.instr import Label

from pynguin.analyses.constants import DynamicConstantProvider
from pynguin.instrumentation import PynguinCompare
from pynguin.instrumentation import StackEffect
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation import tracer
from pynguin.instrumentation import transformer


if TYPE_CHECKING:
    from collections.abc import Sequence

    from bytecode import Bytecode


def to_opcodes(*names: str) -> tuple[int, ...]:
    """Convert a tuple of opcode names to their corresponding integer values."""
    return tuple(opmap[name] for name in names)


OP_UNARY = to_opcodes(
    "UNARY_POSITIVE",
    "UNARY_NEGATIVE",
    "UNARY_NOT",
    "UNARY_INVERT",
    "GET_ITER",
    "GET_YIELD_FROM_ITER",
)

OP_BINARY = to_opcodes(
    "BINARY_POWER",
    "BINARY_MULTIPLY",
    "BINARY_MATRIX_MULTIPLY",
    "BINARY_FLOOR_DIVIDE",
    "BINARY_TRUE_DIVIDE",
    "BINARY_MODULO",
    "BINARY_ADD",
    "BINARY_SUBTRACT",
    "BINARY_LSHIFT",
    "BINARY_RSHIFT",
    "BINARY_AND",
    "BINARY_XOR",
    "BINARY_OR",
)

OP_INPLACE = to_opcodes(
    "INPLACE_POWER",
    "INPLACE_MULTIPLY",
    "INPLACE_MATRIX_MULTIPLY",
    "INPLACE_FLOOR_DIVIDE",
    "INPLACE_TRUE_DIVIDE",
    "INPLACE_MODULO",
    "INPLACE_ADD",
    "INPLACE_SUBTRACT",
    "INPLACE_LSHIFT",
    "INPLACE_RSHIFT",
    "INPLACE_AND",
    "INPLACE_XOR",
    "INPLACE_OR",
)

OP_COMPARE = to_opcodes(
    "COMPARE_OP",
    "IS_OP",
    "CONTAINS_OP",
)

OP_LOCAL_LOAD = to_opcodes(
    "LOAD_FAST",
)
OP_LOCAL_MODIFY = to_opcodes(
    "STORE_FAST",
    "DELETE_FAST",
)
OP_LOCAL_ACCESS = OP_LOCAL_LOAD + OP_LOCAL_MODIFY

OP_NAME_LOAD = to_opcodes(
    "LOAD_NAME",
)
OP_NAME_MODIFY = to_opcodes(
    "STORE_NAME",
    "DELETE_NAME",
)
OP_NAME_ACCESS = OP_NAME_LOAD + OP_NAME_MODIFY

OP_GLOBAL_LOAD = to_opcodes(
    "LOAD_GLOBAL",
)
OP_GLOBAL_MODIFY = to_opcodes(
    "STORE_GLOBAL",
    "DELETE_GLOBAL",
)
OP_GLOBAL_ACCESS = OP_GLOBAL_LOAD + OP_GLOBAL_MODIFY

OP_DEREF_LOAD = to_opcodes(
    "LOAD_DEREF",
    "LOAD_CLASSDEREF",
)
OP_DEREF_MODIFY = to_opcodes(
    "STORE_DEREF",
    "DELETE_DEREF",
)
OP_DEREF_ACCESS = OP_DEREF_LOAD + OP_DEREF_MODIFY
OP_CLOSURE_LOAD = to_opcodes(
    "LOAD_CLOSURE",
)

OP_ATTR_ACCESS = to_opcodes(
    "STORE_ATTR",
    "LOAD_ATTR",
    "DELETE_ATTR",
    "IMPORT_FROM",
    "LOAD_METHOD",
)
OP_SUBSCR_ACCESS = to_opcodes(
    "STORE_SUBSCR",
    "DELETE_SUBSCR",
    "BINARY_SUBSCR",
)
OP_IMPORT_NAME = to_opcodes(
    "IMPORT_NAME",
)
OP_IMPORT_FROM = to_opcodes(
    "IMPORT_FROM",
)
OP_EXTENDED_ARG = to_opcodes(
    "EXTENDED_ARG",
)
OP_ABSOLUTE_JUMP = to_opcodes(
    "JUMP_IF_FALSE_OR_POP",
    "JUMP_IF_TRUE_OR_POP",
    "JUMP_ABSOLUTE",
    "POP_JUMP_IF_FALSE",
    "POP_JUMP_IF_TRUE",
    "JUMP_IF_NOT_EXC_MATCH",
)
OP_RELATIVE_JUMP = to_opcodes(
    "FOR_ITER",
    "JUMP_FORWARD",
    "SETUP_FINALLY",
    "SETUP_WITH",
    "SETUP_ASYNC_WITH",
)
OP_CALL = to_opcodes(
    "CALL_FUNCTION",
    "CALL_FUNCTION_KW",
    "CALL_FUNCTION_EX",
    "CALL_METHOD",
    "YIELD_FROM",
)
OP_RETURN = to_opcodes("RETURN_VALUE", "YIELD_VALUE")

OP_STORES = to_opcodes(
    "STORE_ATTR",
    "STORE_SUBSCR",
)
OP_ACCESS = to_opcodes("LOAD_ATTR", "DELETE_ATTR", "IMPORT_FROM")
OP_STORE_NAME = to_opcodes(
    "STORE_NAME",
)

TRACED_INSTRUCTIONS = (
    OP_UNARY
    + OP_BINARY
    + OP_INPLACE
    + OP_COMPARE
    + OP_LOCAL_ACCESS
    + OP_NAME_ACCESS
    + OP_GLOBAL_ACCESS
    + OP_DEREF_ACCESS
    + OP_ATTR_ACCESS
    + OP_SUBSCR_ACCESS
    + OP_IMPORT_NAME
    + OP_ABSOLUTE_JUMP
    + OP_RELATIVE_JUMP
    + OP_CALL
    + OP_RETURN
)

MEMORY_USE_INSTRUCTIONS = to_opcodes(
    "LOAD_FAST",
    "LOAD_NAME",
    "LOAD_GLOBAL",
    "LOAD_ATTR",
    "LOAD_DEREF",
    "BINARY_SUBSCR",
    "LOAD_METHOD",
    "IMPORT_FROM",
    "LOAD_CLOSURE",
    "LOAD_CLASSDEREF",
)
MEMORY_DEF_INSTRUCTIONS = to_opcodes(
    "STORE_FAST",
    "STORE_NAME",
    "STORE_GLOBAL",
    "STORE_DEREF",
    "STORE_ATTR",
    "STORE_SUBSCR",
    "BINARY_SUBSCR",
    "DELETE_FAST",
    "DELETE_NAME",
    "DELETE_GLOBAL",
    "DELETE_ATTR",
    "DELETE_SUBSCR",
    "DELETE_DEREF",
    "IMPORT_NAME",
)  # compensate incorrect stack effect for IMPORT_NAME
COND_BRANCH_INSTRUCTIONS = to_opcodes(
    "POP_JUMP_IF_TRUE",
    "POP_JUMP_IF_FALSE",
    "JUMP_IF_TRUE_OR_POP",
    "JUMP_IF_FALSE_OR_POP",
    "JUMP_IF_NOT_EXC_MATCH",
    "FOR_ITER",
)


def is_yielding(opcode: int) -> bool:  # noqa: D103
    return opname[opcode] in {
        "YIELD_VALUE",
        "YIELD_FROM",
    }


def is_for_loop(opcode: int) -> bool:  # noqa: D103
    return opname[opcode] == "FOR_ITER"


def add_for_loop_no_yield_nodes(bytecode: Bytecode) -> Bytecode:  # noqa: D103
    bytecode_copy = bytecode.copy()
    i = 0
    while i < len(bytecode_copy):
        instruction = bytecode_copy[i]

        if (
            isinstance(instruction, Instr)
            and is_for_loop(instruction.opcode)
            and isinstance(instruction.arg, Label)
        ):
            exit_label = instruction.arg

            exit_label_index = bytecode_copy.index(exit_label)

            dummy_label = Label()

            bytecode_copy[exit_label_index:exit_label_index] = [
                dummy_label,
                Instr(
                    "NOP",
                    lineno=instruction.lineno,
                    location=instruction.location,
                ),
            ]

            instruction.arg = dummy_label

        i += 1

    return bytecode_copy


def is_import(opcode: int) -> bool:  # noqa: D103
    return opname[opcode] == "IMPORT_NAME"


def get_boolean_condition(opcode: int) -> bool | None:  # noqa: D103
    match opname[opcode]:
        case "POP_JUMP_IF_TRUE" | "JUMP_IF_TRUE_OR_POP":
            # These jump to arg if ToS is True
            return True
        case "POP_JUMP_IF_FALSE" | "JUMP_IF_FALSE_OR_POP" | "JUMP_IF_NOT_EXC_MATCH" | "FOR_ITER":
            # These jump to arg if ToS is False, is Empty or if Exc does not
            # match.
            return False
        case _:
            # Not a conditional jump or a for loop instruction
            return None


def end_with_explicit_return_none(instructions: Sequence[Instr]) -> bool:  # noqa: D103
    return (
        len(instructions) >= 3
        # check if the "return None" is implicit or explicit
        and instructions[-3].lineno != instructions[-2].lineno
        and instructions[-2].opcode == opmap["LOAD_CONST"]
        and instructions[-2].arg is None
        and instructions[-1].opcode == opmap["RETURN_VALUE"]
    )


def stack_effect(  # noqa: D103, C901, PLR0915
    opcode: int,
    arg: int | None,
    *,
    jump: bool = False,
) -> StackEffect:
    effect: StackEffect
    match opname[opcode]:
        case (
            "NOP"
            | "SETUP_ANNOTATIONS"
            | "POP_BLOCK"
            | "DELETE_NAME"
            | "DELETE_GLOBAL"
            | "JUMP_FORWARD"
            | "JUMP_ABSOLUTE"
            | "DELETE_FAST"
            | "DELETE_DEREF"
            | "EXTENDED_ARG"
            | "ROT_N"
        ):
            effect = StackEffect(0, 0)
        case (
            "POP_TOP"
            | "PRINT_EXPR"
            | "RETURN_VALUE"
            | "STORE_NAME"
            | "IMPORT_STAR"
            | "DELETE_ATTR"
            | "STORE_GLOBAL"
            | "POP_JUMP_IF_FALSE"
            | "POP_JUMP_IF_TRUE"
            | "STORE_FAST"
            | "STORE_DEREF"
            | "LIST_APPEND"
            | "SET_ADD"
            | "GEN_START"
        ):
            effect = StackEffect(1, 0)
        case "DELETE_SUBSCR" | "STORE_ATTR" | "MAP_ADD" | "JUMP_IF_NOT_EXC_MATCH":
            effect = StackEffect(2, 0)
        case "STORE_SUBSCR" | "POP_EXCEPT" | "RERAISE":
            effect = StackEffect(3, 0)
        case "END_ASYNC_FOR":
            effect = StackEffect(7, 0)  # TODO conditional 0 pops?
        case (
            "LOAD_BUILD_CLASS"
            | "LOAD_CONST"
            | "LOAD_NAME"
            | "IMPORT_FROM"
            | "LOAD_GLOBAL"
            | "LOAD_FAST"
            | "LOAD_CLOSURE"
            | "LOAD_DEREF"
            | "LOAD_CLASSDEREF"
            | "WITH_EXCEPT_START"
            | "LOAD_ASSERTION_ERROR"
            | "GET_LEN"
            | "MATCH_MAPPING"
            | "MATCH_SEQUENCE"
        ):
            effect = StackEffect(0, 1)
        case "MATCH_KEYS":
            effect = StackEffect(0, 2)
        case (
            "UNARY_POSITIVE"
            | "UNARY_NEGATIVE"
            | "UNARY_NOT"
            | "UNARY_INVERT"
            | "GET_AITER"
            | "GET_ITER"
            | "GET_YIELD_FROM_ITER"
            | "GET_AWAITABLE"
            | "GET_AWAITABLE"
            | "YIELD_VALUE"
            | "LOAD_ATTR"
            | "FORMAT_VALUE"
            | "LIST_TO_TUPLE"
        ):
            effect = StackEffect(1, 1)
        case "ROT_TWO" | "COPY_DICT_WITHOUT_KEYS":
            effect = StackEffect(2, 2)
        case "ROT_THREE":
            effect = StackEffect(3, 3)
        case "ROT_FOUR":
            effect = StackEffect(4, 4)
        case "DUP_TOP" | "BEFORE_ASYNC_WITH" | "GET_ANEXT" | "LOAD_METHOD":
            effect = StackEffect(1, 2)
        case (
            "BINARY_MATRIX_MULTIPLY"
            | "INPLACE_MATRIX_MULTIPLY"
            | "BINARY_POWER"
            | "BINARY_MULTIPLY"
            | "BINARY_MODULO"
            | "BINARY_ADD"
            | "BINARY_SUBTRACT"
            | "BINARY_SUBSCR"
            | "BINARY_FLOOR_DIVIDE"
            | "BINARY_TRUE_DIVIDE"
            | "INPLACE_FLOOR_DIVIDE"
            | "INPLACE_TRUE_DIVIDE"
            | "INPLACE_ADD"
            | "INPLACE_SUBTRACT"
            | "INPLACE_MULTIPLY"
            | "INPLACE_MODULO"
            | "BINARY_LSHIFT"
            | "BINARY_RSHIFT"
            | "BINARY_AND"
            | "BINARY_XOR"
            | "BINARY_OR"
            | "INPLACE_POWER"
            | "YIELD_FROM"
            | "INPLACE_LSHIFT"
            | "INPLACE_RSHIFT"
            | "INPLACE_AND"
            | "INPLACE_XOR"
            | "INPLACE_OR"
            | "COMPARE_OP"
            | "IMPORT_NAME"
            | "IS_OP"
            | "CONTAINS_OP"
            | "MATCH_CLASS"
            | "LIST_EXTEND"
            | "SET_UPDATE"
            | "DICT_MERGE"
            | "DICT_UPDATE"
        ):
            effect = StackEffect(2, 1)
        case "DUP_TOP_TWO":
            effect = StackEffect(2, 4)
        # jump based operations
        case "SETUP_WITH":
            effect = StackEffect(0, 6) if jump else StackEffect(0, 1)
        case "FOR_ITER":
            effect = StackEffect(1, 0) if jump else StackEffect(1, 2)
        case "JUMP_IF_TRUE_OR_POP" | "JUMP_IF_FALSE_OR_POP":
            effect = StackEffect(0, 0) if jump else StackEffect(1, 0)
        case "SETUP_FINALLY":
            effect = StackEffect(0, 6) if jump else StackEffect(0, 0)
        # argument dependant operations
        case "UNPACK_SEQUENCE":
            assert arg is not None
            effect = StackEffect(1, arg)
        case "UNPACK_EX":
            assert arg is not None
            effect = StackEffect(1, (arg & 0xFF) + (arg >> 8) + 1)
        case "BUILD_TUPLE" | "BUILD_LIST" | "BUILD_SET" | "BUILD_STRING":
            assert arg is not None
            effect = StackEffect(arg, 1)
        case "BUILD_MAP":
            assert arg is not None
            effect = StackEffect(2 * arg, 1)
        case "BUILD_CONST_KEY_MAP" | "CALL_FUNCTION":
            assert arg is not None
            effect = StackEffect(1 + arg, 1)
        case "RAISE_VARARGS":
            assert arg is not None
            effect = StackEffect(arg, 0)
        case "CALL_METHOD" | "CALL_FUNCTION_KW":
            assert arg is not None
            effect = StackEffect(2 + arg, 1)
        case "CALL_FUNCTION_EX":
            assert arg is not None
            # argument contains flags
            pops = 2
            if arg & 0x01 != 0:
                pops += 1
            effect = StackEffect(pops, 1)
        case "MAKE_FUNCTION":
            assert arg is not None
            # argument contains flags
            pops = 2
            if arg & 0x01 != 0:
                pops += 1
            if arg & 0x02 != 0:
                pops += 1
            if arg & 0x04 != 0:
                pops += 1
            if arg & 0x08 != 0:
                pops += 1
            effect = StackEffect(pops, 1)
        case "BUILD_SLICE":
            effect = StackEffect(3, 1) if arg == 3 else StackEffect(2, 1)
        case _:
            raise AssertionError(f"The opcode {opcode} ({opname[opcode]}) isn't recognized.")

    assert opcode_stack_effect(opcode, arg, jump=jump) == effect.pushes - effect.pops

    return effect


class BranchCoverageInstrumentation(transformer.BranchCoverageInstrumentationAdapter):
    """Specialized instrumentation adapter for branch coverage in Python 3.10."""

    # Jump operations are the last operation within a basic block
    _JUMP_OP_POS = -1

    # If a conditional jump is based on a comparison, it has to be the second-to-last
    # instruction within the basic block.
    _COMPARE_OP_POS = -2

    _logger = logging.getLogger(__name__)

    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:  # noqa: D107
        self._subject_properties = subject_properties

    def visit_node(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        maybe_jump_index = self._JUMP_OP_POS
        maybe_jump = node.get_instruction(maybe_jump_index)

        if is_for_loop(maybe_jump.opcode):
            self.visit_for_loop(
                cfg,
                code_object_id,
                node,
                maybe_jump,
                maybe_jump_index,
            )
            return

        if not maybe_jump.is_cond_jump():
            return

        maybe_compare_index, maybe_compare = node.find_instruction_by_original_index(
            self._COMPARE_OP_POS,
        )

        if maybe_compare.opcode in OP_COMPARE:
            self.visit_compare_based_conditional_jump(
                cfg,
                code_object_id,
                node,
                maybe_compare,
                maybe_compare_index,
            )
            return

        if maybe_jump.opcode == opmap["JUMP_IF_NOT_EXC_MATCH"]:
            self.visit_exception_based_conditional_jump(
                cfg,
                code_object_id,
                node,
                maybe_jump,
                maybe_jump_index,
            )
            return

        self.visit_bool_based_conditional_jump(
            cfg,
            code_object_id,
            node,
            maybe_jump,
            maybe_jump_index,
        )

    def visit_for_loop(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        for_loop_body = node.basic_block.next_block
        for_loop_no_yield = instr.arg

        assert isinstance(for_loop_body, BasicBlock)
        assert isinstance(for_loop_no_yield, BasicBlock)

        # Insert a call to the tracer before the for-loop body.
        for_loop_body[cf.before(0)] = (
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.executed_bool_predicate.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("LOAD_CONST", arg=True, lineno=lineno),
            cf.ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", arg=2, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        )

        # Insert a call to the tracer before the NOP instruction.
        for_loop_no_yield[cf.before(0)] = (
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.executed_bool_predicate.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("LOAD_CONST", arg=False, lineno=lineno),
            cf.ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", arg=2, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        )

    def visit_compare_based_conditional_jump(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        match instr.name:
            case "COMPARE_OP":
                compare = int(instr.arg)  # type: ignore[arg-type]
            case "IS_OP":
                # Beginning with 3.9, there are separate OPs for various comparisons.
                # Map them back to the old operations, so we can use the enum from the
                # bytecode library.
                compare = PynguinCompare.IS_NOT.value if instr.arg else PynguinCompare.IS.value
            case "CONTAINS_OP":
                compare = PynguinCompare.NOT_IN.value if instr.arg else PynguinCompare.IN.value
            case _:
                raise AssertionError(f"Unknown comparison OP {instr}")

        # Insert instructions right before the comparison.
        # We duplicate the values on top of the stack and report
        # them to the tracer.
        node.basic_block[cf.before(instr_index)] = (
            cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.executed_compare_predicate.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
            cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
            cf.ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            cf.ArtificialInstr("LOAD_CONST", compare, lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 4, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        )

    def visit_exception_based_conditional_jump(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        # Insert instructions right before the conditional jump.
        # We duplicate the values on top of the stack and report
        # them to the tracer.
        node.basic_block[cf.before(instr_index)] = (
            cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.executed_exception_match.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
            cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
            cf.ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 3, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        )

    def visit_bool_based_conditional_jump(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        # Insert instructions right before the conditional jump.
        # We duplicate the value on top of the stack and report
        # it to the tracer.
        node.basic_block[cf.before(instr_index)] = (
            cf.ArtificialInstr("DUP_TOP", lineno=lineno),
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.executed_bool_predicate.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("LOAD_CONST", predicate_id, lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 2, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        )

    def visit_cfg(self, cfg: cf.CFG, code_object_id: int) -> None:  # noqa: D102
        node = cfg.first_basic_block_node

        assert node is not None, "The CFG must have at least one basic block node."

        # Use line number of first instruction
        lineno = node.basic_block[0].lineno  # type: ignore[union-attr]

        # Insert instructions at the beginning.
        node.basic_block[cf.before(0)] = (
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.executed_code_object.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("LOAD_CONST", code_object_id, lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        )


class LineCoverageInstrumentation(transformer.LineCoverageInstrumentationAdapter):
    """Specialized instrumentation adapter for line coverage in Python 3.10."""

    _logger = logging.getLogger(__name__)

    def __init__(  # noqa: D107
        self,
        subject_properties: tracer.SubjectProperties,
    ) -> None:
        self._subject_properties = subject_properties

    def visit_node(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        lineno: int | _UNSET | None = None
        # The bytecode instructions change during the iteration but it is something supported
        for instr_index, instr in enumerate(node.instructions):
            if instr.lineno == lineno or cfg.bytecode_cfg.filename == cf.AST_FILENAME:
                continue

            lineno = instr.lineno

            self.visit_line(cfg, code_object_id, node, instr, instr_index)

    def visit_line(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        line_id = self._subject_properties.register_line(
            tracer.LineMetaData(
                code_object_id=code_object_id,
                file_name=cfg.bytecode_cfg.filename,
                line_number=lineno,  # type: ignore[arg-type]
            )
        )

        # Insert instructions before each line instructions.
        node.basic_block[cf.before(instr_index)] = (
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_line_visit.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("LOAD_CONST", line_id, lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        )


class CheckedCoverageInstrumentation(transformer.CheckedCoverageInstrumentationAdapter):
    """Specialized instrumentation adapter for checked coverage in Python 3.10."""

    _logger = logging.getLogger(__name__)

    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:  # noqa: D107
        self._subject_properties = subject_properties

    def visit_node(  # noqa: C901, D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        file_name = cfg.bytecode_cfg.filename
        lineno: int | _UNSET | None = None

        instr_index = 0
        instr_offset = node.offset
        while instr_index < len(node.basic_block):
            instr = node.get_instruction(instr_index)

            if isinstance(instr, cf.ArtificialInstr):
                instr_index += 1
                continue

            # Register all lines available
            if instr.lineno != lineno and file_name != cf.AST_FILENAME:
                lineno = instr.lineno
                self._subject_properties.register_line(
                    tracer.LineMetaData(
                        code_object_id=code_object_id,
                        file_name=file_name,
                        line_number=lineno,  # type: ignore[arg-type]
                    )
                )

            # Perform the actual instrumentation
            if instr.opcode in (OP_UNARY + OP_BINARY + OP_INPLACE + OP_COMPARE):
                self.visit_generic(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_LOCAL_ACCESS:
                self.visit_local_access(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_ATTR_ACCESS:
                self.visit_attr_access(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_SUBSCR_ACCESS:
                self.visit_subscr_access(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_NAME_ACCESS:
                self.visit_name_access(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_IMPORT_NAME:
                self.visit_import_name_access(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_GLOBAL_ACCESS:
                self.visit_global_access(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_DEREF_ACCESS:
                self.visit_deref_access(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_ABSOLUTE_JUMP + OP_RELATIVE_JUMP:
                self.visit_jump(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_CALL:
                self.visit_call(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )
            elif instr.opcode in OP_RETURN:
                self.visit_return(
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_offset,
                )

            # Update the instr_index to repoint at the original instruction
            while node.get_instruction(instr_index) != instr:
                instr_index += 1

            instr_offset += cf.INSTRUCTION_OFFSET_INCREMENT
            instr_index += 1

    def visit_generic(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        # Instrumentation before the original instruction
        node.basic_block[cf.before(instr_index)] = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_generic.__name__,
                lineno=instr.lineno,
            ),
            # Load arguments
            # Current module
            cf.ArtificialInstr("LOAD_CONST", cfg.bytecode_cfg.filename, lineno=instr.lineno),
            # Code object id
            cf.ArtificialInstr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            cf.ArtificialInstr("LOAD_CONST", node.index, lineno=instr.lineno),
            # Instruction opcode
            cf.ArtificialInstr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            cf.ArtificialInstr(
                "LOAD_CONST",
                instr.lineno,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # Instruction number of access
            cf.ArtificialInstr("LOAD_CONST", instr_offset, lineno=instr.lineno),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 6, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

    def visit_local_access(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        instructions = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                lineno=instr.lineno,
            ),
            # Load arguments
            *self._load_args(
                code_object_id,
                node.index,
                instr_offset,
                instr.arg,
                instr,
                cfg.bytecode_cfg.filename,
            ),
            # Argument address
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_FAST", instr.arg, lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_FAST", instr.arg, lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

        match opname[instr.opcode]:
            case "DELETE_FAST":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[cf.before(instr_index)] = instructions
            case "LOAD_FAST" | "STORE_FAST":
                # Instrumentation after the original instruction
                node.basic_block[cf.after(instr_index)] = instructions

    def visit_attr_access(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        instructions = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_attribute_access.__name__,
                lineno=instr.lineno,
            ),
            # A method occupies two slots on top of the stack
            # -> move third up and keep order of upper two
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            # Load arguments
            *self._load_args_with_prop(
                code_object_id,
                node.index,
                instr_offset,
                instr.arg,
                instr,
                cfg.bytecode_cfg.filename,
            ),
            # TOS is object ref -> duplicate for determination of source address,
            # argument address and argument_type
            cf.ArtificialInstr("DUP_TOP", lineno=instr.lineno),
            cf.ArtificialInstr("DUP_TOP", lineno=instr.lineno),
            # Determine source address
            # Load lookup method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.attribute_lookup.__name__,
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            # Load attribute name (second argument)
            cf.ArtificialInstr("LOAD_CONST", instr.arg, lineno=instr.lineno),
            # Call lookup method
            cf.ArtificialInstr("CALL_METHOD", 2, lineno=instr.lineno),
            # Determine argument address
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_ATTR", arg=instr.arg, lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Determine argument type
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_ATTR", arg=instr.arg, lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 10, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

        match opname[instr.opcode]:
            case "LOAD_ATTR" | "DELETE_ATTR" | "IMPORT_FROM" | "LOAD_METHOD":
                # Instrumentation before the original instruction
                node.basic_block[cf.before(instr_index)] = (
                    # Duplicate top of stack to access attribute
                    cf.ArtificialInstr("DUP_TOP", lineno=instr.lineno),
                    *instructions,
                )
            case "STORE_ATTR":
                # Instrumentation mostly after the original instruction
                node.basic_block[cf.override(instr_index)] = (
                    # Execute actual store instruction
                    cf.ArtificialInstr("DUP_TOP", lineno=instr.lineno),
                    cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
                    instr,
                    *instructions,
                )

    def visit_subscr_access(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        instructions = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_attribute_access.__name__,
                lineno=instr.lineno,
            ),
            # A method occupies two slots on top of the stack
            # -> move third up and keep order of upper two
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            # Load arguments
            *self._load_args_with_prop(
                code_object_id,
                node.index,
                instr_offset,
                "None",
                instr,
                cfg.bytecode_cfg.filename,
            ),
            # Source object address
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # No arg address
            cf.ArtificialInstr(
                "LOAD_CONST",
                None,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # No arg type
            cf.ArtificialInstr(
                "LOAD_CONST",
                None,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 10, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

        match opname[instr.opcode]:
            case "STORE_SUBSCR":
                # Instrumentation mostly after the original instruction
                node.basic_block[cf.override(instr_index)] = (
                    # Execute actual store instruction
                    cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
                    cf.ArtificialInstr("DUP_TOP", lineno=instr.lineno),
                    cf.ArtificialInstr("ROT_FOUR", lineno=instr.lineno),
                    cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
                    instr,
                    *instructions,
                )
            case "DELETE_SUBSCR":
                # Instrumentation mostly after the original instruction
                node.basic_block[cf.override(instr_index)] = (
                    # Execute delete instruction
                    cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
                    cf.ArtificialInstr("DUP_TOP", lineno=instr.lineno),
                    cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
                    cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
                    instr,
                    *instructions,
                )
            case "BINARY_SUBSCR":
                # Instrumentation before the original instruction
                node.basic_block[cf.before(instr_index)] = (
                    # Execute access afterwards, prepare stack
                    cf.ArtificialInstr("DUP_TOP_TWO", lineno=instr.lineno),
                    cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
                    *instructions,
                )

    def visit_name_access(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        instructions = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                lineno=instr.lineno,
            ),
            # Load arguments
            *self._load_args(
                code_object_id,
                node.index,
                instr_offset,
                instr.arg,
                instr,
                cfg.bytecode_cfg.filename,
            ),
            # Argument address
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_NAME", instr.arg, lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_NAME", instr.arg, lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

        match opname[instr.opcode]:
            case "DELETE_NAME":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[cf.before(instr_index)] = instructions
            case "STORE_NAME" | "LOAD_NAME" | "IMPORT_NAME":
                # Instrumentation after the original instruction
                node.basic_block[cf.after(instr_index)] = instructions

    def visit_import_name_access(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        # Instrumentation after the original instruction
        node.basic_block[cf.after(instr_index)] = (
            # Execute actual instruction and duplicate module reference on TOS
            cf.ArtificialInstr("DUP_TOP"),
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=instr.lineno),
            *self._load_args_with_prop(
                code_object_id,
                node.index,
                instr_offset,
                instr.arg,
                instr,
                cfg.bytecode_cfg.filename,
            ),
            cf.ArtificialInstr("DUP_TOP", lineno=instr.lineno),
            # Argument address
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

    def visit_global_access(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        instructions = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                lineno=instr.lineno,
            ),
            # Load arguments
            *self._load_args(
                code_object_id,
                node.index,
                instr_offset,
                instr.arg,
                instr,
                cfg.bytecode_cfg.filename,
            ),
            # Argument address
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_GLOBAL", instr.arg, lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            cf.ArtificialInstr("LOAD_GLOBAL", instr.arg, lineno=instr.lineno),
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

        match opname[instr.opcode]:
            case "DELETE_GLOBAL":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[cf.before(instr_index)] = instructions
            case "STORE_GLOBAL" | "LOAD_GLOBAL":
                # Instrumentation after the original instruction
                node.basic_block[cf.after(instr_index)] = instructions

    def visit_deref_access(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        # Load instruction
        if opname[instr.opcode] == "LOAD_CLASSDEREF":
            load_instr = cf.ArtificialInstr("LOAD_CLASSDEREF", instr.arg, lineno=instr.lineno)
        else:
            load_instr = cf.ArtificialInstr("LOAD_DEREF", instr.arg, lineno=instr.lineno)

        instructions = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                lineno=instr.lineno,
            ),
            # Load arguments
            *self._load_args(
                code_object_id,
                node.index,
                instr_offset,
                instr.arg.name,  # type: ignore[union-attr]
                instr,
                cfg.bytecode_cfg.filename,
            ),
            # Argument address
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            load_instr,
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            cf.ArtificialInstr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            load_instr,
            cf.ArtificialInstr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 9, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

        match opname[instr.opcode]:
            case "DELETE_DEREF":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[cf.before(instr_index)] = instructions
            case "STORE_DEREF" | "LOAD_DEREF" | "LOAD_CLASSDEREF":
                # Instrumentation after the original instruction
                node.basic_block[cf.after(instr_index)] = instructions

    def visit_jump(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        # Instrumentation before the original instruction
        node.basic_block[cf.before(instr_index)] = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_jump.__name__,
                lineno=instr.lineno,
            ),
            # Load arguments
            *self._load_args(
                code_object_id,
                node.index,
                instr_offset,
                cfg.bytecode_cfg.get_block_index(instr.arg),  # type: ignore[arg-type]
                instr,
                cfg.bytecode_cfg.filename,
            ),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 7, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

    def visit_call(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        # Trace argument only for calls with integer arguments
        argument = instr.arg if isinstance(instr.arg, int) and instr.arg != UNSET else None

        # Instrumentation before the original instruction
        node.basic_block[cf.before(instr_index)] = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_call.__name__,
                lineno=instr.lineno,
            ),
            # Load arguments
            *self._load_args(
                code_object_id,
                node.index,
                instr_offset,
                argument,
                instr,
                cfg.bytecode_cfg.filename,
            ),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 7, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

    def visit_return(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        # Instrumentation before the original instruction
        # (otherwise we can not read the data)
        node.basic_block[cf.before(instr_index)] = (
            # Load tracing method
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._subject_properties.instrumentation_tracer,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                tracer.InstrumentationExecutionTracer.track_return.__name__,
                lineno=instr.lineno,
            ),
            # Load arguments
            # Current module
            cf.ArtificialInstr("LOAD_CONST", cfg.bytecode_cfg.filename, lineno=instr.lineno),
            # Code object id
            cf.ArtificialInstr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            cf.ArtificialInstr("LOAD_CONST", node.index, lineno=instr.lineno),
            # Instruction opcode
            cf.ArtificialInstr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            cf.ArtificialInstr(
                "LOAD_CONST",
                instr.lineno,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # Instruction number of access
            cf.ArtificialInstr("LOAD_CONST", instr_offset, lineno=instr.lineno),
            # Call tracing method
            cf.ArtificialInstr("CALL_METHOD", 6, lineno=instr.lineno),
            cf.ArtificialInstr("POP_TOP", lineno=instr.lineno),
        )

    @staticmethod
    def _load_args(  # noqa: PLR0917
        code_object_id: int,
        node_id: int,
        offset: int,
        arg,
        instr: Instr,
        file_name: str,
    ) -> tuple[cf.ArtificialInstr, ...]:
        return (
            # Current module
            cf.ArtificialInstr("LOAD_CONST", file_name, lineno=instr.lineno),
            # Code object id
            cf.ArtificialInstr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            cf.ArtificialInstr("LOAD_CONST", node_id, lineno=instr.lineno),
            # Instruction opcode
            cf.ArtificialInstr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            cf.ArtificialInstr(
                "LOAD_CONST",
                instr.lineno,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            # Instruction number of access
            cf.ArtificialInstr("LOAD_CONST", offset, lineno=instr.lineno),
            # Argument name
            cf.ArtificialInstr("LOAD_CONST", arg, lineno=instr.lineno),
        )

    @staticmethod
    def _load_args_with_prop(  # noqa: PLR0917
        code_object_id: int,
        node_id: int,
        offset: int,
        arg,
        instr: Instr,
        file_name: str,
    ) -> tuple[cf.ArtificialInstr, ...]:
        return (
            # Load arguments
            #   Current module
            cf.ArtificialInstr("LOAD_CONST", file_name, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Code object id
            cf.ArtificialInstr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Basic block id
            cf.ArtificialInstr("LOAD_CONST", node_id, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Instruction opcode
            cf.ArtificialInstr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Line number of access
            cf.ArtificialInstr(
                "LOAD_CONST",
                instr.lineno,  # type: ignore[arg-type]
                lineno=instr.lineno,
            ),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Instruction number of access
            cf.ArtificialInstr("LOAD_CONST", offset, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
            #   Argument name
            cf.ArtificialInstr("LOAD_CONST", arg, lineno=instr.lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=instr.lineno),
        )


class DynamicSeedingInstrumentation(transformer.DynamicSeedingInstrumentationAdapter):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.10."""

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
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        maybe_compare_index = self._COMPARE_OP_POS
        maybe_compare = node.try_get_instruction(maybe_compare_index)

        if (
            maybe_compare is not None
            and isinstance(maybe_compare, Instr)
            and maybe_compare.opcode == opmap["COMPARE_OP"]
        ):
            self.visit_compare_op(
                cfg,
                code_object_id,
                node,
                maybe_compare,
                maybe_compare_index,
            )
            return

        maybe_string_func_index = self._STRING_FUNC_POS
        maybe_string_func = node.try_get_instruction(maybe_string_func_index)

        if (
            isinstance(maybe_string_func, Instr)
            and maybe_string_func.opcode == opmap["LOAD_METHOD"]
            and isinstance(maybe_string_func.arg, str)
            and maybe_string_func.arg in DynamicConstantProvider.STRING_FUNCTION_LOOKUP
        ):
            self.visit_string_function_without_arg(
                cfg,
                code_object_id,
                node,
                maybe_string_func,
                maybe_string_func_index,
                maybe_string_func.arg,
            )
            return

        maybe_string_func_with_arg_index = self._STRING_FUNC_POS_WITH_ARG
        maybe_string_func_with_arg = node.try_get_instruction(maybe_string_func_with_arg_index)

        if (
            isinstance(maybe_string_func_with_arg, Instr)
            and maybe_string_func_with_arg.opcode == opmap["LOAD_METHOD"]
            and isinstance(maybe_string_func_with_arg.arg, str)
        ):
            match maybe_string_func_with_arg.arg:
                case "startswith":
                    self.visit_startswith_function(
                        cfg,
                        code_object_id,
                        node,
                        maybe_string_func_with_arg,
                        maybe_string_func_with_arg_index,
                    )
                case "endswith":
                    self.visit_endswith_function(
                        cfg,
                        code_object_id,
                        node,
                        maybe_string_func_with_arg,
                        maybe_string_func_with_arg_index,
                    )

    def visit_compare_op(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        node.basic_block[cf.before(instr_index)] = [
            cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        self._logger.debug("Instrumented compare_op")

    def visit_string_function_without_arg(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        function_name: str,
    ) -> None:
        lineno = instr.lineno

        node.basic_block[cf.before(instr_index + 1)] = [
            cf.ArtificialInstr("DUP_TOP", lineno=lineno),
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value_for_strings.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("LOAD_CONST", function_name, lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 2, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented string function")

    def visit_startswith_function(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        node.basic_block[cf.before(instr_index + 2)] = [
            cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            cf.ArtificialInstr("ROT_TWO", lineno=lineno),
            cf.ArtificialInstr("BINARY_ADD", lineno=lineno),
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented startswith function")

    def visit_endswith_function(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        node.basic_block[cf.before(instr_index + 2)] = [
            cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
            cf.ArtificialInstr("BINARY_ADD", lineno=lineno),
            cf.ArtificialInstr(
                "LOAD_CONST",
                self._dynamic_constant_provider,  # type: ignore[arg-type]
                lineno=lineno,
            ),
            cf.ArtificialInstr(
                "LOAD_METHOD",
                DynamicConstantProvider.add_value.__name__,
                lineno=lineno,
            ),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("ROT_THREE", lineno=lineno),
            cf.ArtificialInstr("CALL_METHOD", 1, lineno=lineno),
            cf.ArtificialInstr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented endswith function")
