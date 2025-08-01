#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides version-specific functions for Python 3.11."""

from __future__ import annotations

from opcode import opmap
from opcode import opname
from typing import TYPE_CHECKING
from typing import ClassVar

from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation.version.common import AST_FILENAME
from pynguin.instrumentation.version.common import COMPARE_OP_POS
from pynguin.instrumentation.version.common import JUMP_OP_POS
from pynguin.instrumentation.version.common import (
    CheckedCoverageInstrumentationVisitorMethod,
)
from pynguin.instrumentation.version.common import InstrumentationArgument
from pynguin.instrumentation.version.common import InstrumentationClassDeref
from pynguin.instrumentation.version.common import InstrumentationConstantLoad
from pynguin.instrumentation.version.common import InstrumentationDeref
from pynguin.instrumentation.version.common import InstrumentationFastLoad
from pynguin.instrumentation.version.common import InstrumentationGlobalLoad
from pynguin.instrumentation.version.common import InstrumentationInstructionsGenerator
from pynguin.instrumentation.version.common import InstrumentationMethodCall
from pynguin.instrumentation.version.common import InstrumentationNameLoad
from pynguin.instrumentation.version.common import InstrumentationSetupAction
from pynguin.instrumentation.version.common import InstrumentationStackValue
from pynguin.instrumentation.version.common import to_opcodes


if TYPE_CHECKING:
    from bytecode.instr import _UNSET

from pynguin.instrumentation.version import python3_10

from .python3_10 import ACCESS_OPCODES
from .python3_10 import CALL_OPCODES
from .python3_10 import CLOSURE_LOAD_OPCODES
from .python3_10 import EXTENDED_ARG_OPCODES
from .python3_10 import IMPORT_FROM_OPCODES
from .python3_10 import IMPORT_NAME_OPCODES
from .python3_10 import LOAD_DEREF_OPCODES
from .python3_10 import LOAD_FAST_OPCODES
from .python3_10 import LOAD_GLOBAL_OPCODES
from .python3_10 import LOAD_NAME_OPCODES
from .python3_10 import MEMORY_DEF_OPCODES
from .python3_10 import MEMORY_USE_OPCODES
from .python3_10 import MODIFY_DEREF_OPCODES
from .python3_10 import MODIFY_FAST_OPCODES
from .python3_10 import MODIFY_GLOBAL_OPCODES
from .python3_10 import MODIFY_NAME_OPCODES
from .python3_10 import RETURNING_OPCODES
from .python3_10 import STORE_NAME_OPCODES
from .python3_10 import STORE_OPCODES
from .python3_10 import TRACED_OPCODES
from .python3_10 import YIELDING_OPCODES
from .python3_10 import add_for_loop_no_yield_nodes
from .python3_10 import end_with_explicit_return_none
from .python3_10 import is_conditional_jump
from .python3_10 import stack_effect


__all__ = [
    "ACCESS_OPCODES",
    "CALL_OPCODES",
    "CLOSURE_LOAD_OPCODES",
    "COND_BRANCH_OPCODES",
    "EXTENDED_ARG_OPCODES",
    "IMPORT_FROM_OPCODES",
    "IMPORT_NAME_OPCODES",
    "LOAD_DEREF_OPCODES",
    "LOAD_FAST_OPCODES",
    "LOAD_GLOBAL_OPCODES",
    "LOAD_NAME_OPCODES",
    "MEMORY_DEF_OPCODES",
    "MEMORY_USE_OPCODES",
    "MODIFY_DEREF_OPCODES",
    "MODIFY_FAST_OPCODES",
    "MODIFY_GLOBAL_OPCODES",
    "MODIFY_NAME_OPCODES",
    "RETURNING_OPCODES",
    "STORE_NAME_OPCODES",
    "STORE_OPCODES",
    "TRACED_OPCODES",
    "YIELDING_OPCODES",
    "BranchCoverageInstrumentation",
    "CheckedCoverageInstrumentation",
    "DynamicSeedingInstrumentation",
    "LineCoverageInstrumentation",
    "add_for_loop_no_yield_nodes",
    "end_with_explicit_return_none",
    "get_branch_type",
    "is_conditional_jump",
    "stack_effect",
]


COND_BRANCH_OPCODES = to_opcodes(
    "POP_JUMP_FORWARD_IF_TRUE",
    "POP_JUMP_BACKWARD_IF_TRUE",
    "POP_JUMP_FORWARD_IF_NOT_NONE",
    "POP_JUMP_BACKWARD_IF_NOT_NONE",
    "JUMP_IF_TRUE_OR_POP",
    "POP_JUMP_FORWARD_IF_FALSE",
    "POP_JUMP_BACKWARD_IF_FALSE",
    "POP_JUMP_FORWARD_IF_NONE",
    "POP_JUMP_BACKWARD_IF_NONE",
    "JUMP_IF_FALSE_OR_POP",
    "FOR_ITER",
)

JUMP_OPCODES = COND_BRANCH_OPCODES + to_opcodes(
    "JUMP_FORWARD",
    "JUMP_BACKWARD",
    "JUMP_BACKWARD_NO_INTERRUPT",
    "BEFORE_WITH",
    "BEFORE_ASYNC_WITH",
)


def get_branch_type(opcode: int) -> bool | None:  # noqa: D103
    match opname[opcode]:
        case (
            "POP_JUMP_FORWARD_IF_TRUE"
            | "POP_JUMP_BACKWARD_IF_TRUE"
            | "POP_JUMP_FORWARD_IF_NOT_NONE"
            | "POP_JUMP_BACKWARD_IF_NOT_NONE"
            | "JUMP_IF_TRUE_OR_POP"
        ):
            return True
        case (
            "POP_JUMP_FORWARD_IF_FALSE"
            | "POP_JUMP_BACKWARD_IF_FALSE"
            | "POP_JUMP_FORWARD_IF_NONE"
            | "POP_JUMP_BACKWARD_IF_NONE"
            | "JUMP_IF_FALSE_OR_POP"
            | "FOR_ITER"
        ):
            return False
        case _:
            return None


class Python311InstrumentationInstructionsGenerator(InstrumentationInstructionsGenerator):
    """Generates instrumentation instructions for Python 3.11."""

    @classmethod
    def generate_setup_instructions(
        cls,
        setup_action: InstrumentationSetupAction,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match setup_action:
            case (
                InstrumentationSetupAction.NO_ACTION
                | InstrumentationSetupAction.COPY_FIRST
                | InstrumentationSetupAction.COPY_FIRST_TWO
            ):
                # We can just directly copy simple values from the right place
                # in Python 3.11 so no need to duplicate them in the setup.
                return ()
            case InstrumentationSetupAction.COPY_FIRST_SHIFT_DOWN_TWO:
                return (
                    cf.ArtificialInstr("SWAP", 2, lineno=lineno),
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_SECOND:
                # We need to copy the second value from the stack because
                # it will be placed on the first position in the stack
                return (cf.ArtificialInstr("COPY", 2, lineno=lineno),)
            case InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_TWO:
                return (
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 2, lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_THREE:
                return (
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 4, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 3, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 2, lineno=lineno),
                )
            case InstrumentationSetupAction.ADD_FIRST_TWO:
                return (
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                    cf.ArtificialInstr("BINARY_OP", 0, lineno=lineno),
                )
            case InstrumentationSetupAction.ADD_FIRST_TWO_REVERSED:
                return (
                    cf.ArtificialInstr("COPY", 1, lineno=lineno),
                    cf.ArtificialInstr("COPY", 3, lineno=lineno),
                    cf.ArtificialInstr("BINARY_OP", 0, lineno=lineno),
                )
            case _:
                raise ValueError(f"Unsupported instrumentation setup action: {setup_action}.")

    @classmethod
    def _generate_argument_instruction(
        cls,
        arg: InstrumentationArgument,
        position: int,
        lineno: int | _UNSET | None,
    ) -> cf.ArtificialInstr:
        match arg:
            case InstrumentationConstantLoad(value):
                return cf.ArtificialInstr("LOAD_CONST", value, lineno=lineno)  # type: ignore[arg-type]
            case InstrumentationFastLoad(name):
                return cf.ArtificialInstr("LOAD_FAST", name, lineno=lineno)
            case InstrumentationNameLoad(name):
                return cf.ArtificialInstr("LOAD_NAME", name, lineno=lineno)
            case InstrumentationGlobalLoad(name):
                return cf.ArtificialInstr("LOAD_GLOBAL", name, lineno=lineno)
            case InstrumentationDeref(name):
                return cf.ArtificialInstr("LOAD_DEREF", name, lineno=lineno)
            case InstrumentationClassDeref(name):
                return cf.ArtificialInstr("LOAD_CLASSDEREF", name, lineno=lineno)
            case InstrumentationStackValue():
                return cf.ArtificialInstr("COPY", position + 2 + arg.value, lineno=lineno)

    @classmethod
    def generate_method_call_instructions(
        cls,
        method_call: InstrumentationMethodCall,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        return (
            cf.ArtificialInstr("LOAD_CONST", method_call.self, lineno=lineno),
            cf.ArtificialInstr("LOAD_METHOD", method_call.method_name, lineno=lineno),
            *(
                cls._generate_argument_instruction(arg, position, lineno=lineno)
                for position, arg in enumerate(method_call.args)
            ),
            cf.ArtificialInstr("PRECALL", len(method_call.args), lineno=lineno),
            cf.ArtificialInstr("CALL", len(method_call.args), lineno=lineno),
        )

    @classmethod
    def generate_teardown_instructions(
        cls,
        setup_action: InstrumentationSetupAction,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match setup_action:
            case (
                InstrumentationSetupAction.NO_ACTION
                | InstrumentationSetupAction.COPY_FIRST
                | InstrumentationSetupAction.COPY_FIRST_TWO
            ):
                # We did not copy anything in the setup so we do not need to remove anything
                # except the return value of the method call.
                return (cf.ArtificialInstr("POP_TOP", lineno=lineno),)
            case (
                InstrumentationSetupAction.COPY_FIRST_SHIFT_DOWN_TWO
                | InstrumentationSetupAction.COPY_SECOND
                | InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_TWO
                | InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_THREE
                | InstrumentationSetupAction.ADD_FIRST_TWO
                | InstrumentationSetupAction.ADD_FIRST_TWO_REVERSED
            ):
                # We need to remove the value we copied in the setup and the return value
                # of the method call.
                return (
                    cf.ArtificialInstr("POP_TOP", lineno=lineno),
                    cf.ArtificialInstr("POP_TOP", lineno=lineno),
                )
            case _:
                raise ValueError(f"Unsupported instrumentation setup action: {setup_action}.")


class BranchCoverageInstrumentation(python3_10.BranchCoverageInstrumentation):
    """Specialized instrumentation adapter for branch coverage in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    def visit_node(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        maybe_jump_index = JUMP_OP_POS
        maybe_jump = node.try_get_instruction(maybe_jump_index)

        if maybe_jump is None:
            return

        if maybe_jump.opcode == opmap["FOR_ITER"]:
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
            COMPARE_OP_POS,
        )

        if maybe_compare.opcode in python3_10.COMPARE_OPCODES:
            self.visit_compare_based_conditional_jump(
                cfg,
                code_object_id,
                node,
                maybe_compare,
                maybe_compare_index,
            )
            return

        if maybe_compare.opcode == opmap["CHECK_EXC_MATCH"]:
            self.visit_exception_based_conditional_jump(
                cfg,
                code_object_id,
                node,
                maybe_compare,
                maybe_compare_index,
            )
            return

        self.visit_bool_based_conditional_jump(
            cfg,
            code_object_id,
            node,
            maybe_jump,
            maybe_jump_index,
        )


class LineCoverageInstrumentation(python3_10.LineCoverageInstrumentation):
    """Specialized instrumentation adapter for line coverage in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    def visit_node(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        lineno: int | _UNSET | None = None

        # The bytecode instructions change during the iteration but it is something supported
        for instr_index, instr in enumerate(node.instructions):
            if (
                instr.lineno == lineno
                or instr.opcode == opmap["RESUME"]
                or cfg.bytecode_cfg.filename == AST_FILENAME
            ):
                continue

            lineno = instr.lineno

            self.visit_line(cfg, code_object_id, node, instr, instr_index)


class CheckedCoverageInstrumentation(python3_10.CheckedCoverageInstrumentation):
    """Specialized instrumentation adapter for checked coverage in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    METHODS: ClassVar[
        dict[
            tuple[int, ...],
            CheckedCoverageInstrumentationVisitorMethod,
        ]
    ] = {
        python3_10.OPERATION_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_generic,
        python3_10.ACCESS_FAST_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_local_access,  # noqa: E501
        python3_10.ATTRIBUTES_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_attr_access,
        python3_10.ACCESS_SUBSCR_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_subscr_access,  # noqa: E501
        python3_10.ACCESS_NAME_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_name_access,
        python3_10.IMPORT_NAME_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_import_name_access,  # noqa: E501
        python3_10.ACCESS_GLOBAL_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_global_access,  # noqa: E501
        python3_10.ACCESS_DEREF_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_deref_access,  # noqa: E501
        JUMP_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_jump,
        python3_10.CALL_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_call,
        python3_10.RETURNING_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_return,
    }


# If one of the considered string functions needing no argument is used in the if
# statement, it will be loaded in the third last position. After it comes the
# call of the method and the jump operation.
STRING_FUNC_POS = -4

# If one of the considered string functions needing one argument is used in the if
# statement, it will be loaded in the fourth last position. After it comes the
# load of the argument, the call of the method and the jump operation.
STRING_FUNC_POS_WITH_ARG = -5


class DynamicSeedingInstrumentation(python3_10.DynamicSeedingInstrumentation):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    STRING_FUNC_POS: ClassVar[int] = STRING_FUNC_POS
    STRING_FUNC_POS_WITH_ARG: ClassVar[int] = STRING_FUNC_POS_WITH_ARG
