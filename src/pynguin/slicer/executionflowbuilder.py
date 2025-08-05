#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
"""Provides classes to reconstruct the execution given an execution trace."""

from __future__ import annotations

import opcode

from dataclasses import dataclass
from types import CodeType
from typing import TYPE_CHECKING

from bytecode.cfg import BasicBlock
from bytecode.instr import BITFLAG2_OPCODES
from bytecode.instr import BITFLAG_OPCODES
from bytecode.instr import UNSET
from bytecode.instr import Instr

from pynguin.instrumentation.version import CALL_OPCODES
from pynguin.instrumentation.version import COND_BRANCH_OPCODES
from pynguin.instrumentation.version import IMPORT_NAME_OPCODES
from pynguin.instrumentation.version import MEMORY_DEF_OPCODES
from pynguin.instrumentation.version import MEMORY_USE_OPCODES
from pynguin.instrumentation.version import RETURNING_OPCODES
from pynguin.instrumentation.version import TRACED_OPCODES
from pynguin.instrumentation.version import YIELDING_OPCODES
from pynguin.instrumentation.version import stack_effects
from pynguin.utils.exceptions import InstructionNotFoundException


if TYPE_CHECKING:
    from pynguin.instrumentation import StackEffects
    from pynguin.instrumentation.controlflow import BasicBlockNode
    from pynguin.instrumentation.tracer import CodeObjectMetaData
    from pynguin.instrumentation.tracer import ExecutionTrace
    from pynguin.slicer.executedinstruction import ExecutedInstruction


class UniqueInstruction(Instr):
    """A representation for concrete occurrences of instructions.

    It combines multiple information sources, including the corresponding
    instruction in the disassembly.
    """

    def __init__(
        self,
        *,
        file: str,
        name: str,
        code_object_id: int,
        node_id: int,
        code_meta: CodeObjectMetaData,
        instr_original_index: int,
        arg=UNSET,
        lineno: int | None = None,
    ):
        """Initializes a unique instruction.

        Args:
            file: The name of the file where the instruction is from
            name: The name of the callable where the instruction is from
            code_object_id: The code object ID containing the instruction
            node_id: The node ID
            code_meta: Meta information about the code object
            instr_original_index: The original index of the instruction in the code object
            arg: Additional arguments
            lineno: The instruction's line number
        """
        self.file = file
        if arg is not UNSET:
            super().__init__(name, arg, lineno=lineno)
        else:
            super().__init__(name, lineno=lineno)
        self.code_object_id = code_object_id
        self.node_id = node_id
        self.instr_original_index = instr_original_index

        node = code_meta.original_cfg.get_basic_block_node(self.node_id)

        assert node is not None, "Invalid basic block node id"

        # The jump target is always the first instruction in a basic block
        self.is_jump_target = instr_original_index == 0 and any(
            basic_block_node.basic_block.get_jump() is node.basic_block
            for basic_block_node in code_meta.original_cfg.basic_block_nodes
        )

    def is_def(self) -> bool:
        """Returns a boolean if the instruction is a definition.

        Returns:
            True if the instructions is a definition, False otherwise.
        """
        return self.opcode in MEMORY_DEF_OPCODES

    def is_use(self) -> bool:
        """Returns a boolean if the instruction is a use.

        Returns:
            True if the instructions is a use, False otherwise.
        """
        return self.opcode in MEMORY_USE_OPCODES

    def is_cond_branch(self) -> bool:
        """Returns a boolean if the instruction is a conditional branching.

        Returns:
            True if the instructions is a conditional branching, False otherwise.
        """
        return self.opcode in COND_BRANCH_OPCODES

    def stack_effects(self, jump: bool = False) -> StackEffects:  # noqa: FBT001, FBT002
        """Returns the stack effects of the instruction.

        Args:
            jump: If the instruction is a jump, this is True, otherwise False.

        Returns:
            The stack effects of the instruction.
        """
        # Check the code of stackeffect of the bytecode library for more info

        arg: int | None
        if not self.require_arg():
            arg = None

        elif self._opcode in BITFLAG_OPCODES and isinstance(self.arg, tuple):
            assert len(self.arg) == 2
            assert self.arg[0] is None or isinstance(self.arg[0], int)
            arg = self.arg[0]

        elif self._opcode in BITFLAG2_OPCODES and isinstance(self.arg, tuple):
            assert len(self.arg) == 3
            assert self.arg[0] is None or isinstance(self.arg[0], int)
            arg = self.arg[0]
        elif not isinstance(self.arg, int) or self.opcode in opcode.hasconst:
            arg = 0
        else:
            arg = self.arg

        effects = stack_effects(self.opcode, arg, jump=jump)

        assert self.stack_effect(jump) == effects.pushes - effects.pops, (
            f"Expected a stack effect of {self.stack_effect(jump)} for "
            f"{self.name} (arg={arg}, jump={jump}) but got {effects.pushes - effects.pops}. "
            f"({effects.pushes} pushes / {effects.pops} pops)"
        )

        return effects

    def __str__(self) -> str:
        if isinstance(self.arg, BasicBlock):
            try:
                first_instr = self.arg[0]
            except IndexError:
                first_instr = None

            if isinstance(first_instr, Instr):
                arg = f"<BB {first_instr.name} lineno={first_instr.lineno}>"
            else:
                arg = "<BB>"
        elif isinstance(self.arg, CodeType):
            arg = f"<CodeObject '{self.arg.co_name}'>"
        else:
            arg = str(self.arg)

        return f"<UniqueInstruction {self.name} arg={arg} lineno={self.lineno}>"

    def __hash__(self):
        return hash((self.name, self.code_object_id, self.node_id, self.instr_original_index))


@dataclass
class LastInstrState:
    """The state at the last instruction.

    When the execution flow is reconstructed with traced instructions there are some
    events which can happen between instructions, e.g. a switch to a different code
    object with a function call.

    All relevant information required to keep track of the exact location of the flow
    is represented here.
    """

    file: str
    last_instr: Instr | None
    code_object_id: int
    basic_block_id: int
    instr_original_index: int
    jump: bool = False
    call: bool = False
    returned: bool = False
    exception: bool = False
    import_start: bool = False
    import_back_call: UniqueInstruction | None = None


@dataclass
class ExecutionFlowBuilderState:
    """Holds the configuration and state of the execution flow builder."""

    bb_id: int
    co_id: int
    file: str
    instr_original_index: int
    jump: bool = False
    call: bool = False
    returned: bool = False
    exception: bool = False
    import_start: bool = False
    import_back_call: UniqueInstruction | None = None


class ExecutionFlowBuilder:
    """The ExecutionFlowBuilder reconstructs the execution flow of a program run.

    It does so in a backwards direction with the help of an execution trace. The trace
    must contain instructions relevant for the control flow of the specific execution.

    Note: The solution here is designed to provide a last instruction whenever possible.
    That means, whenever there is an unexpected mismatch between expected and real last
    traced instruction, it is assumed that an exception occurred and the flow is
    continued at the last traced instruction.
    """

    def __init__(
        self,
        trace: ExecutionTrace,
        known_code_objects: dict[int, CodeObjectMetaData],
    ):
        """Initializes the builder.

        Args:
            trace: The execution trace
            known_code_objects: A dictionary of known code object data
        """
        self.trace = trace
        self.known_code_objects = known_code_objects

    def _finish_basic_block(
        self,
        instr_index: int,
        basic_block_node: BasicBlockNode,
        import_instr: UniqueInstruction | None,
        efb_state: ExecutionFlowBuilderState,
    ) -> LastInstrState:
        last_instr: Instr | None

        # This is the last location where instructions must be reconstructed,
        # so it is either the end or there are remaining instruction in the same
        # code object (and no jump since this would have been traced.)
        if instr_index > 0:
            # Instruction has exactly one possible predecessor
            last_instr = basic_block_node.get_instruction(instr_index - 1)
            efb_state.instr_original_index -= 1
        else:
            last_instr = self._continue_at_last_basic_block(efb_state)

        # Special case inside the special case. Imports are "special calls":
        # the instructions on the module level of the imported module are executed
        # before the IMPORT_NAME instruction ("import back call").
        # This case is the end of these module instructions
        # and we continue before the IMPORT_NAME.
        if last_instr is None and import_instr:
            last_instr = self._continue_before_import(efb_state, import_instr)
            return LastInstrState(
                efb_state.file,
                last_instr,
                efb_state.co_id,
                efb_state.bb_id,
                efb_state.instr_original_index,
                import_start=True,
            )

        return LastInstrState(
            efb_state.file,
            last_instr,
            efb_state.co_id,
            efb_state.bb_id,
            efb_state.instr_original_index,
        )

    def get_last_instruction(  # noqa: PLR0917
        self,
        file: str,
        instr: Instr,
        trace_pos: int,
        instr_original_index: int,
        co_id: int,
        bb_id: int,
        import_instr: UniqueInstruction | None = None,
    ) -> LastInstrState:
        """Look for the last instruction that must have been executed before ``instr``.

        Args:
            file: File of parameter instr
            instr: Instruction for which the instruction executed beforehand is searched
            trace_pos: Position in the execution trace where instr occurs (or, in case
                it is not a traced one, the position of the last instruction traced
                before instr)
            instr_original_index: the original index of the instruction in the code object
            co_id: Code object id of instr
            bb_id: Basic block id of instr
            import_instr: This instruction is necessary if the execution of
                ``instr`` is caused directly (i.e. no calls in between) by an
                IMPORT_NAME instruction. The argument is this import instruction.

        Returns:
            The last instruction and the state when it is executed
        """
        # Find the basic block and the exact location of the current instruction
        basic_block_node = self._get_basic_block_node(co_id, bb_id)

        instr_index, _ = basic_block_node.find_instruction_by_original_index(instr_original_index)

        # Variables to keep track of what happened
        efb_state = ExecutionFlowBuilderState(bb_id, co_id, file, instr_original_index)

        # Special case: if there are not remaining instructions in the trace,
        # finish this basic block
        if trace_pos < 0:
            return self._finish_basic_block(instr_index, basic_block_node, import_instr, efb_state)

        # Get the current instruction in the disassembly for further information
        unique_instr = self._create_unique_instruction(
            efb_state.file,
            instr,
            efb_state.co_id,
            efb_state.bb_id,
            efb_state.instr_original_index,
        )

        # Get the instruction last in the trace
        last_traced_instr = self.trace.executed_instructions[trace_pos]

        # Determine last instruction
        last_instr = self._determine_last_instruction(
            efb_state,
            basic_block_node,
            instr_index,
            last_traced_instr,
            unique_instr,
        )

        # Handle return instruction
        if last_traced_instr.opcode in RETURNING_OPCODES:
            last_instr = self._handle_return_instructions(
                efb_state,
                instr,
                last_instr,
                last_traced_instr,
                unique_instr,
            )

        # Handle method invocation
        if last_instr is None:
            last_instr = self._handle_method_invocation(efb_state, import_instr, last_traced_instr)

        # Handle generators and exceptions
        if last_instr is not None and not efb_state.call and not efb_state.returned:
            last_instr = self._handle_generator_and_exceptions(
                efb_state,
                last_instr,
                last_traced_instr,
            )

        return LastInstrState(
            efb_state.file,
            last_instr,
            efb_state.co_id,
            efb_state.bb_id,
            instr_original_index=efb_state.instr_original_index,
            jump=efb_state.jump,
            call=efb_state.call,
            returned=efb_state.returned,
            exception=efb_state.exception,
            import_start=efb_state.import_start,
            import_back_call=efb_state.import_back_call,
        )

    def _determine_last_instruction(
        self,
        efb_state: ExecutionFlowBuilderState,
        basic_block_node: BasicBlockNode,
        instr_index: int,
        last_traced_instr: ExecutedInstruction,
        unique_instr: UniqueInstruction,
    ) -> Instr | None:
        last_instr: Instr | None

        if instr_index > 0:
            # Instruction has exactly one possible predecessor
            last_instr = basic_block_node.get_instruction(instr_index - 1)
            efb_state.instr_original_index -= 1
        elif unique_instr.is_jump_target:
            # Instruction is the last instruction in this basic block
            # -> decide what to do with this instruction
            # The instruction is a jump target, check if it was jumped to
            if last_traced_instr.is_jump() and last_traced_instr.argument == efb_state.bb_id:
                # It was jumped to this instruction,
                # continue with target basic block of last traced
                assert efb_state.co_id == last_traced_instr.code_object_id, (
                    "Jump to instruction must originate from same code object"
                )
                last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)
                efb_state.jump = True
            else:
                # If this is not a jump target,
                # proceed with previous block (in case there is one)
                last_instr = self._continue_at_last_basic_block(efb_state)
        else:
            # If this is not a jump target,
            # proceed with previous block (in case there is one)
            last_instr = self._continue_at_last_basic_block(efb_state)

        return last_instr

    def _handle_return_instructions(
        self,
        efb_state: ExecutionFlowBuilderState,
        instr: Instr,
        last_instr: Instr | None,
        last_traced_instr: ExecutedInstruction,
        unique_instr: UniqueInstruction,
    ):
        if instr.opcode not in IMPORT_NAME_OPCODES:
            # Coming back from a method call. If last_instr is a call, then the
            # method was called explicitly.
            # If last_instr is not a call, but is traced and does not match the
            # last instruction in the trace, there must have been an implicit call
            # to a magic method (such as __get__). Since we collect instructions
            # invoking these methods, we can safely switch to the called method.
            if last_instr is not None:
                if (last_instr.opcode in CALL_OPCODES) or (
                    last_instr.opcode in TRACED_OPCODES
                    and last_instr.opcode != last_traced_instr.opcode
                ):
                    last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)
                    efb_state.returned = True

            else:
                # Edge case: reached the end of a method, but there is neither
                # a call nor any previous instruction. Can happen for example with
                # setUp(), i.e. when no calls but multiple methods are involved.
                # The only way to resolve this is to continue at the last traced
                # instruction (RETURN).
                last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)
                efb_state.returned = True
        else:
            # Imports are "special calls": The instructions on the module level of
            # the imported module are executed before the IMPORT_NAME instruction
            # We call this an "import back call" here.
            last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)
            efb_state.import_back_call = unique_instr
            efb_state.returned = True
        return last_instr

    def _handle_method_invocation(
        self,
        efb_state: ExecutionFlowBuilderState,
        import_instr: UniqueInstruction | None,
        last_traced_instr: ExecutedInstruction,
    ) -> Instr | None:
        # There is not last instruction in code object,
        # so there must have been a call.
        efb_state.call = True

        last_instr: Instr | None
        if import_instr is None:
            # Switch to another function/method.
            # Either an explicit call (when the last traced is a call instruction),
            # or an implicit call to a magic method. In both cases tracing is
            # continued at the caller.
            last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)
        else:
            # Imports are "special calls": the instructions on the module level of
            # the imported module are executed before the IMPORT_NAME instruction
            # ("import back call"). This case is the end of these module
            # instructions and we continue before the IMPORT_NAME.
            last_instr = self._continue_before_import(efb_state, import_instr)
            efb_state.import_start = True

        return last_instr

    def _handle_generator_and_exceptions(
        self,
        efb_state: ExecutionFlowBuilderState,
        last_instr: Instr,
        last_traced_instr: ExecutedInstruction,
    ) -> Instr:
        if last_instr.opcode in YIELDING_OPCODES:
            # Generators produce an unusual execution flow: the interpreter handles
            # jumps to the respective yield statement internally and we can not see
            # this in the trace. So we assume that this unusual case (explained in
            # the next branch) is not an exception but the return from a generator.
            last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)

        elif last_instr.opcode in TRACED_OPCODES and last_instr.opcode != last_traced_instr.opcode:
            # The last instruction that is determined is not in the trace,
            # despite the fact that it should be. There is only one known remaining
            # reasons for this: during an exception. Tracing continues with the last
            # traced instruction (and probably misses some in between).
            last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)
            efb_state.exception = True

        return last_instr

    def _create_unique_instruction(
        self,
        module: str,
        instr: Instr,
        code_object_id: int,
        node_id: int,
        instr_original_index: int,
    ) -> UniqueInstruction:
        return UniqueInstruction(
            file=module,
            name=instr.name,
            code_object_id=code_object_id,
            node_id=node_id,
            code_meta=self.known_code_objects[code_object_id],
            instr_original_index=instr_original_index,
            arg=instr.arg,
            lineno=instr.lineno,
        )

    def _continue_at_last_traced(
        self,
        last_traced_instr: ExecutedInstruction,
        efb_state: ExecutionFlowBuilderState,
    ) -> Instr:
        efb_state.file = last_traced_instr.file
        efb_state.co_id = last_traced_instr.code_object_id
        efb_state.bb_id = last_traced_instr.node_id

        node = self._get_basic_block_node(
            last_traced_instr.code_object_id,
            last_traced_instr.node_id,
        )

        _, last_instr = node.find_instruction_by_original_index(
            last_traced_instr.instr_original_index
        )

        if (
            last_traced_instr.opcode != last_instr.opcode
            or last_traced_instr.lineno != last_instr.lineno
        ):
            raise InstructionNotFoundException

        efb_state.instr_original_index = last_traced_instr.instr_original_index

        return last_instr

    def _continue_at_last_basic_block(self, efb_state: ExecutionFlowBuilderState) -> Instr | None:
        if efb_state.bb_id <= 0:
            return None

        efb_state.bb_id -= 1
        basic_block_node = self._get_basic_block_node(efb_state.co_id, efb_state.bb_id)
        last_instr = basic_block_node.get_instruction(-1)
        # Set instr_original_index to the last instruction of the new basic block
        efb_state.instr_original_index = sum(1 for _ in basic_block_node.original_instructions) - 1
        return last_instr

    def _continue_before_import(
        self,
        efb_state: ExecutionFlowBuilderState,
        import_instr: UniqueInstruction,
    ) -> Instr | None:
        efb_state.co_id = import_instr.code_object_id
        efb_state.bb_id = import_instr.node_id
        efb_state.instr_original_index = import_instr.instr_original_index

        # Find the basic block and the exact location of the current instruction
        basic_block_node = self._get_basic_block_node(efb_state.co_id, efb_state.bb_id)

        instr_index, _ = basic_block_node.find_instruction_by_original_index(
            efb_state.instr_original_index
        )

        last_instr: Instr | None
        if instr_index > 0:
            # Instruction has exactly one possible predecessor
            last_instr = basic_block_node.get_instruction(instr_index - 1)
            efb_state.instr_original_index -= 1
        else:
            last_instr = self._continue_at_last_basic_block(efb_state)

        return last_instr

    def _get_basic_block_node(self, code_object_id: int, node_id: int) -> BasicBlockNode:
        code_object = self.known_code_objects.get(code_object_id)
        assert code_object, "Unknown code object id"

        basic_block_node = code_object.original_cfg.get_basic_block_node(node_id)
        assert basic_block_node, "Invalid basic block node id"

        return basic_block_node
