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
from bytecode.instr import BITFLAG2_OPCODES, BITFLAG_OPCODES, UNSET, Instr, InstrArg

from pynguin.instrumentation.version import (
    CALL_NAMES,
    COND_BRANCH_NAMES,
    IMPORT_NAME_NAMES,
    MEMORY_DEF_NAMES,
    MEMORY_USE_NAMES,
    RETURNING_NAMES,
    TRACED_NAMES,
    YIELDING_NAMES,
    stack_effects,
)
from pynguin.slicer.executedinstruction import ExecutedAttributeInstruction

if TYPE_CHECKING:
    from pynguin.instrumentation import StackEffects
    from pynguin.instrumentation.controlflow import BasicBlockNode
    from pynguin.instrumentation.tracer import CodeObjectMetaData, ExecutionTrace
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
        instr_original_index: int,
        is_method: bool,
        is_jump_target: bool,
        arg: InstrArg = UNSET,
        lineno: int | None = None,
    ):
        """Initializes a unique instruction.

        Args:
            file: The name of the file where the instruction is from
            name: The name of the callable where the instruction is from
            code_object_id: The code object ID containing the instruction
            node_id: The node ID
            instr_original_index: The original index of the instruction in the code object
            is_method: Whether the instruction is a method call
            is_jump_target: Whether the instruction is a jump target
            arg: Additional arguments
            lineno: The instruction's line number
        """
        if arg is not UNSET:
            super().__init__(name, arg, lineno=lineno)
        else:
            super().__init__(name, lineno=lineno)
        self.file = file
        self.code_object_id = code_object_id
        self.node_id = node_id
        self.instr_original_index = instr_original_index
        self.is_method = is_method
        self.is_jump_target = is_jump_target

    @property
    def is_traced(self) -> bool:
        """Returns a boolean if the instruction is traced.

        Returns:
            True if the instruction is traced, False otherwise.
        """
        return self.name in TRACED_NAMES

    @property
    def is_def(self) -> bool:
        """Returns a boolean if the instruction is a definition.

        Returns:
            True if the instructions is a definition, False otherwise.
        """
        return self.name in MEMORY_DEF_NAMES

    @property
    def is_use(self) -> bool:
        """Returns a boolean if the instruction is a use.

        Returns:
            True if the instructions is a use, False otherwise.
        """
        return self.name in MEMORY_USE_NAMES

    @property
    def is_cond_branch(self) -> bool:
        """Returns a boolean if the instruction is a conditional branching.

        Returns:
            True if the instructions is a conditional branching, False otherwise.
        """
        return self.name in COND_BRANCH_NAMES

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


@dataclass(frozen=True)
class InstrState:
    """The state after the backward execution of some instructions.

    When the execution flow is reconstructed with traced instructions there are some
    events which can happen between instructions, e.g. a switch to a different code
    object with a function call.

    All relevant information required to keep track of the exact location of the flow
    is represented here.
    """

    instr: UniqueInstruction
    trace_position: int
    traced_instr: ExecutedInstruction | None
    jump: bool = False
    call: bool = False
    returned: bool = False
    exception: bool = False
    import_start: bool = False
    import_back_call: UniqueInstruction | None = None


@dataclass
class ExecutionFlowBuilderState:
    """Holds the configuration and state of the execution flow builder."""

    previous_instr: Instr | None
    previous_file: str
    previous_code_object_id: int
    previous_node_id: int
    previous_instr_original_index: int
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
    ) -> None:
        """Initializes the builder.

        Args:
            trace: The execution trace
            known_code_objects: A dictionary of known code object data
        """
        self._trace = trace
        self._known_code_objects = known_code_objects

    def create_instruction_state(self, trace_position: int) -> InstrState:
        """Creates an instruction state starting from the given trace position.

        Args:
            trace_position: Position in the execution trace where the first traced instr occurs
                (or, in case it is not a traced one, the position of the last instruction
                traced before instr)

        Returns:
            The instruction state
        """
        traced_instr = self._trace.executed_instructions[trace_position]
        node, _ = self._get_node(traced_instr.code_object_id, traced_instr.node_id)
        _, original_instr = node.find_instruction_by_original_index(
            traced_instr.instr_original_index
        )

        unique_instr = self._create_unique_instruction(
            file=traced_instr.file,
            name=traced_instr.name,
            code_object_id=traced_instr.code_object_id,
            node_id=traced_instr.node_id,
            instr_original_index=traced_instr.instr_original_index,
            arg=original_instr.arg,
            lineno=traced_instr.lineno,
            traced_instr=traced_instr,
        )

        return InstrState(
            instr=unique_instr,
            trace_position=trace_position,
            traced_instr=self._trace.executed_instructions[trace_position],
            import_back_call=None,
        )

    def get_previous_instruction_state(
        self,
        state: InstrState,
        import_back_call: UniqueInstruction | None = None,
    ) -> InstrState | None:
        """Get the state that was before the current instruction state.

        Args:
            state: The current instruction state
            import_back_call: This instruction is necessary if the execution of
                ``state.instr`` is caused directly (i.e. no calls in between) by an
                IMPORT_NAME instruction. The argument is this import instruction.

        Returns:
            The previous instruction state, or None if there is no previous instruction state
        """
        instr = state.instr
        previous_trace_position = (
            state.trace_position - 1 if instr.is_traced else state.trace_position
        )

        efb_state = ExecutionFlowBuilderState(
            previous_instr=None,
            previous_file=instr.file,
            previous_code_object_id=instr.code_object_id,
            previous_node_id=instr.node_id,
            previous_instr_original_index=instr.instr_original_index,
            import_back_call=import_back_call,
        )

        # Special case: if there are not remaining instructions in the trace,
        # finish this basic block
        if previous_trace_position < 0:
            self._finish_basic_block(efb_state)

            return self._create_instr_state(efb_state, previous_trace_position, None)

        previous_traced_instr = self._trace.executed_instructions[previous_trace_position]
        self._determine_previous_instruction(efb_state, previous_traced_instr, instr)
        self._handle_return_instructions(efb_state, previous_traced_instr, instr)
        self._handle_method_invocation(efb_state, previous_traced_instr)
        self._handle_generator_and_exceptions(efb_state, previous_traced_instr)

        return self._create_instr_state(efb_state, previous_trace_position, previous_traced_instr)

    def _get_node(
        self, code_object_id: int, node_id: int
    ) -> tuple[BasicBlockNode, CodeObjectMetaData]:
        code_meta = self._known_code_objects[code_object_id]
        node = code_meta.cfg.get_basic_block_node(node_id)
        return node, code_meta

    def _create_unique_instruction(  # noqa: PLR0917
        self,
        file: str,
        name: str,
        code_object_id: int,
        node_id: int,
        instr_original_index: int,
        arg: InstrArg,
        lineno: int | None,
        traced_instr: ExecutedInstruction | None,
    ) -> UniqueInstruction:
        node, code_meta = self._get_node(code_object_id, node_id)

        # The jump target is always the first instruction in a basic block
        is_jump_target = instr_original_index == 0 and any(
            basic_block_node.basic_block.get_jump() is node.basic_block
            for basic_block_node in code_meta.cfg.basic_block_nodes
        )

        is_method = (
            isinstance(traced_instr, ExecutedAttributeInstruction) and traced_instr.is_method
        )

        return UniqueInstruction(
            file=file,
            name=name,
            code_object_id=code_object_id,
            node_id=node_id,
            instr_original_index=instr_original_index,
            is_method=is_method,
            is_jump_target=is_jump_target,
            arg=arg,
            lineno=lineno,
        )

    def _create_instr_state(
        self,
        efb_state: ExecutionFlowBuilderState,
        previous_trace_position: int,
        previous_traced_instr: ExecutedInstruction | None,
    ) -> InstrState | None:
        if efb_state.previous_instr is None:
            return None

        instr = self._create_unique_instruction(
            file=efb_state.previous_file,
            name=efb_state.previous_instr.name,
            code_object_id=efb_state.previous_code_object_id,
            node_id=efb_state.previous_node_id,
            instr_original_index=efb_state.previous_instr_original_index,
            arg=efb_state.previous_instr.arg,
            lineno=efb_state.previous_instr.lineno,
            traced_instr=previous_traced_instr,
        )

        traced_instr = (
            self._trace.executed_instructions[previous_trace_position] if instr.is_traced else None
        )

        return InstrState(
            instr=instr,
            trace_position=previous_trace_position,
            traced_instr=traced_instr,
            jump=efb_state.jump,
            call=efb_state.call,
            returned=efb_state.returned,
            exception=efb_state.exception,
            import_start=efb_state.import_start,
            import_back_call=efb_state.import_back_call,
        )

    def _decrease_instr_original_index(self, efb_state: ExecutionFlowBuilderState) -> bool:
        node, _ = self._get_node(efb_state.previous_code_object_id, efb_state.previous_node_id)

        previous_instr_original_index = efb_state.previous_instr_original_index - 1

        if previous_instr_original_index < 0:
            return False

        _, efb_state.previous_instr = node.find_instruction_by_original_index(
            previous_instr_original_index
        )

        efb_state.previous_instr_original_index = previous_instr_original_index

        return True

    def _finish_basic_block(self, efb_state: ExecutionFlowBuilderState) -> None:
        # This is the last location where instructions must be reconstructed,
        # so it is either the end or there are remaining instruction in the same
        # code object (and no jump since this would have been traced.)
        if not self._decrease_instr_original_index(efb_state):
            self._continue_at_last_basic_block(efb_state)

        # Special case inside the special case. Imports are "special calls":
        # the instructions on the module level of the imported module are executed
        # before the IMPORT_NAME instruction ("import back call").
        # This case is the end of these module instructions
        # and we continue before the IMPORT_NAME.
        if efb_state.previous_instr is None and efb_state.import_back_call is not None:
            self._continue_before_import(efb_state)

    def _determine_previous_instruction(
        self,
        efb_state: ExecutionFlowBuilderState,
        previous_traced_instr: ExecutedInstruction,
        instr: UniqueInstruction,
    ) -> None:
        if not self._decrease_instr_original_index(efb_state):
            if (
                instr.is_jump_target
                and previous_traced_instr.is_jump()
                and previous_traced_instr.argument == efb_state.previous_node_id
            ):
                # The previous instruction jumps to the current instruction,
                # so we continue at the previous traced instruction.
                assert efb_state.previous_code_object_id == previous_traced_instr.code_object_id, (
                    "Jump to instruction must originate from same code object"
                )
                self._continue_at_previous_traced(previous_traced_instr, efb_state)
                efb_state.jump = True
            else:
                # This is not a jump target, so proceed with previous block (in case there is one)
                self._continue_at_last_basic_block(efb_state)

    def _handle_return_instructions(
        self,
        efb_state: ExecutionFlowBuilderState,
        previous_traced_instr: ExecutedInstruction,
        instr: UniqueInstruction,
    ) -> None:
        if previous_traced_instr.name not in RETURNING_NAMES:
            return

        if instr.name in IMPORT_NAME_NAMES:
            # Imports are "special calls": The instructions on the module level of
            # the imported module are executed before the IMPORT_NAME instruction
            # We call this an "import back call" here.
            self._continue_at_previous_traced(previous_traced_instr, efb_state)
            efb_state.import_back_call = instr
            efb_state.returned = True
            return

        if efb_state.previous_instr is None:
            # Edge case: reached the end of a method, but there is neither
            # a call nor any previous instruction. Can happen for example with
            # setUp(), i.e. when no calls but multiple methods are involved.
            # The only way to resolve this is to continue at the last traced
            # instruction (RETURN).
            self._continue_at_previous_traced(previous_traced_instr, efb_state)
            efb_state.returned = True
            return

        # Coming back from a method call. If last_instr is a call, then the
        # method was called explicitly.
        # If last_instr is not a call, but is traced and does not match the
        # last instruction in the trace, there must have been an implicit call
        # to a magic method (such as __get__). Since we collect instructions
        # invoking these methods, we can safely switch to the called method.
        if (efb_state.previous_instr.name in CALL_NAMES) or (
            efb_state.previous_instr.name in TRACED_NAMES
            and efb_state.previous_instr.opcode != previous_traced_instr.opcode
        ):
            self._continue_at_previous_traced(previous_traced_instr, efb_state)
            efb_state.returned = True

    def _handle_method_invocation(
        self,
        efb_state: ExecutionFlowBuilderState,
        previous_traced_instr: ExecutedInstruction,
    ) -> None:
        if efb_state.previous_instr is not None:
            return

        # There is no previous instruction in code object, so there must have been a call.
        efb_state.call = True

        if efb_state.import_back_call is not None:
            # Imports are "special calls": the instructions on the module level of
            # the imported module are executed before the IMPORT_NAME instruction
            # ("import back call"). This case is the end of these module
            # instructions and we continue before the IMPORT_NAME.
            self._continue_before_import(efb_state)

        # Switch to another function/method.
        # Either an explicit call (when the previous traced is a call instruction),
        # or an implicit call to a magic method. In both cases tracing is
        # continued at the caller.
        self._continue_at_previous_traced(previous_traced_instr, efb_state)

    def _handle_generator_and_exceptions(
        self,
        efb_state: ExecutionFlowBuilderState,
        previous_traced_instr: ExecutedInstruction,
    ) -> None:
        if efb_state.previous_instr is None or efb_state.call or efb_state.returned:
            return

        if efb_state.previous_instr.name in YIELDING_NAMES:
            # Generators produce an unusual execution flow: the interpreter handles
            # jumps to the respective yield statement internally and we can not see
            # this in the trace. So we assume that this unusual case (explained in
            # the next branch) is not an exception but the return from a generator.
            self._continue_at_previous_traced(previous_traced_instr, efb_state)

        if (
            efb_state.previous_instr.name in TRACED_NAMES
            and efb_state.previous_instr.opcode != previous_traced_instr.opcode
        ):
            # The last instruction that is determined is not in the trace,
            # despite the fact that it should be. There is only one known remaining
            # reasons for this: during an exception. Tracing continues with the last
            # traced instruction (and probably misses some in between).
            self._continue_at_previous_traced(previous_traced_instr, efb_state)
            efb_state.exception = True

    def _continue_at_previous_traced(
        self,
        previous_traced_instr: ExecutedInstruction,
        efb_state: ExecutionFlowBuilderState,
    ) -> None:
        efb_state.previous_file = previous_traced_instr.file
        efb_state.previous_code_object_id = previous_traced_instr.code_object_id
        efb_state.previous_node_id = previous_traced_instr.node_id
        efb_state.previous_instr_original_index = previous_traced_instr.instr_original_index

        node, _ = self._get_node(efb_state.previous_code_object_id, efb_state.previous_node_id)

        _, efb_state.previous_instr = node.find_instruction_by_original_index(
            previous_traced_instr.instr_original_index
        )
        assert (
            previous_traced_instr.opcode == efb_state.previous_instr.opcode
            or previous_traced_instr.lineno == efb_state.previous_instr.lineno
        ), (
            f"Executed instruction {previous_traced_instr} references a wrong bytecode "
            f"instruction {efb_state.previous_instr}."
        )

    def _continue_at_last_basic_block(self, efb_state: ExecutionFlowBuilderState) -> None:
        if efb_state.previous_node_id <= 0:
            return

        efb_state.previous_node_id -= 1
        node, _ = self._get_node(efb_state.previous_code_object_id, efb_state.previous_node_id)

        try:
            _, instr = node.find_instruction_by_original_index(-1)
        except IndexError:
            # No instruction in the basic block, so we continue at the last basic block
            self._continue_at_last_basic_block(efb_state)
            return

        # Set instr_original_index to the last instruction of the new basic block
        efb_state.previous_instr = instr
        efb_state.previous_instr_original_index = sum(1 for _ in node.original_instructions) - 1

    def _continue_before_import(self, efb_state: ExecutionFlowBuilderState) -> None:
        import_back_call = efb_state.import_back_call
        assert import_back_call is not None, (
            "Cannot continue before import without an import back call"
        )

        efb_state.previous_code_object_id = import_back_call.code_object_id
        efb_state.previous_node_id = import_back_call.node_id
        efb_state.previous_instr_original_index = import_back_call.instr_original_index

        if not self._decrease_instr_original_index(efb_state):
            self._continue_at_last_basic_block(efb_state)

        efb_state.import_start = True
