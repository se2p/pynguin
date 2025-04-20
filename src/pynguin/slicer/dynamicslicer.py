#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
"""Provides classes and logic for dynamic slicing."""

from __future__ import annotations

import logging
import operator
import time

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.utils.opcodes as op

from pynguin.slicer.executedinstruction import ExecutedAttributeInstruction
from pynguin.slicer.executedinstruction import ExecutedMemoryInstruction
from pynguin.slicer.executionflowbuilder import ExecutionFlowBuilder
from pynguin.slicer.executionflowbuilder import UniqueInstruction
from pynguin.slicer.stack.stackeffect import StackEffect
from pynguin.slicer.stack.stacksimulation import TraceStack
from pynguin.utils.exceptions import InstructionNotFoundException
from pynguin.utils.exceptions import SlicingTimeoutException


if TYPE_CHECKING:
    from bytecode import Instr

    from pynguin.analyses.controlflow import CFG
    from pynguin.analyses.controlflow import ControlDependenceGraph
    from pynguin.analyses.controlflow import ProgramGraphNode
    from pynguin.instrumentation.instrumentation import CodeObjectMetaData
    from pynguin.instrumentation.tracer import ExecutedAssertion
    from pynguin.instrumentation.tracer import ExecutionTrace
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.slicer.executedinstruction import ExecutedInstruction
    from pynguin.slicer.executionflowbuilder import LastInstrState


@dataclass
class SlicingCriterion:
    """The slicing criterion, consists of instruction and position in the trace."""

    unique_instr: UniqueInstruction
    trace_position: int


@dataclass
class SlicingContext:
    """Stores the slicing context.

    The context consists of all defined and used variables, as well as instructions used
    at one point during slicing.
    """

    # Instructions included in the slice
    instr_in_slice: list[UniqueInstruction] = field(default_factory=list)

    # Instructions for which to compute control dependencies
    instr_ctrl_deps: set[UniqueInstruction] = field(default_factory=set)

    # Variable uses for which a definition is needed
    var_uses_local: set[tuple[int | str | None, int]] = field(default_factory=set)
    var_uses_global: set[tuple[int | str | None, str]] = field(default_factory=set)

    var_uses_nonlocal: set[tuple] = field(default_factory=set)
    var_uses_addresses: set[str] = field(default_factory=set)

    # Attribute uses for which a definition is needed
    attr_uses: set[str] = field(default_factory=set)

    # Variable uses, which normally are attribute uses
    # (used when encompassing object is created)
    attribute_variables: set[str] = field(default_factory=set)


@dataclass
class SlicingState:
    """Holds the configuration and state of the dynamic slicing process.

    The state is tracked for each analysed instruction.
    """

    basic_block_id: int
    code_object_id: int
    context: SlicingContext
    curr_instr: Instr
    execution_flow_builder: ExecutionFlowBuilder
    file: str
    new_attribute_object_uses: set[str]
    offset: int
    pops: int
    pushes: int
    timeout: float
    trace_position: int
    trace_stack: TraceStack
    code_object_dependent: bool = False
    import_back_call: UniqueInstruction | None = None
    stack_simulation: bool = True  # must be disabled for exceptions

    def update_state(self) -> LastInstrState:
        """Updates the slicing state for the next instruction.

        Returns:
            The new last instruction as LastInst
        """
        last_state = self.execution_flow_builder.get_last_instruction(
            self.file,
            self.curr_instr,
            self.trace_position,
            self.offset,
            self.code_object_id,
            self.basic_block_id,
            self.import_back_call,
        )
        self.file = last_state.file
        self.offset = last_state.offset
        self.code_object_id = last_state.code_object_id
        self.basic_block_id = last_state.basic_block_id
        return last_state


class DynamicSlicer:
    """Class that holds the slicing logic and calls."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        known_code_objects: dict[int, CodeObjectMetaData],
    ):
        """Initializes the dynamic slicer.

        Args:
            known_code_objects: A dictionary of code object data
        """
        self._known_code_objects = known_code_objects

    def slice(  # noqa: C901
        self,
        trace: ExecutionTrace,
        slicing_criterion: SlicingCriterion,
    ) -> list[UniqueInstruction]:
        """Main routine to perform the dynamic slicing.

        Args:
            trace: Execution trace object containing slicing information
                with collected instructions.
            slicing_criterion: Slicing criterion object where slicing is started

        Returns:
            A `DynamicSlice` object containing the included instructions.

        Raises:
            SlicingTimeoutException: when the slicing takes longer than the
                configured budget
        """
        slc = self._setup_slicing_configuration(slicing_criterion, trace)

        while True:
            criterion_in_slice = imp_data_dep = False
            include_use = True

            # Get last instruction
            last_state = slc.update_state()

            if last_state.exception:
                # Stack can not be reliably simulated when an exception occurred
                slc.stack_simulation = False
            if not last_state.last_instr:
                # Reached end of executed instructions -> return slice (and keep order)
                instructions = set()
                slice_instructions = []
                for i in reversed(slc.context.instr_in_slice):
                    if i not in instructions:
                        instructions.add(i)
                        slice_instructions.append(i)
                return slice_instructions

            last_unique_instr = self.create_unique_instruction(
                slc.file,
                last_state.last_instr,
                slc.code_object_id,
                slc.basic_block_id,
                slc.offset,
            )
            # Adjust trace position
            last_traced_instr = None
            if last_state.last_instr.opcode in op.TRACED_INSTRUCTIONS:
                last_traced_instr = trace.executed_instructions[slc.trace_position]
                slc.trace_position -= 1

            # Stack housekeeping
            prev_import_back_call = self._stack_housekeeping(last_state, last_unique_instr, slc)

            # Control dependency
            control_dependency = self.check_control_dependency(
                slc.context, last_unique_instr, slc.code_object_id
            )

            # Data dependencies
            # Explicit data dependency
            (
                exp_data_dep,
                slc.new_attribute_object_uses,
            ) = self.check_explicit_data_dependency(
                slc.context, last_unique_instr, last_traced_instr
            )

            # Dependency via method call
            if last_state.call and slc.code_object_dependent:
                imp_data_dep = True
                slc.code_object_dependent = False

                if last_state.import_start:
                    # We need to include the import statement after determining
                    # if one of the instructions executed by the import is included
                    # (because IMPORT_NAME is traced afterwards).
                    slc.context.instr_in_slice.append(prev_import_back_call)
                    num_import_pops = StackEffect.stack_effect(
                        prev_import_back_call.opcode, arg=None, jump=False
                    )[0]
                    slc.trace_stack.update_pop_operations(
                        num_import_pops, prev_import_back_call, in_slice=True
                    )
            # Implicit data dependency (over stack)
            if slc.stack_simulation:
                stack_dep, include_use = slc.trace_stack.update_push_operations(
                    slc.pushes, returned=last_state.returned
                )
                if stack_dep:
                    imp_data_dep = True
            if last_state.returned:
                slc.code_object_dependent = False

            if control_dependency or exp_data_dep or imp_data_dep:
                criterion_in_slice = True

                if not last_state.call:
                    slc.code_object_dependent = True

            # Unconditional jumps
            if last_state.jump and last_state.last_instr.is_uncond_jump():
                criterion_in_slice = True

            # Housekeeping for execution trace, stack
            self._trace_housekeeping(
                criterion_in_slice,
                include_use,
                last_traced_instr,
                last_unique_instr,
                slc,
            )

            # next iteration
            slc.curr_instr = last_state.last_instr

            if time.time() > slc.timeout:
                raise SlicingTimeoutException

    def _stack_housekeeping(self, last_state, last_unique_instr, slc):
        prev_import_back_call = slc.trace_stack.get_import_frame()
        slc.trace_stack.set_attribute_uses(slc.context.attribute_variables)
        if last_state.returned:
            # New frame
            self._add_new_frame(last_state, slc)
        if last_state.call or last_state.import_start:
            # Frame finished
            self._finish_frame(slc)
        slc.context.attribute_variables = slc.trace_stack.get_attribute_uses()
        slc.import_back_call = slc.trace_stack.get_import_frame()
        self._update_stack_effects(last_state, last_unique_instr, slc)
        return prev_import_back_call

    def _trace_housekeeping(
        self, criterion_in_slice, include_use, last_traced_instr, last_unique_instr, slc
    ):
        # Add instruction to slice
        if criterion_in_slice:
            slc.context.instr_in_slice.append(last_unique_instr)
        # Add uses (for S_D)
        if criterion_in_slice and last_unique_instr.is_use() and include_use:
            self.add_uses(slc.context, last_traced_instr)
        # Add control dependencies (for S_C)
        if criterion_in_slice:
            self.add_control_dependencies(slc.context, last_unique_instr, slc.code_object_id)
        # Add current instruction to the stack
        if slc.stack_simulation:
            slc.trace_stack.update_pop_operations(
                slc.pops, last_unique_instr, in_slice=criterion_in_slice
            )

    @staticmethod
    def _update_stack_effects(last_state, last_unique_instr, slc):
        try:
            slc.pops, slc.pushes = StackEffect.stack_effect(
                last_unique_instr.opcode,
                last_unique_instr.dis_arg,
                jump=last_state.jump,
            )
        except ValueError:
            # Stack simulation in not possible with this opcode
            slc.stack_simulation = False

    @staticmethod
    def _finish_frame(slc):
        slc.trace_stack.pop_stack()
        # After leaving the frame where the exception occurred,
        # simulation can be continued
        if not slc.stack_simulation:
            slc.trace_stack.push_artificial_stack()
            slc.stack_simulation = True

    @staticmethod
    def _add_new_frame(last_state, slc):
        slc.trace_stack.push_stack(slc.code_object_id)
        slc.trace_stack.set_attribute_uses(slc.new_attribute_object_uses)
        slc.new_attribute_object_uses.clear()
        slc.trace_stack.set_import_frame(last_state.import_back_call)

    def _setup_slicing_configuration(
        self,
        slicing_criterion: SlicingCriterion,
        trace: ExecutionTrace,
    ):
        new_attribute_object_uses: set[str] = set()
        # Build slicing criterion
        last_ex_instruction = slicing_criterion.unique_instr
        code_object_id = last_ex_instruction.code_object_id
        basic_block_id = last_ex_instruction.node_id
        curr_instr = self._locate_unique_in_bytecode(
            last_ex_instruction, code_object_id, basic_block_id
        )
        execution_flow_builder = ExecutionFlowBuilder(trace, self._known_code_objects)
        pops, pushes, trace_stack = self._init_stack(
            last_ex_instruction,
        )
        context = self._init_context(code_object_id, last_ex_instruction)
        timeout = time.time() + config.configuration.stopping.maximum_slicing_time
        return SlicingState(
            basic_block_id,
            code_object_id,
            context,
            curr_instr,
            execution_flow_builder,
            last_ex_instruction.file,
            new_attribute_object_uses,
            last_ex_instruction.offset,
            pops,
            pushes,
            timeout,
            slicing_criterion.trace_position,
            trace_stack,
        )

    @staticmethod
    def _init_stack(last_ex_instruction) -> tuple[int, int, TraceStack]:
        trace_stack = TraceStack()
        pops, pushes = StackEffect.stack_effect(
            last_ex_instruction.opcode,
            last_ex_instruction.dis_arg,
        )
        trace_stack.update_push_operations(pushes, returned=False)
        trace_stack.update_pop_operations(
            pops, last_ex_instruction, in_slice=True
        )  # The slicing criterion is in the slice
        return pops, pushes, trace_stack

    def _init_context(self, code_object_id, last_ex_instruction) -> SlicingContext:
        context = SlicingContext()
        context.instr_in_slice.append(last_ex_instruction)
        self.add_control_dependencies(context, last_ex_instruction, code_object_id)
        return context

    def _locate_unique_in_bytecode(
        self, instr: UniqueInstruction, code_object_id: int, basic_block_id: int
    ) -> Instr:
        # Get relevant basic block
        basic_block = None
        bb_offset = -1
        code_object = self._known_code_objects.get(code_object_id)
        assert code_object, "Unknown code object id"
        for node in code_object.original_cfg.nodes:
            if node.index == basic_block_id:
                basic_block = node.basic_block
                bb_offset = node.offset

        if (not basic_block) or (bb_offset < 0):
            raise InstructionNotFoundException

        for instruction in basic_block:
            if (
                instr.opcode == instruction.opcode  # type: ignore[union-attr]
                and instr.lineno == instruction.lineno  # type: ignore[union-attr]
                and instr.offset == bb_offset
            ):
                return instruction  # type: ignore[return-value]
            bb_offset += 2

        raise InstructionNotFoundException

    def create_unique_instruction(
        self, file: str, instr: Instr, code_object_id: int, node_id: int, offset: int
    ) -> UniqueInstruction:
        """Creates and returns a unique instruction object from an instruction.

        Args:
            file: the file name which contains the instruction
            instr: the bytecode instruction
            code_object_id: the code object producing the instruction
            node_id: the node inside the code object containing the instruction
            offset: the offset of the instruction

        Returns:
            The created UniqueInstruction object
        """
        code_meta = self._known_code_objects[code_object_id]
        return UniqueInstruction(
            file=file,
            name=instr.name,
            code_object_id=code_object_id,
            node_id=node_id,
            code_meta=code_meta,
            offset=offset,
            arg=instr.arg,
            lineno=instr.lineno,
        )

    def check_control_dependency(
        self,
        context: SlicingContext,
        unique_instr: UniqueInstruction,
        code_object_id: int,
    ) -> bool:
        """Check if the given instruction has a control dependency from the context.

        Args:
            context: the slicing context
            unique_instr: the instruction to check for
            code_object_id: the id of the code object containing the instruction

        Returns:
            True if the instruction is part of the slice due to a control dependency,
            False otherwise
        """
        control_dependency = False

        if not unique_instr.is_cond_branch():
            return False

        code_object: CodeObjectMetaData = self._known_code_objects[code_object_id]
        cdg: ControlDependenceGraph = code_object.cdg
        curr_node = self.get_node(unique_instr.node_id, cdg)
        assert curr_node, "Invalid node id"
        successors = cdg.get_successors(curr_node)

        instr_ctrl_deps_copy = context.instr_ctrl_deps.copy()

        # Check if any instruction on S_C is control dependent on current instruction
        # If so: include current instruction in the slice, remove all instructions
        # control dependent on current instruction
        for instr in context.instr_ctrl_deps:
            instr_node = self.get_node(instr.node_id, cdg)
            if instr_node in successors:
                instr_ctrl_deps_copy.remove(instr)
                control_dependency = True
        context.instr_ctrl_deps = instr_ctrl_deps_copy

        return control_dependency

    def add_control_dependencies(
        self,
        context: SlicingContext,
        unique_instr: UniqueInstruction,
        code_object_id: int,
    ) -> None:
        """Add control dependencies to the slicing context.

        Args:
            context: The context that will receive the control dependencies
            unique_instr: The instruction to check for control dependencies
            code_object_id: the id of the code object containing the instruction
        """
        code_object: CodeObjectMetaData = self._known_code_objects[code_object_id]
        cdg: ControlDependenceGraph = code_object.cdg
        curr_node = self.get_node(unique_instr.node_id, cdg)
        assert curr_node, "Invalid node id"
        predecessors = cdg.get_predecessors(curr_node)

        for predecessor in predecessors:
            if not predecessor.is_artificial:
                context.instr_ctrl_deps.add(unique_instr)

    @staticmethod
    def get_node(node_id: int, graph: ControlDependenceGraph | CFG) -> ProgramGraphNode | None:
        """Iterate through all nodes of the graph and return the node with the given id.

        Args:
            node_id: the node id to find inside the given graph
            graph: the graph to find the node inside of

        Returns:
            A ProgramGraphNode object with the given id
            or None if the id is not in the nodes
        """
        for node in graph.nodes:
            if node.index == node_id:
                return node
        return None

    def check_explicit_data_dependency(  # noqa: C901
        self,
        context: SlicingContext,
        unique_instr: UniqueInstruction,
        traced_instr: ExecutedInstruction | None,
    ) -> tuple[bool, set[str]]:
        """Analyses the explicit data dependencies from one instruction to another.

        Args:
            context: The slicing context used in the analyses
            unique_instr: the instruction checked if it has explicit data dependency
            traced_instr: the instruction the data dependency can be to

        Returns:
            A tuple with either False and an empty set or True and a set containing all
            explicit attribute creation uses.
        """
        complete_cover = False
        partial_cover = False
        attribute_creation_uses = set()

        if not unique_instr.is_def():
            return False, set()

        # Check variable definitions
        if isinstance(traced_instr, ExecutedMemoryInstruction):
            complete_cover = self._check_variables(context, traced_instr)

            # When an object, of which certain used attributes are taken from,
            # is created, the slicer has to look for the definition of normal variables
            # instead of these attributes, since they are defined as variables and not
            # as attributes on class/module level.
            if traced_instr.arg_address and traced_instr.object_creation:
                attribute_uses = set()
                for use in context.attr_uses:
                    if use.startswith(hex(traced_instr.arg_address)) and len(use) > len(
                        hex(traced_instr.arg_address)
                    ):
                        complete_cover = True
                        attribute_uses.add(use)
                        attribute_creation_uses.add("_".join(use.split("_")[1:]))
                for use in attribute_uses:
                    context.attr_uses.remove(use)

            # Check for address dependencies
            if traced_instr.is_mutable_type and traced_instr.object_creation:
                # Note that the definition of an object here means the
                # creation of the object.
                address_dependency = self._check_scope_for_def(
                    context.var_uses_addresses,
                    hex(traced_instr.arg_address),
                    None,
                    None,
                )
                if address_dependency:
                    complete_cover = True

            # Check for the attributes which were converted to variables
            # (explained in the previous construct)
            if traced_instr.argument in context.attribute_variables:
                complete_cover = True
                context.attribute_variables.remove(str(traced_instr.argument))

        if isinstance(traced_instr, ExecutedAttributeInstruction):
            # check attribute defs
            if traced_instr.combined_attr in context.attr_uses:
                complete_cover = True
                context.attr_uses.remove(traced_instr.combined_attr)
            # Partial cover: modification of attribute of
            # object in search for definition
            if hex(traced_instr.src_address) in context.var_uses_addresses:
                partial_cover = True

        return (complete_cover or partial_cover), attribute_creation_uses

    def _check_variables(self, context, traced_instr):
        complete_cover = False

        # Check local variables
        if traced_instr.opcode in {op.STORE_FAST, op.DELETE_FAST}:
            complete_cover = self._check_scope_for_def(
                context.var_uses_local,
                traced_instr.argument,
                traced_instr.code_object_id,
                operator.eq,
            )

        # Check global variables (with *_NAME instructions)
        elif traced_instr.opcode in {op.STORE_NAME, op.DELETE_NAME}:
            if (
                traced_instr.code_object_id in self._known_code_objects
                and self._known_code_objects[traced_instr.code_object_id] is not None
                and self._known_code_objects[traced_instr.code_object_id].code_object.co_name
                == "<module>"
            ):
                complete_cover = self._check_scope_for_def(
                    context.var_uses_global,
                    traced_instr.argument,
                    traced_instr.file,
                    operator.eq,
                )
            else:
                complete_cover = self._check_scope_for_def(
                    context.var_uses_local,
                    traced_instr.argument,
                    traced_instr.code_object_id,
                    operator.eq,
                )

        # Check global variables
        elif traced_instr.opcode in {op.STORE_GLOBAL, op.DELETE_GLOBAL}:
            complete_cover = self._check_scope_for_def(
                context.var_uses_global,
                traced_instr.argument,
                traced_instr.file,
                operator.eq,
            )

        # Check nonlocal variables
        elif traced_instr.opcode in {op.STORE_DEREF, op.DELETE_DEREF}:
            complete_cover = self._check_scope_for_def(
                context.var_uses_nonlocal,
                traced_instr.argument,
                traced_instr.code_object_id,
                operator.contains,
            )

        # Check IMPORT_NAME instructions
        # IMPORT_NAME gets a special treatment: it has an incorrect stack effect,
        # but it is compensated by treating it as a definition
        elif traced_instr.opcode == op.IMPORT_NAME:
            if (
                traced_instr.arg_address
                and hex(traced_instr.arg_address) in context.var_uses_addresses
                and traced_instr.object_creation
            ):
                complete_cover = True
                context.var_uses_addresses.remove(hex(traced_instr.arg_address))

        else:
            # There should be no other possible instructions
            raise ValueError("Instruction opcode can not be analyzed for definitions.")

        return complete_cover

    @staticmethod
    def _check_scope_for_def(
        context_scope: set,
        argument: str,
        scope_id: int | str | tuple | None,
        comp_op,
    ) -> bool:
        complete_cover = False
        remove_tuples = set()

        for tup in context_scope:
            if isinstance(tup, tuple):
                if argument == tup[0] and comp_op(tup[1], scope_id):
                    complete_cover = True
                    remove_tuples.add(tup)
            elif argument == tup:
                complete_cover = True
                remove_tuples.add(tup)
        for tup in remove_tuples:
            context_scope.remove(tup)

        return complete_cover

    def add_uses(self, context: SlicingContext, traced_instr: ExecutedInstruction) -> None:
        """Add all uses found in the executed instruction into the slicing context.

        Args:
            context: The slicing context that gets extended
            traced_instr: The instruction to analyse
        """
        if isinstance(traced_instr, ExecutedMemoryInstruction):
            self._add_variable_uses(context, traced_instr)

        # Add attribute uses
        if isinstance(traced_instr, ExecutedAttributeInstruction):
            self._add_attribute_uses(context, traced_instr)

    def _add_variable_uses(self, context, traced_instr):
        if traced_instr.arg_address and traced_instr.is_mutable_type:
            context.var_uses_addresses.add(hex(traced_instr.arg_address))
        # Add local variables
        if traced_instr.opcode == op.LOAD_FAST:
            context.var_uses_local.add((
                traced_instr.argument,
                traced_instr.code_object_id,
            ))
        # Add global variables (with *_NAME instructions)
        elif traced_instr.opcode == op.LOAD_NAME:
            if (
                traced_instr.code_object_id in self._known_code_objects
                and self._known_code_objects[traced_instr.code_object_id] is not None
                and self._known_code_objects[traced_instr.code_object_id].code_object.co_name
                == "<module>"
            ):
                context.var_uses_global.add((traced_instr.argument, traced_instr.file))
            else:
                context.var_uses_local.add((
                    traced_instr.argument,
                    traced_instr.code_object_id,
                ))
        # Add global variables
        elif traced_instr.opcode == op.LOAD_GLOBAL:
            context.var_uses_global.add((traced_instr.argument, traced_instr.file))
        # Add nonlocal variables
        elif traced_instr.opcode in {
            op.LOAD_CLOSURE,
            op.LOAD_DEREF,
            op.LOAD_CLASSDEREF,
        }:
            variable_scope = set()
            current_code_object_id = traced_instr.code_object_id
            while True:
                current_code_meta = self._known_code_objects[current_code_object_id]
                variable_scope.add(current_code_object_id)
                if traced_instr.argument in current_code_meta.code_object.co_cellvars:
                    break

                assert current_code_meta.parent_code_object_id is not None
                current_code_object_id = current_code_meta.parent_code_object_id
            context.var_uses_nonlocal.add((
                traced_instr.argument,
                tuple(variable_scope),
            ))
        else:
            # There should be no other possible instructions
            raise ValueError("Instruction opcode can not be analyzed for definitions.")

    @staticmethod
    def _add_attribute_uses(context, traced_instr):
        # Memory address of loaded attribute
        if traced_instr.arg_address and traced_instr.is_mutable_type:
            context.var_uses_addresses.add(hex(traced_instr.arg_address))
        # Attribute name in combination with source
        if traced_instr.arg_address:
            context.attr_uses.add(traced_instr.combined_attr)
        # Special case for access to composite types and imports:
        # We want the complete definition of composite types and
        # the imported module, respectively
        if not traced_instr.arg_address or traced_instr.opcode == op.IMPORT_FROM:
            context.var_uses_addresses.add(hex(traced_instr.src_address))

    @staticmethod
    def get_line_id_by_instruction(
        instruction: UniqueInstruction, subject_properties: SubjectProperties
    ) -> int:
        """Get the line id of the line an instruction belongs to.

        Args:
            instruction: the instruction the line id is needed for
            subject_properties: the known data about the module under test

        Returns:
            the line id used by the line of an instruction

        Raises:
            ValueError: If the line of the instruction is not part of the known data.
        """
        for line_id, line_meta in subject_properties.existing_lines.items():
            if (
                line_meta.file_name == instruction.file
                and line_meta.line_number == instruction.lineno
            ):
                return line_id
        raise ValueError("The instruction's line is not registered in the known data")

    @staticmethod
    def map_instructions_to_lines(
        instructions: list[UniqueInstruction], subject_properties: SubjectProperties
    ) -> set[int]:
        """Map the list of instructions in a slice to a set of lines of the SUT.

        Instructions of the test case statements are ignored.

        Args:
            instructions: list of unique instructions
            subject_properties: the known data about the module under test

        Returns:
            a set of line ids used in the given list of instructions
        """
        line_ids = set()
        curr_line = -1
        for instruction in instructions:
            if instruction.file == "<ast>":  # do not include test statements
                continue
            if instruction.lineno == curr_line:  # only add new lines
                continue
            curr_line = instruction.lineno  # type: ignore[assignment]
            line_ids.add(DynamicSlicer.get_line_id_by_instruction(instruction, subject_properties))
        return line_ids


class AssertionSlicer:
    """Holds all logic of slicing traced assertions.

    Generates the dynamic slice produced by a test.
    """

    def __init__(
        self,
        known_code_objects: dict[int, CodeObjectMetaData],
    ):
        """Initializes the slicer.

        Args:
            known_code_objects: The dictionary of code object data
        """
        self._known_code_objects = known_code_objects

    def _slicing_criterion_from_assertion(
        self, assertion: ExecutedAssertion, trace: ExecutionTrace
    ) -> SlicingCriterion:
        traced_instr = trace.executed_instructions[assertion.trace_position]
        code_meta = self._known_code_objects[traced_instr.code_object_id]

        # find out the basic block of the assertion
        basic_block = None
        for node in code_meta.original_cfg.nodes:
            if node.index == traced_instr.node_id and node.basic_block:
                basic_block = node.basic_block
        assert basic_block, "node id or code object id were off"

        # the traced instruction is always the jump at the end of the bb
        original_instr = None
        for instr in reversed(list(basic_block)):
            if instr.opcode == traced_instr.opcode:  # type: ignore[union-attr]
                original_instr = instr
                break
        assert original_instr

        unique_instr = UniqueInstruction(
            file=traced_instr.file,
            name=traced_instr.name,
            code_object_id=traced_instr.code_object_id,
            node_id=traced_instr.node_id,
            code_meta=code_meta,
            offset=traced_instr.offset,
            arg=original_instr.arg,  # type: ignore[union-attr]
            lineno=traced_instr.lineno,
        )

        return SlicingCriterion(unique_instr, assertion.trace_position - 1)

    def slice_assertion(
        self, assertion: ExecutedAssertion, trace: ExecutionTrace
    ) -> list[UniqueInstruction]:
        """Calculate the dynamic slice for an assertion inside a test case.

        Args:
            assertion: The assertion, for which to calculate the slice.
            trace: the execution trace

        Returns:
            The list of executed instructions contained in the slice of the assertion.
        """
        slicing_criterion = self._slicing_criterion_from_assertion(assertion, trace)
        slicer = DynamicSlicer(self._known_code_objects)
        return slicer.slice(trace, slicing_criterion)
