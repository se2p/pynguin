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
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

import pynguin.configuration as config
from pynguin.instrumentation import AST_FILENAME
from pynguin.instrumentation.controlflow import BasicBlockNode
from pynguin.instrumentation.version import (
    CLOSURE_LOAD_NAMES,
    IMPORT_FROM_NAMES,
    IMPORT_NAME_NAMES,
    LOAD_DEREF_NAMES,
    LOAD_FAST_NAMES,
    LOAD_GLOBAL_NAMES,
    LOAD_NAME_NAMES,
    MODIFY_DEREF_NAMES,
    MODIFY_FAST_NAMES,
    MODIFY_GLOBAL_NAMES,
    MODIFY_NAME_NAMES,
)
from pynguin.slicer.executedinstruction import (
    ExecutedAttributeInstruction,
    ExecutedMemoryInstruction,
)
from pynguin.slicer.executionflowbuilder import ExecutionFlowBuilder, UniqueInstruction
from pynguin.slicer.stack.stacksimulation import TraceStack
from pynguin.utils.exceptions import SlicingTimeoutException

if TYPE_CHECKING:
    from bytecode.instr import _UNSET

    from pynguin.instrumentation.tracer import (
        CodeObjectMetaData,
        ExecutedAssertion,
        ExecutionTrace,
        SubjectProperties,
    )
    from pynguin.slicer.executedinstruction import ExecutedInstruction
    from pynguin.slicer.executionflowbuilder import InstrState


@dataclass(frozen=True)
class SlicingCriterion:
    """The slicing criterion consists of the position of an instruction in an execution trace."""

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
    local_var_uses: set[tuple[int | str | None, int]] = field(default_factory=set)
    global_var_uses: set[tuple[int | str | None, str]] = field(default_factory=set)

    nonlocal_var_uses: set[tuple[int | str | None, tuple[int, ...]]] = field(default_factory=set)
    var_address_uses: set[str] = field(default_factory=set)

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

    context: SlicingContext
    execution_flow_builder: ExecutionFlowBuilder
    new_attribute_object_uses: set[str]
    state: InstrState
    pops: int
    pushes: int
    timeout: float
    trace_stack: TraceStack
    code_object_dependent: bool = False
    import_back_call: UniqueInstruction | None = None
    stack_simulation: bool = True  # must be disabled for exceptions


T = TypeVar(
    "T",
    bound=tuple[int | str | None, tuple[int, ...]]
    | tuple[int | str | None, int]
    | tuple[int | str | None, str]
    | str,
)


class DynamicSlicer:
    """Class that holds the slicing logic and calls.

    The process of dynamic slicing consists on finding all the variables and instructions
    that contributed to reaching an instruction based on an execution trace. This is achieved
    by traversing the execution trace backwards starting from a slicing criterion, which is an
    instruction used in the execution trace.

    Several mechanisms are used to retrieve information:
        - Control dependencies: We keep the conditional instructions that are in the trace.
        - Explicit data dependencies: We keep the instructions that used variables
            that allowed the slicing criterion to be reached.
        - Implicit data dependencies: We keep the instructions that used values
            passed via the stack or via the return and yield instructions.
        - Unconditional jumps: We keep the instructions that are unconditional jumps.

    The stack used in dynamic slicing is a bit special. Since we are traversing
    the execution trace backwards, we push instructions onto it when we encounter an instruction
    that pops values, and we pop instructions when we encounter an instruction that pushes values.
    This allows us to find dependencies between the different instructions that use the Python stack
    to operate. For example, if we look at a “BINARY_ADD” instruction, we know that it will pop
    its two arguments from the Python stack and then push its result into it. In our case,
    it will rather pop the instruction that uses the result when executed normally from our stack
    and push itself into it twice to indicate that it uses two arguments when executed normally.
    """

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

    def slice(  # noqa: C901, PLR0915
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

        self._logger.debug("========================= [START] =========================")
        self._logger.debug("\t %s", slc.state.instr)
        self._logger.debug("-----------------------------------------------------------")

        self._log_iteration_results(slc)

        while True:
            # Get previous instruction state
            state = slc.execution_flow_builder.get_previous_instruction_state(
                slc.state,
                slc.import_back_call,
            )

            if state is None:
                # Reached end of executed instructions
                break

            slc.state = state
            context = slc.context
            instr = state.instr

            criterion_in_slice = False
            imp_data_dep = False
            include_use = True

            if instr.is_traced:
                self._logger.debug(
                    "========================= [POSITION %s] =========================",
                    state.trace_position,
                )
            else:
                self._logger.debug(
                    "========================= [NOT TRACED] ========================="
                )

            self._logger.debug("     %s", instr)
            self._logger.debug("----------------------------------------------------------------")

            # Stack can not be reliably simulated when an exception occurred
            if state.exception:
                self._logger.debug("EXCEPTION: An exception occurred, disabling stack simulation.")
                slc.stack_simulation = False

            # Stack housekeeping
            previous_frame_import_back_call = self._stack_housekeeping(slc)

            # Control dependency
            control_dependency = self.check_control_dependency(context, instr)

            if control_dependency:
                self._logger.debug("CRITERION IN SLICE (CONTROL DEPENDENCY): %s", instr)
                criterion_in_slice = True

            # Explicit data dependency
            exp_data_dep, slc.new_attribute_object_uses = self.check_explicit_data_dependency(
                context,
                state.traced_instr,
                instr,
            )

            if exp_data_dep:
                self._logger.debug("CRITERION IN SLICE (EXPLICIT DATA DEPENDENCY): %s", instr)
                criterion_in_slice = True

            # Implicit data dependency
            if state.call and slc.code_object_dependent:
                # via method call
                imp_data_dep = True
                slc.code_object_dependent = False

                if previous_frame_import_back_call is not None and state.import_start:
                    # We need to include the import statement after determining
                    # if one of the instructions executed by the import is included
                    # (because IMPORT_NAME is traced afterwards).
                    num_import_pops, _ = previous_frame_import_back_call.stack_effects(jump=False)
                    slc.trace_stack.update_pop_operations(
                        num_import_pops, previous_frame_import_back_call, in_slice=True
                    )
                    self._logger.debug("IN SLICE: %s", previous_frame_import_back_call)
                    slc.context.instr_in_slice.append(previous_frame_import_back_call)

            if slc.stack_simulation:
                # over stack
                stack_dep, include_use = slc.trace_stack.update_push_operations(
                    slc.pushes, returned=state.returned
                )
                if stack_dep:
                    self._logger.debug("IMPLICIT DATA DEPENDENCY (STACK): %s", instr)
                    imp_data_dep = True

            slc.code_object_dependent = not state.returned or (
                not state.call and criterion_in_slice
            )

            if imp_data_dep:
                self._logger.debug("CRITERION IN SLICE (IMPLICIT DATA DEPENDENCY): %s", instr)
                criterion_in_slice = True

            # Unconditional jumps
            if state.jump and instr.is_uncond_jump():
                self._logger.debug("CRITERION IN SLICE (UNCONDITIONAL JUMP): %s", instr)
                criterion_in_slice = True

            # Housekeeping for execution trace, stack
            self._trace_housekeeping(criterion_in_slice, include_use, slc)

            # Log current iteration
            self._log_iteration_results(slc)

            if time.time() > slc.timeout:
                raise SlicingTimeoutException

        # Return slice (and keep order)
        instructions = set()
        slice_instructions = []
        for i in reversed(slc.context.instr_in_slice):
            if i not in instructions:
                instructions.add(i)
                slice_instructions.append(i)

        self._logger.debug("Found %d instructions in the slice.", len(slice_instructions))
        self._logger.debug("========================= [END] =========================")

        return slice_instructions

    def _setup_slicing_configuration(
        self,
        slicing_criterion: SlicingCriterion,
        trace: ExecutionTrace,
    ):
        execution_flow_builder = ExecutionFlowBuilder(trace, self._known_code_objects)
        state = execution_flow_builder.create_instruction_state(slicing_criterion.trace_position)
        new_attribute_object_uses: set[str] = set()
        timeout = time.time() + config.configuration.stopping.maximum_slicing_time

        trace_stack = TraceStack()
        pops, pushes = state.instr.stack_effects()
        trace_stack.update_push_operations(pushes, returned=False)
        trace_stack.update_pop_operations(pops, state.instr, in_slice=True)

        context = SlicingContext()
        context.instr_in_slice.append(state.instr)
        self._logger.debug("IN SLICE: %s", state.instr)
        self.add_control_dependency(context, state.instr)

        return SlicingState(
            context,
            execution_flow_builder,
            new_attribute_object_uses,
            state,
            pops,
            pushes,
            timeout,
            trace_stack,
        )

    def _log_iteration_results(self, slc: SlicingState):
        if not self._logger.isEnabledFor(logging.DEBUG):
            return

        self._logger.debug("> INSTRUCTIONS IN SLICE NUMBER: %d", len(slc.context.instr_in_slice))
        if slc.context.instr_ctrl_deps:
            self._logger.debug(
                "> INSTRUCTIONS CONTROL DEPENDENCIES NUMBER: %d",
                len(slc.context.instr_ctrl_deps),
            )
        if slc.context.local_var_uses:
            self._logger.debug(
                "> VARIABLE LOCAL USES: %s",
                {var for var, _ in slc.context.local_var_uses},
            )
        if slc.context.global_var_uses:
            self._logger.debug(
                "> VARIABLE GLOBAL USES: %s",
                {var for var, _ in slc.context.global_var_uses},
            )
        if slc.context.nonlocal_var_uses:
            self._logger.debug(
                "> VARIABLE NONLOCAL USES: %s",
                {var for var, _ in slc.context.nonlocal_var_uses},
            )
        if slc.context.var_address_uses:
            self._logger.debug(
                "> VARIABLE ADDRESS USES: %s",
                slc.context.var_address_uses,
            )
        if slc.context.attr_uses:
            self._logger.debug(
                "> ATTRIBUTE USES: %s",
                slc.context.attr_uses,
            )
        if slc.context.attribute_variables:
            self._logger.debug(
                "> ATTRIBUTE VARIABLES: %s",
                slc.context.attribute_variables,
            )
        self._logger.debug(
            "> LAST FRAME BLOCK INSTRUCTIONS NUMBER: %d (%d frames)",
            len(slc.trace_stack.last_frame_stack.last_block),
            len(slc.trace_stack.frame_stacks),
        )

    def _stack_housekeeping(self, slc: SlicingState) -> UniqueInstruction | None:
        previous_frame_import_back_call = slc.trace_stack.last_frame_stack.import_name_instr

        slc.trace_stack.last_frame_stack.attribute_uses = slc.context.attribute_variables.copy()

        if slc.state.returned:
            # New frame
            slc.trace_stack.push_stack(slc.state.instr.code_object_id)
            slc.trace_stack.last_frame_stack.attribute_uses = slc.new_attribute_object_uses.copy()
            slc.trace_stack.last_frame_stack.import_name_instr = slc.state.import_back_call
            slc.new_attribute_object_uses.clear()
            self._logger.debug("NEW FRAME: %s", len(slc.trace_stack.frame_stacks))

        if slc.state.call or slc.state.import_start:
            # Frame finished
            self._logger.debug("FRAME FINISHED: %s", len(slc.trace_stack.frame_stacks))
            slc.trace_stack.pop_stack()
            # After leaving the frame where the exception occurred,
            # simulation can be continued
            if not slc.stack_simulation:
                slc.trace_stack.push_artificial_stack()
                slc.stack_simulation = True

        slc.context.attribute_variables = slc.trace_stack.last_frame_stack.attribute_uses
        slc.import_back_call = slc.trace_stack.last_frame_stack.import_name_instr
        slc.pops, slc.pushes = slc.state.instr.stack_effects(jump=slc.state.jump)

        return previous_frame_import_back_call

    def _trace_housekeeping(
        self,
        criterion_in_slice: bool,  # noqa: FBT001
        include_use: bool,  # noqa: FBT001
        slc: SlicingState,
    ):
        state = slc.state

        # Add current instruction to the stack
        if slc.stack_simulation:
            slc.trace_stack.update_pop_operations(
                slc.pops, state.instr, in_slice=criterion_in_slice
            )

        if not criterion_in_slice:
            return

        # Add instruction to slice
        self._logger.debug("IN SLICE: %s", state.instr)
        slc.context.instr_in_slice.append(state.instr)

        # Add control dependencies (for S_C)
        self.add_control_dependency(slc.context, state.instr)

        # Add uses (for S_D)
        if state.instr.is_use and include_use:
            self.add_uses(slc.context, state.traced_instr)

    def check_control_dependency(self, context: SlicingContext, instr: UniqueInstruction) -> bool:
        """Check if any instruction on S_C is control dependent on the current instruction.

        Args:
            context: the slicing context
            instr: the current instruction to check

        Returns:
            True if the current instruction is part of the slice due to a control dependency,
            False otherwise
        """
        if not instr.is_cond_branch:
            return False

        code_object = self._known_code_objects[instr.code_object_id]
        cdg = code_object.cdg
        node = cdg.get_basic_block_node(instr.node_id)

        # The descendants of the current node in the control-dependence graph (CDG) are the
        # dominated nodes which are control dependent on the current instruction. We also
        # handle the special case of jumps used to create loops, as they should only be
        # dominated by the loops to which they are connected, and this is not necessarily
        # reflected in the CDG.
        dominated_nodes = cdg.get_descendants(node)
        dominator_loops = cdg.get_dominator_loops(node)
        dominated_instr_ctrl_deps = {
            instr
            for instr in context.instr_ctrl_deps
            if (
                dominated_node := self._known_code_objects[
                    instr.code_object_id
                ].cdg.get_basic_block_node(instr.node_id)
            )
            in dominated_nodes
            and (
                not instr.has_jump()
                or code_object.cfg.get_successors(dominated_node).isdisjoint(dominator_loops)
            )
        }
        context.instr_ctrl_deps = context.instr_ctrl_deps.difference(dominated_instr_ctrl_deps)
        control_dependency = bool(dominated_instr_ctrl_deps)

        if control_dependency:
            self._logger.debug(
                "CONTROL DEPENDENCIES (DOMINATOR): Remove %d dominated instructions",
                len(dominated_instr_ctrl_deps),
            )

        return control_dependency

    def add_control_dependency(
        self,
        context: SlicingContext,
        instr: UniqueInstruction,
    ) -> None:
        """Add the current instruction to the control-dependence graph if required.

        Args:
            context: the slicing context
            instr: the instruction to add
        """
        code_object = self._known_code_objects[instr.code_object_id]
        cdg = code_object.cdg
        node = cdg.get_basic_block_node(instr.node_id)

        # The ancestors of the current node in the control-dependence graph (CDG) are the
        # dominator nodes on which the current instruction is control dependent. We also
        # handle the special case where there is a loop in the CDG.
        dominator_nodes = cdg.get_ancestors(node)
        dominated_nodes = cdg.get_descendants(node)
        if any(
            isinstance(dominator_node, BasicBlockNode)
            for dominator_node in dominator_nodes
            if dominator_node not in dominated_nodes
        ):
            self._logger.debug("CONTROL DEPENDENCIES (DOMINATED): %s", instr)
            context.instr_ctrl_deps.add(instr)

    @staticmethod
    def _extract_arguments(
        traced_instr: ExecutedMemoryInstruction,
    ) -> tuple[tuple[str, int, bool, bool], ...]:
        match traced_instr:
            case ExecutedMemoryInstruction(
                argument=str(argument),
                arg_address=int(arg_address),
                is_mutable_type=bool(is_mutable_type),
                object_creation=bool(object_creation),
            ):
                return ((argument, arg_address, is_mutable_type, object_creation),)
            case ExecutedMemoryInstruction(
                argument=(str(argument0), str(argument1)),
                arg_address=(int(arg_address0), int(arg_address1)),
                is_mutable_type=(bool(is_mutable_type0), bool(is_mutable_type1)),
                object_creation=(bool(object_creation0), bool(object_creation1)),
            ):
                return (
                    (argument0, arg_address0, is_mutable_type0, object_creation0),
                    (argument1, arg_address1, is_mutable_type1, object_creation1),
                )
            case _:
                raise AssertionError(f"Invalid traced instruction: {traced_instr}")

    def check_explicit_data_dependency(  # noqa: C901
        self,
        context: SlicingContext,
        traced_instr: ExecutedInstruction | None,
        instr: UniqueInstruction,
    ) -> tuple[bool, set[str]]:
        """Analyses the explicit data dependencies from one instruction to another.

        Args:
            context: The slicing context
            traced_instr: The executed instruction that is used to check for dependencies
            instr: The instruction to check for explicit data dependencies

        Returns:
            A tuple with either False and an empty set or True and a set containing all
            explicit attribute creation uses.
        """
        if not instr.is_def:
            return False, set()

        complete_cover = False
        partial_cover = False
        attribute_creation_uses = set()

        # Check variable definitions
        if isinstance(traced_instr, ExecutedMemoryInstruction):
            complete_cover = False

            for argument, arg_address, is_mutable_type, object_creation in self._extract_arguments(
                traced_instr
            ):
                complete_cover = complete_cover or self._check_variables(
                    context,
                    instr.file,
                    instr.code_object_id,
                    instr.name,
                    argument,
                    arg_address,
                    object_creation,
                )

                if complete_cover:
                    self._logger.debug("EXPLICIT DATA DEPENDENCY (VARIABLE): '%s'", argument)

                # When an object, of which certain used attributes are taken from,
                # is created, the slicer has to look for the definition of normal variables
                # instead of these attributes, since they are defined as variables and not
                # as attributes on class/module level.
                if arg_address and object_creation:
                    attribute_uses = set()
                    for use in context.attr_uses:
                        if use.startswith(hex(arg_address)) and len(use) > len(hex(arg_address)):
                            attribute_name = "_".join(use.split("_")[1:])
                            self._logger.debug(
                                "EXPLICIT DATA DEPENDENCY (ATTRIBUTE): '%s'",
                                attribute_name,
                            )
                            complete_cover = True
                            attribute_uses.add(use)
                            attribute_creation_uses.add(attribute_name)
                    for use in attribute_uses:
                        context.attr_uses.remove(use)

                # Check for address dependencies
                if is_mutable_type and object_creation:
                    # Note that the definition of an object here means the
                    # creation of the object.
                    address_dependency = self._check_scope_for_def(
                        context.var_address_uses,
                        hex(arg_address),
                        None,
                        None,
                    )
                    if address_dependency:
                        self._logger.debug(
                            "EXPLICIT DATA DEPENDENCY (VARIABLE ADDRESS): '%s'",
                            hex(arg_address),
                        )
                        complete_cover = True

                # Check for the attributes which were converted to variables
                # (explained in the previous construct)
                if argument in context.attribute_variables:
                    complete_cover = True
                    context.attribute_variables.remove(str(argument))

        if isinstance(traced_instr, ExecutedAttributeInstruction):
            # check attribute defs
            if traced_instr.combined_attr in context.attr_uses:
                self._logger.debug(
                    "EXPLICIT DATA DEPENDENCY (COMBINED ATTRIBUTE): '%s'",
                    traced_instr.combined_attr,
                )
                complete_cover = True
                context.attr_uses.remove(traced_instr.combined_attr)
            # Partial cover: modification of attribute of
            # object in search for definition
            if hex(traced_instr.src_address) in context.var_address_uses:
                self._logger.debug(
                    "EXPLICIT DATA DEPENDENCY (PARTIAL VARIABLE ADDRESS): '%s'",
                    hex(traced_instr.src_address),
                )
                partial_cover = True

        return (complete_cover or partial_cover), attribute_creation_uses

    def _check_variables(  # noqa: PLR0917
        self,
        context: SlicingContext,
        file: str,
        code_object_id: int,
        name: str,
        argument: str,
        arg_address: int,
        object_creation: bool,  # noqa: FBT001
    ) -> bool:
        complete_cover = False

        # Check local variables
        if name in MODIFY_FAST_NAMES:
            complete_cover = self._check_scope_for_def(
                context.local_var_uses, argument, code_object_id, operator.eq
            )

        # Check global variables (with *_NAME instructions)
        elif name in MODIFY_NAME_NAMES:
            if (
                code_object_id in self._known_code_objects
                and self._known_code_objects[code_object_id] is not None
                and self._known_code_objects[code_object_id].code_object.co_name == "<module>"
            ):
                complete_cover = self._check_scope_for_def(
                    context.global_var_uses, argument, file, operator.eq
                )
            else:
                complete_cover = self._check_scope_for_def(
                    context.local_var_uses, argument, code_object_id, operator.eq
                )

        # Check global variables
        elif name in MODIFY_GLOBAL_NAMES:
            complete_cover = self._check_scope_for_def(
                context.global_var_uses, argument, file, operator.eq
            )

        # Check nonlocal variables
        elif name in MODIFY_DEREF_NAMES:
            complete_cover = self._check_scope_for_def(
                context.nonlocal_var_uses, argument, code_object_id, operator.contains
            )

        # Check IMPORT_NAME instructions
        # IMPORT_NAME gets a special treatment: it has an incorrect stack effect,
        # but it is compensated by treating it as a definition
        elif name in IMPORT_NAME_NAMES:
            if arg_address and hex(arg_address) in context.var_address_uses and object_creation:
                complete_cover = True
                context.var_address_uses.remove(hex(arg_address))

        else:
            # There should be no other possible instructions
            raise ValueError("Instruction opcode can not be analyzed for definitions.")

        return complete_cover

    @staticmethod
    def _check_scope_for_def(
        context_scope: set[T],
        argument: int | str | None,
        scope_id: int | str | tuple | None,
        comp_op,
    ) -> bool:
        complete_cover = False
        remove_tuples: set[T] = set()

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

    def add_uses(self, context: SlicingContext, traced_instr: ExecutedInstruction | None) -> None:
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

    def _add_variable_uses(
        self,
        context: SlicingContext,
        traced_instr: ExecutedMemoryInstruction,
    ) -> None:
        for argument, arg_address, is_mutable_type, _ in self._extract_arguments(traced_instr):
            if arg_address and is_mutable_type:
                self._logger.debug("VARIABLE ADDRESS USE: '%s' address", hex(arg_address))
                context.var_address_uses.add(hex(arg_address))
            # Add local variables
            if traced_instr.name in LOAD_FAST_NAMES:
                self._logger.debug("FAST VARIABLE USE: '%s'", argument)
                context.local_var_uses.add((
                    argument,
                    traced_instr.code_object_id,
                ))
            # Add global variables (with *_NAME instructions)
            elif traced_instr.name in LOAD_NAME_NAMES:
                self._logger.debug("NAME VARIABLE USE: '%s'", argument)
                if (
                    traced_instr.code_object_id in self._known_code_objects
                    and self._known_code_objects[traced_instr.code_object_id] is not None
                    and self._known_code_objects[traced_instr.code_object_id].code_object.co_name
                    == "<module>"
                ):
                    context.global_var_uses.add((argument, traced_instr.file))
                else:
                    context.local_var_uses.add((
                        argument,
                        traced_instr.code_object_id,
                    ))
            # Add global variables
            elif traced_instr.name in LOAD_GLOBAL_NAMES:
                self._logger.debug("GLOBAL VARIABLE USE: '%s'", argument)
                context.global_var_uses.add((argument, traced_instr.file))
            # Add nonlocal variables
            elif traced_instr.name in LOAD_DEREF_NAMES + CLOSURE_LOAD_NAMES:
                variable_scope: set[int] = set()
                current_code_object_id = traced_instr.code_object_id
                while True:
                    current_code_meta = self._known_code_objects[current_code_object_id]
                    variable_scope.add(current_code_object_id)
                    if argument in current_code_meta.code_object.co_cellvars:
                        break

                    assert current_code_meta.parent_code_object_id is not None
                    current_code_object_id = current_code_meta.parent_code_object_id
                self._logger.debug("DEREF VARIABLE USE: '%s'", argument)
                context.nonlocal_var_uses.add((
                    argument,
                    tuple(variable_scope),
                ))
            else:
                # There should be no other possible instructions
                raise AssertionError(
                    f"Instruction {traced_instr} can not be analyzed for definitions."
                )

    def _add_attribute_uses(
        self,
        context: SlicingContext,
        traced_instr: ExecutedAttributeInstruction,
    ) -> None:
        # Memory address of loaded attribute
        if traced_instr.arg_address and traced_instr.is_mutable_type:
            self._logger.debug("VARIABLE ADDRESS USE: '%s' address", hex(traced_instr.arg_address))
            context.var_address_uses.add(hex(traced_instr.arg_address))
        # Attribute name in combination with source
        if traced_instr.arg_address:
            self._logger.debug("COMBINED ATTRIBUTE USE: '%s'", traced_instr.combined_attr)
            context.attr_uses.add(traced_instr.combined_attr)
        # Special case for access to composite types and imports:
        # We want the complete definition of composite types and
        # the imported module, respectively
        if not traced_instr.arg_address or traced_instr.name in IMPORT_FROM_NAMES:
            self._logger.debug(
                "PARTIAL VARIABLE ADDRESS USE: '%s' address", hex(traced_instr.src_address)
            )
            context.var_address_uses.add(hex(traced_instr.src_address))

    @staticmethod
    def get_line_id_by_instruction(
        instruction: UniqueInstruction,
        subject_properties: SubjectProperties,
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
        instructions: list[UniqueInstruction],
        subject_properties: SubjectProperties,
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
        curr_line: int | _UNSET | None = None
        for instruction in instructions:
            if instruction.file == AST_FILENAME:  # do not include test statements
                continue
            if instruction.lineno == curr_line:  # only add new lines
                continue
            curr_line = instruction.lineno
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
        slicer = DynamicSlicer(self._known_code_objects)
        return slicer.slice(trace, SlicingCriterion(assertion.trace_position))
