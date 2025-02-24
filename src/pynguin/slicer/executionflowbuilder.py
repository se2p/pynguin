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

import dis

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bytecode import Instr

import pynguin.utils.opcodes as op

from pynguin.utils.exceptions import InstructionNotFoundException


UNSET = object()

if TYPE_CHECKING:
    from pynguin.instrumentation.instrumentation import CodeObjectMetaData
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
        offset: int,
        arg=UNSET,
        lineno: int | None = None,
        in_slice: bool = False,
    ):
        """Initializes a unique instruction.

        Args:
            file: The name of the file where the instruction is from
            name: The name of the callable where the instruction is from
            code_object_id: The code object ID containing the instruction
            node_id: The node ID
            code_meta: Meta information about the code object
            offset: The offset of the instruction in the code object
            arg: Additional arguments
            lineno: The instruction's line number
            in_slice: Whether the instruction is part of a slice
        """
        self.file = file
        if arg is not UNSET:
            super().__init__(name, arg, lineno=lineno)
        else:
            super().__init__(name, lineno=lineno)
        self.code_object_id = code_object_id
        self.node_id = node_id
        self.offset = offset

        # Additional information from disassembly
        dis_instr = self.locate_in_disassembly(list(dis.get_instructions(code_meta.code_object)))
        self.dis_arg = dis_instr.arg
        self.is_jump_target = dis_instr.is_jump_target

        self._in_slice = in_slice

    @property
    def in_slice(self) -> bool:
        """Returns a boolean if the instruction is inside the slice.

        Returns:
            True if the instructions is part of the slice, False otherwise.
        """
        return self._in_slice

    @in_slice.setter
    def in_slice(self, in_slice) -> None:
        """Sets whether the instruction is inside the slice.

        Args:
            in_slice: whether the instruction is inside the slice
        """
        self._in_slice = in_slice

    def is_def(self) -> bool:
        """Returns a boolean if the instruction is a definition.

        Returns:
            True if the instructions is a definition, False otherwise.
        """
        return self.opcode in op.MEMORY_DEF_INSTRUCTIONS

    def is_use(self) -> bool:
        """Returns a boolean if the instruction is a use.

        Returns:
            True if the instructions is a use, False otherwise.
        """
        return self.opcode in op.MEMORY_USE_INSTRUCTIONS

    def is_cond_branch(self) -> bool:
        """Returns a boolean if the instruction is a conditional branching.

        Returns:
            True if the instructions is a conditional branching, False otherwise.
        """
        return self.opcode in op.COND_BRANCH_INSTRUCTIONS

    def locate_in_disassembly(self, disassembly) -> dis.Instruction:
        """Retrieves the instruction inside disassembled bytecode.

        Args:
            disassembly: the disassembled bytecode containing the instruction

        Returns:
            The instruction from withing the bytecode.

        Raises:
            InstructionNotFoundException: If the instruction is not
                located in the code object.
        """
        # EXTENDED_ARG instructions are not counted for instrumented offsets,
        # which has to be compensated here
        offset_offset = 0

        for dis_instr in disassembly:
            if dis_instr.opcode == op.EXTENDED_ARG:
                offset_offset += 2

            if dis_instr.opcode == self.opcode and dis_instr.offset == (
                self.offset + offset_offset
            ):
                return dis_instr

        raise InstructionNotFoundException

    def __hash__(self):
        return hash((self.name, self.code_object_id, self.node_id, self.offset))


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
    last_instr: Instr
    code_object_id: int
    basic_block_id: int
    offset: int
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
    offset: int
    jump: bool = False
    call: bool = False
    returned: bool = False
    exception: bool = False
    import_start: bool = False
    import_back_call: UniqueInstruction | None = None


class ExecutionFlowBuilder:
    """The ExecutionFlowBuilder reconstructs the execution flow of a program run.

    It does so in a backwards direction with the help of an execution trace.  The trace
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
        basic_block: list[Instr],
        import_instr: UniqueInstruction | None,
        efb_state: ExecutionFlowBuilderState,
    ) -> LastInstrState:
        # This is the last location where instructions must be reconstructed,
        # so it is either the end or there are remaining instruction in the same
        # code object (and no jump since this would have been traced.)
        if instr_index > 0:
            # Instruction has exactly one possible predecessor
            last_instr = basic_block[instr_index - 1]
            efb_state.offset -= 2
        else:
            last_instr = self._continue_at_last_basic_block(efb_state)

        # Special case inside the special case. Imports are "special calls":
        # the instructions on the module level of the imported module are executed
        # before the IMPORT_NAME instruction ("import back call").
        # This case is the end of these module instructions
        # and we continue before the IMPORT_NAME.
        if not last_instr and import_instr:  # type: ignore[truthy-bool]
            last_instr = self._continue_before_import(efb_state, import_instr)
            return LastInstrState(
                efb_state.file,
                last_instr,
                efb_state.co_id,
                efb_state.bb_id,
                efb_state.offset,
                import_start=True,
            )

        return LastInstrState(
            efb_state.file,
            last_instr,
            efb_state.co_id,
            efb_state.bb_id,
            efb_state.offset,
        )

    def get_last_instruction(  # noqa: PLR0917
        self,
        file: str,
        instr: Instr,
        trace_pos: int,
        offset: int,
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
            offset: Offset of instr in the basic block
            co_id: Code object id of instr
            bb_id: Basic block id of instr
            import_instr: This instruction is necessary if the execution of
                ``instr`` is caused directly (i.e. no calls in between) by an
                IMPORT_NAME instruction. The argument is this import instruction.

        Returns:
            The last instruction and the state when it is executed
        """
        # Find the basic block and the exact location of the current instruction
        basic_block, bb_offset = self._get_basic_block(co_id, bb_id)
        instr_index = self.locate_in_basic_block(instr, offset, basic_block, bb_offset)

        # Variables to keep track of what happened
        efb_state = ExecutionFlowBuilderState(bb_id, co_id, file, offset)

        # Special case: if there are not remaining instructions in the trace,
        # finish this basic block
        if trace_pos < 0:
            return self._finish_basic_block(instr_index, basic_block, import_instr, efb_state)

        # Get the current instruction in the disassembly for further information
        unique_instr = self._create_unique_instruction(
            efb_state.file, instr, efb_state.co_id, efb_state.bb_id, efb_state.offset
        )

        # Get the instruction last in the trace
        last_traced_instr = self.trace.executed_instructions[trace_pos]

        # Determine last instruction
        last_instr = self._determine_last_instruction(
            efb_state,
            basic_block,
            instr_index,
            last_traced_instr,
            unique_instr,
        )

        # Handle return instruction
        if last_traced_instr.opcode in op.OP_RETURN:
            last_instr = self._handle_return_instructions(
                efb_state,
                instr,
                last_instr,
                last_traced_instr,
                unique_instr,
            )

        # Handle method invocation
        if not last_instr:  # type: ignore[truthy-bool]
            last_instr = self._handle_method_invocation(efb_state, import_instr, last_traced_instr)

        # Handle generators and exceptions
        if not efb_state.call and not efb_state.returned:
            last_instr = self._handle_generator_and_exceptions(
                efb_state, last_instr, last_traced_instr
            )

        return LastInstrState(
            efb_state.file,
            last_instr,
            efb_state.co_id,
            efb_state.bb_id,
            offset=efb_state.offset,
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
        basic_block,
        instr_index,
        last_traced_instr,
        unique_instr,
    ) -> Instr:
        if instr_index > 0:
            # Instruction has exactly one possible predecessor
            last_instr = basic_block[instr_index - 1]
            efb_state.offset -= 2
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
        instr,
        last_instr,
        last_traced_instr,
        unique_instr,
    ):
        if instr.opcode != op.IMPORT_NAME:
            # Coming back from a method call. If last_instr is a call, then the
            # method was called explicitly.
            # If last_instr is not a call, but is traced and does not match the
            # last instruction in the trace, there must have been an implicit call
            # to a magic method (such as __get__). Since we collect instructions
            # invoking these methods, we can safely switch to the called method.
            if last_instr:
                if (last_instr.opcode in op.OP_CALL) or (
                    last_instr.opcode in op.TRACED_INSTRUCTIONS
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
        last_traced_instr,
    ) -> Instr:
        # There is not last instruction in code object,
        # so there must have been a call.
        efb_state.call = True
        if not import_instr:
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
        last_instr,
        last_traced_instr: ExecutedInstruction,
    ) -> Instr:
        if last_instr.opcode in {op.YIELD_VALUE, op.YIELD_FROM}:
            # Generators produce an unusual execution flow: the interpreter handles
            # jumps to the respective yield statement internally and we can not see
            # this in the trace. So we assume that this unusual case (explained in
            # the next branch) is not an exception but the return from a generator.
            last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)

        elif (
            last_instr
            and last_instr.opcode in op.TRACED_INSTRUCTIONS
            and last_instr.opcode != last_traced_instr.opcode
        ):
            # The last instruction that is determined is not in the trace,
            # despite the fact that it should be. There is only one known remaining
            # reasons for this: during an exception. Tracing continues with the last
            # traced instruction (and probably misses some in between).
            last_instr = self._continue_at_last_traced(last_traced_instr, efb_state)
            efb_state.exception = True
        return last_instr

    def _create_unique_instruction(
        self, module: str, instr: Instr, code_object_id: int, node_id: int, offset: int
    ) -> UniqueInstruction:
        code_meta = self.known_code_objects.get(code_object_id)
        assert code_meta, "Unknown code object id"
        return UniqueInstruction(
            file=module,
            name=instr.name,
            code_object_id=code_object_id,
            node_id=node_id,
            code_meta=code_meta,
            offset=offset,
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
        last_instr = self._locate_traced_in_bytecode(last_traced_instr)
        efb_state.offset = last_traced_instr.offset

        return last_instr

    def _continue_at_last_basic_block(self, efb_state: ExecutionFlowBuilderState) -> Instr:
        last_instr = None

        if efb_state.bb_id > 0:
            efb_state.bb_id -= 1
            last_instr = self._get_last_in_basic_block(efb_state.co_id, efb_state.bb_id)
            efb_state.offset -= 2

        return last_instr  # type: ignore[return-value]

    def _continue_before_import(
        self, efb_state: ExecutionFlowBuilderState, import_instr: UniqueInstruction
    ) -> Instr:
        efb_state.co_id = import_instr.code_object_id
        efb_state.bb_id = import_instr.node_id
        efb_state.offset = import_instr.offset
        instr = Instr(import_instr.name, arg=import_instr.arg, lineno=import_instr.lineno)

        # Find the basic block and the exact location of the current instruction
        basic_block, bb_offset = self._get_basic_block(efb_state.co_id, efb_state.bb_id)
        instr_index = self.locate_in_basic_block(instr, efb_state.offset, basic_block, bb_offset)

        if instr_index > 0:
            # Instruction has exactly one possible predecessor
            last_instr = basic_block[instr_index - 1]
            efb_state.offset -= 2
        else:
            last_instr = self._continue_at_last_basic_block(efb_state)

        return last_instr

    def _get_last_in_basic_block(self, code_object_id: int, basic_block_id: int) -> Instr:
        code_object = self.known_code_objects.get(code_object_id)
        assert code_object, "Unknown code object id"
        # Locate basic block in CFG to which instruction belongs
        instr = None
        for node in code_object.original_cfg.nodes:
            if node.index == basic_block_id and node.basic_block:
                instr = node.basic_block[-1]
                break
        assert instr, "Block did not contain a last instruction"
        return instr  # type: ignore[return-value]

    def _get_basic_block(self, code_object_id: int, basic_block_id: int) -> tuple[list[Instr], int]:
        """Locates the basic block in CFG to which the current state belongs.

        The current state is defined by the last instruction.

        Args:
            code_object_id: the code object to look inside of
            basic_block_id: the basic block to find inside the code object

        Returns:
            Tuple of the current basic block and the offset of the first
            instruction in the basic block

        Raises:
            InstructionNotFoundException: when the basic block is not found
                in the given code object
        """
        code_object = self.known_code_objects[code_object_id]
        assert code_object is not None, "Unknown code object id"
        for node in code_object.original_cfg.nodes:
            if node.index == basic_block_id and node.basic_block:
                return node.basic_block, node.offset  # type: ignore[return-value]

        raise InstructionNotFoundException

    def _locate_traced_in_bytecode(self, instr: ExecutedInstruction) -> Instr:
        basic_block, bb_offset = self._get_basic_block(instr.code_object_id, instr.node_id)

        for instruction in basic_block:
            if (
                instr.opcode == instruction.opcode
                and instr.lineno == instruction.lineno
                and instr.offset == bb_offset
            ):
                return instruction
            bb_offset += 2

        raise InstructionNotFoundException

    @staticmethod
    def locate_in_basic_block(
        instr: Instr, instr_offset: int, basic_block: list[Instr], bb_offset: int
    ) -> int:
        """Searches for the location, i.e., the index of the instruction in basic block.

        Args:
            instr: Instruction to be searched for
            instr_offset: Offset of instr
            basic_block: Basic block where instr is located
            bb_offset: Offset of the first instruction in basic_block

        Returns:
            Index of instr in basic_block

        Raises:
            InstructionNotFoundException: when the given instruction is
                not in the given basic block
        """
        for index, instruction in enumerate(basic_block):
            if instruction == instr and instr_offset == bb_offset:
                return index
            bb_offset += 2

        raise InstructionNotFoundException
