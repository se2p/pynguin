#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
"""Provides classes and logic for dynamic slicing."""

import logging
import operator
import time
from dataclasses import dataclass, field
from typing import Union

from bytecode import Instr

import pynguin.configuration as config
import pynguin.utils.opcodes as op
from pynguin.analyses.controlflow import CFG, ControlDependenceGraph, ProgramGraphNode
from pynguin.instrumentation.instrumentation import is_traced_instruction
from pynguin.slicer.executionflowbuilder import ExecutionFlowBuilder, LastInstrState
from pynguin.slicer.instruction import UniqueInstruction
from pynguin.slicer.stack.stackeffect import StackEffect
from pynguin.slicer.stack.stacksimulation import TraceStack
from pynguin.testcase.execution import (
    CodeObjectMetaData,
    ExecutedAttributeInstruction,
    ExecutedInstruction,
    ExecutedMemoryInstruction,
    ExecutionTrace,
)
from pynguin.utils.exceptions import (
    InstructionNotFoundException,
    SlicingTimeoutException,
)


@dataclass
class DynamicSlice:
    """The slice containing the list of instructions in the slice and its origin."""

    origin_name: str

    sliced_instructions: list[UniqueInstruction]


@dataclass
class SlicingCriterion:
    """Slicing criterion data class holding the instruction
    and variables to slice for."""

    unique_instr: UniqueInstruction

    occurrence: int = 1

    local_variables: set | None = None

    global_variables: set | None = None


@dataclass
class SlicingContext:
    """Data class storing all defined and used variables as well as instructions
    used at one point during the slicing."""

    # Instructions included in the slice
    instr_in_slice: list[UniqueInstruction] = field(default_factory=list)

    # Instructions for which to compute control dependencies
    instr_ctrl_deps: set[UniqueInstruction] = field(default_factory=set)

    # Variable uses for which a definition is needed
    var_uses_local: set[tuple[int, int]] = field(default_factory=set)
    var_uses_global: set[tuple[int, str]] = field(default_factory=set)
    var_uses_nonlocal: set[tuple] = field(default_factory=set)
    var_uses_addresses: set[str] = field(default_factory=set)

    # Attribute uses for which a definition is needed
    attr_uses: set[str] = field(default_factory=set)

    # Variable uses, which normally are attribute uses
    # (used when encompassing object is created)
    attribute_variables: set[str] = field(default_factory=set)


@dataclass
class SlicingState:
    """Holds the configuration and state of the dynamic slicing process
    for each analysed instruction."""

    basic_block_id: int
    code_object_dependent: bool
    code_object_id: int
    context: SlicingContext
    curr_instr: Instr
    execution_flow_builder: ExecutionFlowBuilder
    file: str
    import_back_call: UniqueInstruction | None
    new_attribute_object_uses: set[str]
    offset: int
    pops: int
    pushes: int
    stack_simulation: bool
    timeout: float
    trace_position: int
    trace_stack: TraceStack

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
        trace: ExecutionTrace,
        known_code_objects: dict[int, CodeObjectMetaData],
    ):
        self._known_code_objects = known_code_objects
        self._trace = trace

    @property
    def known_code_objects(self):
        """Provide known code objects.

        Returns:
            The known code objects of the execution
        """
        return self._known_code_objects

    @property
    def trace(self):
        """Get the trace with the current information.

        Returns:
            The current execution trace
        """
        return self._trace

    def slice(
        self,
        trace: ExecutionTrace,
        slicing_criterion: SlicingCriterion,
        trace_position: int,
    ) -> DynamicSlice:
        """Main routine to perform the dynamic slicing.

        Args:
            trace: Execution trace object containing slicing information
                with collected instructions.
            slicing_criterion: Slicing criterion object where slicing is started
                (must have correct `occurrence` attribute if
                `trace_position` is not given).
            trace_position: Optional parameter. The position in the trace where
                slicing is started. Can be given directly (as in the case of internal
                traced assertions). In case it is not given it has to be determined
                based on the occurrence of the instruction of the slicing criterion
                in the trace.

        Returns:
            A `DynamicSlice` object containing the included instructions.
        """
        slc = self._setup_slicing_configuration(
            slicing_criterion, trace, trace_position
        )

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
                return DynamicSlice(trace.test_id, slice_instructions)

            last_unique_instr = self.create_unique_instruction(
                slc.file,
                last_state.last_instr,
                slc.code_object_id,
                slc.basic_block_id,
                slc.offset,
            )
            # Adjust trace position
            last_traced_instr = None
            if is_traced_instruction(last_state.last_instr):
                last_traced_instr = trace.executed_instructions[slc.trace_position]
                slc.trace_position -= 1

            # Stack housekeeping
            prev_import_back_call = self._stack_housekeeping(
                last_state, last_unique_instr, slc
            )

            # Control dependency
            control_dependency = self.check_control_dependency(
                slc.context, last_unique_instr, slc.code_object_id
            )

            assert last_traced_instr, "Working on set of untracked instructions"
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
                        num_import_pops, prev_import_back_call, True
                    )
            # Implicit data dependency (over stack)
            if slc.stack_simulation:
                stack_dep, include_use = slc.trace_stack.update_push_operations(
                    slc.pushes, last_state.returned
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

            self._debug_output(
                slc.context,
                control_dependency,
                slc.curr_instr,
                exp_data_dep,
                imp_data_dep,
                criterion_in_slice,
            )

            if time.time() > slc.timeout:
                raise SlicingTimeoutException

    def _stack_housekeeping(self, last_state, last_unique_instr, slc):
        prev_import_back_call = slc.trace_stack.get_import_frame()
        # TODO(SiL) must prev_import_back_call be not none?
        # assert prev_import_back_call, "Import frame was None"
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
            self.add_control_dependencies(
                slc.context, last_unique_instr, slc.code_object_id
            )
        # Add current instruction to the stack
        if slc.stack_simulation:
            slc.trace_stack.update_pop_operations(
                slc.pops, last_unique_instr, criterion_in_slice
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
        trace_position: int,
    ):
        # The slicing criterion is in the slice
        criterion_in_slice = True
        # Stack simulation is enabled initially (must be disabled for exceptions)
        stack_simulation = True
        code_object_dependent = False
        new_attribute_object_uses: set[str] = set()
        import_back_call = None
        # Build slicing criterion
        last_ex_instruction = slicing_criterion.unique_instr
        file = last_ex_instruction.file
        code_object_id = last_ex_instruction.code_object_id
        basic_block_id = last_ex_instruction.node_id
        offset = last_ex_instruction.offset
        curr_instr = self._locate_unique_in_bytecode(
            last_ex_instruction, code_object_id, basic_block_id
        )
        execution_flow_builder = ExecutionFlowBuilder(trace, self._known_code_objects)
        pops, pushes, trace_stack = self._init_stack(
            criterion_in_slice, last_ex_instruction
        )
        context = self._init_context(
            code_object_id, last_ex_instruction, slicing_criterion
        )
        timeout = time.time() + config.configuration.stopping.maximum_slicing_time
        return SlicingState(
            basic_block_id,
            code_object_dependent,
            code_object_id,
            context,
            curr_instr,
            execution_flow_builder,
            file,
            import_back_call,
            new_attribute_object_uses,
            offset,
            pops,
            pushes,
            stack_simulation,
            timeout,
            trace_position,
            trace_stack,
        )

    @staticmethod
    def _init_stack(in_slice, last_ex_instruction) -> tuple[int, int, TraceStack]:
        trace_stack = TraceStack()
        pops, pushes = StackEffect.stack_effect(
            last_ex_instruction.opcode, last_ex_instruction.dis_arg, False
        )
        trace_stack.update_push_operations(pushes, False)
        trace_stack.update_pop_operations(pops, last_ex_instruction, in_slice)
        return pops, pushes, trace_stack

    def _init_context(
        self, code_object_id, last_ex_instruction, slicing_criterion
    ) -> SlicingContext:
        context = SlicingContext()
        context.instr_in_slice.append(last_ex_instruction)
        if slicing_criterion.global_variables:
            for tup in slicing_criterion.global_variables:
                context.var_uses_global.add(tup)
        self.add_control_dependencies(context, last_ex_instruction, code_object_id)
        return context

    def _debug_output(
        self,
        context,
        control_dependency,
        curr_instr,
        exp_data_dep,
        imp_data_dep,
        in_slice,
    ):
        self._logger.debug(curr_instr)
        self._logger.debug("\tIn slice: %s", in_slice)
        if in_slice:
            self._logger.debug("\t(Reason: ")
            if exp_data_dep:
                self._logger.debug("explicit data dependency, ")
            if imp_data_dep:
                self._logger.debug("implicit data dependency, ")
            if control_dependency:
                self._logger.debug("control dependency")
            self._logger.debug(")")
        self._logger.debug("\n")
        self._logger.debug("\tlocal_variables: %s", context.var_uses_local)
        self._logger.debug("\tglobal_variables: %s", context.var_uses_global)
        self._logger.debug("\tcell_free_variables: %s", context.var_uses_nonlocal)
        self._logger.debug("\taddresses: %s", context.var_uses_addresses)
        self._logger.debug("\tattributes: %s", context.attr_uses)
        self._logger.debug("\tattribute_variables: %s", context.attribute_variables)
        self._logger.debug("\tS_C: %s", context.instr_ctrl_deps)
        self._logger.debug("\n")

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
                instr.opcode == instruction.opcode
                and instr.lineno == instruction.lineno
                and instr.offset == bb_offset
            ):
                return instruction
            bb_offset += 2

        raise InstructionNotFoundException

    def create_unique_instruction(
        self, file: str, instr: Instr, code_object_id: int, node_id: int, offset: int
    ) -> UniqueInstruction:
        """Creates and returns a unique instruction object from an instruction,
        the code object id, the node id and the offset of the instruction.
        """
        code_meta = self._known_code_objects[code_object_id]
        return UniqueInstruction(
            file,
            instr.name,
            code_object_id,
            node_id,
            code_meta,
            offset,
            instr.arg,
            instr.lineno,
        )

    def check_control_dependency(
        self,
        context: SlicingContext,
        unique_instr: UniqueInstruction,
        code_object_id: int,
    ) -> bool:
        """Check if the given unique instruction has a control dependency from the
        slicing context.

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
        predecessors = cdg.get_predecessors(curr_node)

        for predecessor in predecessors:
            if not predecessor.is_artificial:
                context.instr_ctrl_deps.add(unique_instr)

    @staticmethod
    def organize_by_code_object(
        instructions: list[UniqueInstruction],
    ) -> dict[int, list[UniqueInstruction]]:
        """Sort a list of instructions into a dictionary, where each instruction is
        stored in a list accessible through the if of the code object containing the
        instruction.

        Args:
            instructions: The instructions to sort as list

        Returns:
            A dictionary where each id of a code object contains a list of
            instructions of the code object belonging to the id.
        """
        code_object_instructions: dict[int, list[UniqueInstruction]] = {}

        for instruction in instructions:
            if instruction.code_object_id not in code_object_instructions:
                code_object_instructions[instruction.code_object_id] = []
            code_object_instructions[instruction.code_object_id].append(instruction)

        return code_object_instructions

    @staticmethod
    def organize_by_module(
        dynamic_slice: DynamicSlice,
    ) -> dict[str, list[UniqueInstruction]]:
        """Sort all instructions of a dynamic slice by their module name.

        Args:
            dynamic_slice: The dynamic slice

        Returns:
            A dictionary where each module name contains a list of instructions of the
            slice that belong to the module with that name.
        """
        module_instructions: dict[str, list[UniqueInstruction]] = {}

        for instruction in dynamic_slice.sliced_instructions:
            if instruction.file not in module_instructions:
                module_instructions[instruction.file] = []
            module_instructions[instruction.file].append(instruction)

        return module_instructions

    @staticmethod
    def get_node(
        node_id: int, graph: Union[ControlDependenceGraph, CFG]
    ) -> ProgramGraphNode:
        """Iterate through all nodes of the graph and return the node
        with the given id."""
        ret_node = None
        for node in graph.nodes:
            if node.index == node_id:
                ret_node = node
                break
        assert ret_node, "Invalid node id"
        return ret_node

    def check_explicit_data_dependency(
        self,
        context: SlicingContext,
        unique_instr: UniqueInstruction,
        traced_instr: ExecutedInstruction | None,
    ) -> tuple[bool, set[str]]:
        """Analyses the explicit data dependencies from one instruction to another
        instruction.

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
        if traced_instr.opcode in [op.STORE_FAST, op.DELETE_FAST]:
            complete_cover = self._check_scope_for_def(
                context.var_uses_local,
                traced_instr.argument,
                traced_instr.code_object_id,
                operator.eq,
            )

        # Check global variables (with *_NAME instructions)
        elif traced_instr.opcode in [op.STORE_NAME, op.DELETE_NAME]:
            if (
                traced_instr.code_object_id in self._known_code_objects
                and self._known_code_objects[traced_instr.code_object_id]
                and self._known_code_objects[
                    traced_instr.code_object_id
                ].code_object.co_name
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
        elif traced_instr.opcode in [op.STORE_GLOBAL, op.DELETE_GLOBAL]:
            complete_cover = self._check_scope_for_def(
                context.var_uses_global,
                traced_instr.argument,
                traced_instr.file,
                operator.eq,
            )

        # Check nonlocal variables
        elif traced_instr.opcode in [op.STORE_DEREF, op.DELETE_DEREF]:
            complete_cover = self._check_scope_for_def(
                context.var_uses_nonlocal,
                traced_instr.argument,
                traced_instr.code_object_id,
                operator.contains,
            )

        # Check IMPORT_NAME instructions
        # IMPORT_NAME gets a special treatment: it has an incorrect stack effect,
        # but it is compensated by treating it as a definition
        elif traced_instr.opcode in [op.IMPORT_NAME]:
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
        scope_id: Union[int, str, tuple] | None,
        comp_op,
    ) -> bool:
        complete_cover = False
        remove_tuples = set()

        for tup in context_scope:
            if isinstance(tup, tuple):
                if argument == tup[0] and comp_op(tup[1], scope_id):
                    complete_cover = True
                    remove_tuples.add(tup)
            else:
                if argument == tup:
                    complete_cover = True
                    remove_tuples.add(tup)
        for tup in remove_tuples:
            context_scope.remove(tup)

        return complete_cover

    def add_uses(
        self, context: SlicingContext, traced_instr: ExecutedInstruction
    ) -> None:
        """Add all uses found in the executed instruction into the slicing context.

        Args:
            context: The slicing context that gets extended
            traced_instr: The instruction to analyse
        """
        # Add variable uses
        if isinstance(traced_instr, ExecutedMemoryInstruction):
            if traced_instr.arg_address and traced_instr.is_mutable_type:
                context.var_uses_addresses.add(hex(traced_instr.arg_address))

            # Add local variables
            if traced_instr.opcode in [op.LOAD_FAST]:
                context.var_uses_local.add(
                    (traced_instr.argument, traced_instr.code_object_id)
                )
            # Add global variables (with *_NAME instructions)
            elif traced_instr.opcode in [op.LOAD_NAME]:
                if (
                    traced_instr.code_object_id in self._known_code_objects
                    and self._known_code_objects[traced_instr.code_object_id]
                    and self._known_code_objects[
                        traced_instr.code_object_id
                    ].code_object.co_name
                    == "<module>"
                ):
                    context.var_uses_global.add(
                        (traced_instr.argument, traced_instr.file)
                    )
                else:
                    context.var_uses_local.add(
                        (traced_instr.argument, traced_instr.code_object_id)
                    )
            # Add global variables
            elif traced_instr.opcode in [op.LOAD_GLOBAL]:
                context.var_uses_global.add((traced_instr.argument, traced_instr.file))
            # Add nonlocal variables
            elif traced_instr.opcode in [
                op.LOAD_CLOSURE,
                op.LOAD_DEREF,
                op.LOAD_CLASSDEREF,
            ]:
                variable_scope = set()
                current_code_object_id = traced_instr.code_object_id
                while True:
                    current_code_meta = self._known_code_objects[current_code_object_id]
                    variable_scope.add(current_code_object_id)
                    assert (
                        current_code_meta.parent_code_object_id
                    ), "Code object was not a child object"
                    current_code_object_id = current_code_meta.parent_code_object_id

                    if (
                        traced_instr.argument
                        in current_code_meta.code_object.co_cellvars
                    ):
                        break
                context.var_uses_nonlocal.add(
                    (traced_instr.argument, tuple(variable_scope))
                )
            else:
                # There should be no other possible instructions
                raise ValueError(
                    "Instruction opcode can not be analyzed for definitions."
                )

        # Add attribute uses
        if isinstance(traced_instr, ExecutedAttributeInstruction):
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
    def find_trace_position(
        trace: ExecutionTrace, slicing_criterion: SlicingCriterion
    ) -> int:
        """
        Find the position of the slicing criterion in the executed instructions
        of the trace.

        Args:
            trace: Execution trace
            slicing_criterion: slicing criterion to slice for

        Returns:
            the index of the slicing criterion instruction withing the trace
        """
        slice_instr: UniqueInstruction = slicing_criterion.unique_instr
        occurrences = 0
        position = 0
        for ex_instr in trace.executed_instructions:
            if (
                ex_instr.file == slice_instr.file
                and ex_instr.opcode == slice_instr.opcode
                and ex_instr.lineno == ex_instr.lineno
                and ex_instr.offset == slice_instr.offset
            ):
                occurrences += 1

                if occurrences == slicing_criterion.occurrence:
                    return position
            position += 1

        raise ValueError("Slicing criterion could not be found in trace")
