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
from typing import TypeVar

import pynguin.configuration as config

from pynguin.instrumentation import AST_FILENAME
from pynguin.instrumentation.controlflow import BasicBlockNode
from pynguin.instrumentation.version import CLOSURE_LOAD_OPCODES
from pynguin.instrumentation.version import IMPORT_FROM_OPCODES
from pynguin.instrumentation.version import IMPORT_NAME_OPCODES
from pynguin.instrumentation.version import LOAD_DEREF_OPCODES
from pynguin.instrumentation.version import LOAD_FAST_OPCODES
from pynguin.instrumentation.version import LOAD_GLOBAL_OPCODES
from pynguin.instrumentation.version import LOAD_NAME_OPCODES
from pynguin.instrumentation.version import MODIFY_DEREF_OPCODES
from pynguin.instrumentation.version import MODIFY_FAST_OPCODES
from pynguin.instrumentation.version import MODIFY_GLOBAL_OPCODES
from pynguin.instrumentation.version import MODIFY_NAME_OPCODES
from pynguin.instrumentation.version import TRACED_OPCODES
from pynguin.slicer.executedinstruction import ExecutedAttributeInstruction
from pynguin.slicer.executedinstruction import ExecutedMemoryInstruction
from pynguin.slicer.executionflowbuilder import ExecutionFlowBuilder
from pynguin.slicer.executionflowbuilder import UniqueInstruction
from pynguin.slicer.stack.stacksimulation import TraceStack
from pynguin.utils.exceptions import SlicingTimeoutException


if TYPE_CHECKING:
    from bytecode.instr import _UNSET
    from bytecode.instr import Instr

    from pynguin.instrumentation.tracer import CodeObjectMetaData
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

    def __str__(self) -> str:
        return f"SlicingCriterion({self.unique_instr}, position={self.trace_position})"


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

    node_id: int
    code_object_id: int
    context: SlicingContext
    curr_instr: Instr
    execution_flow_builder: ExecutionFlowBuilder
    file: str
    new_attribute_object_uses: set[str]
    instr_original_index: int
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
            self.instr_original_index,
            self.code_object_id,
            self.node_id,
            self.import_back_call,
        )
        self.file = last_state.file
        self.instr_original_index = last_state.instr_original_index
        self.code_object_id = last_state.code_object_id
        self.node_id = last_state.basic_block_id
        return last_state


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
        self._logger.debug("========================= [START] =========================")
        self._logger.debug("\t %s", slicing_criterion.unique_instr)
        self._logger.debug("-----------------------------------------------------------")

        slc = self._setup_slicing_configuration(slicing_criterion, trace)

        self._log_iteration_results(slc)

        while True:
            criterion_in_slice = False
            imp_data_dep = False
            include_use = True

            # Get last instruction
            last_state = slc.update_state()

            if last_state.last_instr is None:
                # Reached end of executed instructions
                break

            last_unique_instr = UniqueInstruction(
                file=slc.file,
                name=last_state.last_instr.name,
                code_object_id=slc.code_object_id,
                node_id=slc.node_id,
                code_meta=self._known_code_objects[slc.code_object_id],
                instr_original_index=slc.instr_original_index,
                arg=last_state.last_instr.arg,
                lineno=last_state.last_instr.lineno,
            )

            # Adjust trace position
            last_traced_instr = None
            if last_state.last_instr.opcode in TRACED_OPCODES:
                last_traced_instr = trace.executed_instructions[slc.trace_position]
                self._logger.debug(
                    "========================= [POSITION %s] =========================",
                    slc.trace_position,
                )
                slc.trace_position -= 1
            else:
                self._logger.debug(
                    "========================= [NOT TRACED] ========================="
                )

            self._logger.debug("     %s", last_unique_instr)
            self._logger.debug("----------------------------------------------------------------")

            # Stack can not be reliably simulated when an exception occurred
            if last_state.exception:
                self._logger.debug("EXCEPTION: An exception occurred, disabling stack simulation.")
                slc.stack_simulation = False

            # Stack housekeeping
            prev_import_back_call = self._stack_housekeeping(last_state, last_unique_instr, slc)

            # Control dependency
            control_dependency = self.check_control_dependency(
                slc.context, last_unique_instr, slc.code_object_id
            )

            if control_dependency:
                self._logger.debug("CRITERION IN SLICE (CONTROL DEPENDENCY): %s", last_unique_instr)
                criterion_in_slice = True

            # Explicit data dependency
            exp_data_dep, slc.new_attribute_object_uses = self.check_explicit_data_dependency(
                slc.context, last_unique_instr, last_traced_instr
            )

            if exp_data_dep:
                self._logger.debug(
                    "CRITERION IN SLICE (EXPLICIT DATA DEPENDENCY): %s", last_unique_instr
                )
                criterion_in_slice = True

            # Implicit data dependency
            if last_state.call and slc.code_object_dependent:
                # via method call
                imp_data_dep = True
                slc.code_object_dependent = False

                if prev_import_back_call is not None and last_state.import_start:
                    # We need to include the import statement after determining
                    # if one of the instructions executed by the import is included
                    # (because IMPORT_NAME is traced afterwards).
                    num_import_pops, _ = prev_import_back_call.stack_effects(jump=False)
                    slc.trace_stack.update_pop_operations(
                        num_import_pops, prev_import_back_call, in_slice=True
                    )
                    self._logger.debug("IN SLICE: %s", prev_import_back_call)
                    slc.context.instr_in_slice.append(prev_import_back_call)

            if slc.stack_simulation:
                # over stack
                stack_dep, include_use = slc.trace_stack.update_push_operations(
                    slc.pushes, returned=last_state.returned
                )
                if stack_dep:
                    self._logger.debug("IMPLICIT DATA DEPENDENCY (STACK): %s", last_unique_instr)
                    imp_data_dep = True

            slc.code_object_dependent = not last_state.returned or (
                not last_state.call and criterion_in_slice
            )

            if imp_data_dep:
                self._logger.debug(
                    "CRITERION IN SLICE (IMPLICIT DATA DEPENDENCY): %s", last_unique_instr
                )
                criterion_in_slice = True

            # Unconditional jumps
            if last_state.jump and last_state.last_instr.is_uncond_jump():
                self._logger.debug("CRITERION IN SLICE (UNCONDITIONAL JUMP): %s", last_unique_instr)
                criterion_in_slice = True

            # Housekeeping for execution trace, stack
            self._trace_housekeeping(
                criterion_in_slice,
                include_use,
                last_traced_instr,
                last_unique_instr,
                slc,
            )

            # Log current iteration
            self._log_iteration_results(slc)

            # Next iteration
            slc.curr_instr = last_state.last_instr

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

    def _stack_housekeeping(
        self,
        last_state: LastInstrState,
        last_unique_instr: UniqueInstruction,
        slc: SlicingState,
    ) -> UniqueInstruction | None:
        prev_import_back_call = slc.trace_stack.last_frame_stack.import_name_instr

        slc.trace_stack.last_frame_stack.attribute_uses = slc.context.attribute_variables.copy()

        if last_state.returned:
            # New frame
            slc.trace_stack.push_stack(slc.code_object_id)
            slc.trace_stack.last_frame_stack.attribute_uses = slc.new_attribute_object_uses.copy()
            slc.trace_stack.last_frame_stack.import_name_instr = last_state.import_back_call
            slc.new_attribute_object_uses.clear()
            self._logger.debug("NEW FRAME: %s", len(slc.trace_stack.frame_stacks))

        if last_state.call or last_state.import_start:
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
        slc.pops, slc.pushes = last_unique_instr.stack_effects(jump=last_state.jump)

        return prev_import_back_call

    def _trace_housekeeping(
        self,
        criterion_in_slice: bool,  # noqa: FBT001
        include_use: bool,  # noqa: FBT001
        last_traced_instr: ExecutedInstruction | None,
        last_unique_instr: UniqueInstruction,
        slc: SlicingState,
    ):
        # Add current instruction to the stack
        if slc.stack_simulation:
            slc.trace_stack.update_pop_operations(
                slc.pops, last_unique_instr, in_slice=criterion_in_slice
            )

        if not criterion_in_slice:
            return

        # Add instruction to slice
        self._logger.debug("IN SLICE: %s", last_unique_instr)
        slc.context.instr_in_slice.append(last_unique_instr)

        # Add control dependencies (for S_C)
        self.add_control_dependency(slc.context, last_unique_instr, slc.code_object_id)

        # Add uses (for S_D)
        if last_unique_instr.is_use() and include_use:
            self.add_uses(slc.context, last_traced_instr)

    def _setup_slicing_configuration(
        self,
        slicing_criterion: SlicingCriterion,
        trace: ExecutionTrace,
    ):
        last_unique_instr = slicing_criterion.unique_instr
        basic_block_id = last_unique_instr.node_id
        code_object_id = last_unique_instr.code_object_id
        execution_flow_builder = ExecutionFlowBuilder(trace, self._known_code_objects)
        new_attribute_object_uses: set[str] = set()
        timeout = time.time() + config.configuration.stopping.maximum_slicing_time

        code_object = self._known_code_objects[code_object_id]
        node = code_object.original_cfg.get_basic_block_node(basic_block_id)
        assert node is not None, (
            f"The instruction of the slicing criterion {slicing_criterion} is not in the CFG."
        )

        _, bytecode_instr = node.find_instruction_by_original_index(
            last_unique_instr.instr_original_index
        )
        assert (
            last_unique_instr.opcode == bytecode_instr.opcode
            or last_unique_instr.lineno == bytecode_instr.lineno
        ), (
            f"Slicing criterion {slicing_criterion} references a wrong bytecode instruction {bytecode_instr}."  # noqa: E501
        )

        trace_stack = TraceStack()
        pops, pushes = last_unique_instr.stack_effects()
        trace_stack.update_push_operations(pushes, returned=False)
        trace_stack.update_pop_operations(pops, last_unique_instr, in_slice=True)

        context = SlicingContext()
        context.instr_in_slice.append(last_unique_instr)
        self._logger.debug("IN SLICE: %s", last_unique_instr)
        self.add_control_dependency(context, last_unique_instr, code_object_id)

        return SlicingState(
            basic_block_id,
            code_object_id,
            context,
            bytecode_instr,
            execution_flow_builder,
            last_unique_instr.file,
            new_attribute_object_uses,
            last_unique_instr.instr_original_index,
            pops,
            pushes,
            timeout,
            slicing_criterion.trace_position,
            trace_stack,
        )

    def check_control_dependency(
        self,
        context: SlicingContext,
        last_unique_instr: UniqueInstruction,
        code_object_id: int,
    ) -> bool:
        """Check if any instruction on S_C is control dependent on the last unique instruction.

        Args:
            context: the slicing context
            last_unique_instr: the last instruction to check for
            code_object_id: the id of the code object containing the last instruction

        Returns:
            True if the last instruction is part of the slice due to a control dependency,
            False otherwise
        """
        if not last_unique_instr.is_cond_branch():
            return False

        code_object = self._known_code_objects[code_object_id]
        cdg = code_object.cdg
        last_node = cdg.get_basic_block_node(last_unique_instr.node_id)
        assert last_node is not None, "Invalid node id"

        # The dominated nodes in the control dependency graph (CDG) are the nodes that are
        # control dependent on the last instruction. They are the successors of the last node
        # in the CDG.
        dominated_nodes = cdg.get_successors(last_node)
        dominated_instr_ctrl_deps = {
            instr
            for instr in context.instr_ctrl_deps
            if cdg.get_basic_block_node(instr.node_id) in dominated_nodes
        }
        context.instr_ctrl_deps = context.instr_ctrl_deps.difference(dominated_instr_ctrl_deps)
        control_dependency = bool(dominated_instr_ctrl_deps)

        if control_dependency:
            self._logger.debug(
                "CONTROL DEPENDENCIES (DOMINANT): Remove %d dominated instructions",
                len(dominated_instr_ctrl_deps),
            )

        return control_dependency

    def add_control_dependency(
        self,
        context: SlicingContext,
        last_unique_instr: UniqueInstruction,
        code_object_id: int,
    ) -> None:
        """Add the last unique instruction to the control dependency if it is control dependent.

        Args:
            context: the slicing context
            last_unique_instr: the last instruction to add
            code_object_id: the id of the code object containing the last instruction
        """
        code_object = self._known_code_objects[code_object_id]
        cdg = code_object.cdg
        last_node = cdg.get_basic_block_node(last_unique_instr.node_id)
        assert last_node is not None, "Invalid node id"

        # The dominant nodes in the control dependency graph (CDG) are the nodes on which
        # the last instruction is control dependent. They are the predecessors of the last node
        # in the CDG.
        dominant_nodes = cdg.get_predecessors(last_node)
        if any(isinstance(dominant_node, BasicBlockNode) for dominant_node in dominant_nodes):
            self._logger.debug("CONTROL DEPENDENCIES (DOMINATED): %s", last_unique_instr)
            context.instr_ctrl_deps.add(last_unique_instr)

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

            if complete_cover:
                self._logger.debug(
                    "EXPLICIT DATA DEPENDENCY (VARIABLE): '%s'",
                    traced_instr.argument,
                )

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
            if traced_instr.is_mutable_type and traced_instr.object_creation:
                # Note that the definition of an object here means the
                # creation of the object.
                address_dependency = self._check_scope_for_def(
                    context.var_address_uses,
                    hex(traced_instr.arg_address),
                    None,
                    None,
                )
                if address_dependency:
                    self._logger.debug(
                        "EXPLICIT DATA DEPENDENCY (VARIABLE ADDRESS): '%s'",
                        hex(traced_instr.arg_address),
                    )
                    complete_cover = True

            # Check for the attributes which were converted to variables
            # (explained in the previous construct)
            if traced_instr.argument in context.attribute_variables:
                complete_cover = True
                context.attribute_variables.remove(str(traced_instr.argument))

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

    def _check_variables(
        self,
        context: SlicingContext,
        traced_instr: ExecutedMemoryInstruction,
    ) -> bool:
        complete_cover = False

        # Check local variables
        if traced_instr.opcode in MODIFY_FAST_OPCODES:
            complete_cover = self._check_scope_for_def(
                context.local_var_uses,
                traced_instr.argument,
                traced_instr.code_object_id,
                operator.eq,
            )

        # Check global variables (with *_NAME instructions)
        elif traced_instr.opcode in MODIFY_NAME_OPCODES:
            if (
                traced_instr.code_object_id in self._known_code_objects
                and self._known_code_objects[traced_instr.code_object_id] is not None
                and self._known_code_objects[traced_instr.code_object_id].code_object.co_name
                == "<module>"
            ):
                complete_cover = self._check_scope_for_def(
                    context.global_var_uses,
                    traced_instr.argument,
                    traced_instr.file,
                    operator.eq,
                )
            else:
                complete_cover = self._check_scope_for_def(
                    context.local_var_uses,
                    traced_instr.argument,
                    traced_instr.code_object_id,
                    operator.eq,
                )

        # Check global variables
        elif traced_instr.opcode in MODIFY_GLOBAL_OPCODES:
            complete_cover = self._check_scope_for_def(
                context.global_var_uses,
                traced_instr.argument,
                traced_instr.file,
                operator.eq,
            )

        # Check nonlocal variables
        elif traced_instr.opcode in MODIFY_DEREF_OPCODES:
            complete_cover = self._check_scope_for_def(
                context.nonlocal_var_uses,
                traced_instr.argument,
                traced_instr.code_object_id,
                operator.contains,
            )

        # Check IMPORT_NAME instructions
        # IMPORT_NAME gets a special treatment: it has an incorrect stack effect,
        # but it is compensated by treating it as a definition
        elif traced_instr.opcode in IMPORT_NAME_OPCODES:
            if (
                traced_instr.arg_address
                and hex(traced_instr.arg_address) in context.var_address_uses
                and traced_instr.object_creation
            ):
                complete_cover = True
                context.var_address_uses.remove(hex(traced_instr.arg_address))

        else:
            # There should be no other possible instructions
            raise ValueError("Instruction opcode can not be analyzed for definitions.")

        return complete_cover

    def _check_scope_for_def(
        self,
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
                    remove_tuples.add(tup)  # type: ignore[arg-type]
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
        if traced_instr.arg_address and traced_instr.is_mutable_type:
            self._logger.debug("VARIABLE ADDRESS USE: '%s' address", hex(traced_instr.arg_address))
            context.var_address_uses.add(hex(traced_instr.arg_address))
        # Add local variables
        if traced_instr.opcode in LOAD_FAST_OPCODES:
            self._logger.debug("FAST VARIABLE USE: '%s'", traced_instr.argument)
            context.local_var_uses.add((
                traced_instr.argument,
                traced_instr.code_object_id,
            ))
        # Add global variables (with *_NAME instructions)
        elif traced_instr.opcode in LOAD_NAME_OPCODES:
            self._logger.debug("NAME VARIABLE USE: '%s'", traced_instr.argument)
            if (
                traced_instr.code_object_id in self._known_code_objects
                and self._known_code_objects[traced_instr.code_object_id] is not None
                and self._known_code_objects[traced_instr.code_object_id].code_object.co_name
                == "<module>"
            ):
                context.global_var_uses.add((traced_instr.argument, traced_instr.file))
            else:
                context.local_var_uses.add((
                    traced_instr.argument,
                    traced_instr.code_object_id,
                ))
        # Add global variables
        elif traced_instr.opcode in LOAD_GLOBAL_OPCODES:
            # Starting with Python 3.11, LOAD_GLOBAL uses a tuple for the argument
            if isinstance(traced_instr.argument, tuple):
                argument = traced_instr.argument[1]
            else:
                argument = traced_instr.argument
            self._logger.debug("GLOBAL VARIABLE USE: '%s'", argument)
            context.global_var_uses.add((argument, traced_instr.file))
        # Add nonlocal variables
        elif traced_instr.opcode in LOAD_DEREF_OPCODES + CLOSURE_LOAD_OPCODES:
            variable_scope: set[int] = set()
            current_code_object_id = traced_instr.code_object_id
            while True:
                current_code_meta = self._known_code_objects[current_code_object_id]
                variable_scope.add(current_code_object_id)
                if traced_instr.argument in current_code_meta.code_object.co_cellvars:
                    break

                assert current_code_meta.parent_code_object_id is not None
                current_code_object_id = current_code_meta.parent_code_object_id
            self._logger.debug("DEREF VARIABLE USE: '%s'", traced_instr.argument)
            context.nonlocal_var_uses.add((
                traced_instr.argument,
                tuple(variable_scope),
            ))
        else:
            # There should be no other possible instructions
            raise AssertionError(f"Instruction {traced_instr} can not be analyzed for definitions.")

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
        if not traced_instr.arg_address or traced_instr.opcode in IMPORT_FROM_OPCODES:
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

    def _slicing_criterion_from_assertion(
        self, assertion: ExecutedAssertion, trace: ExecutionTrace
    ) -> SlicingCriterion:
        traced_instr = trace.executed_instructions[assertion.trace_position]
        code_meta = self._known_code_objects[traced_instr.code_object_id]

        # find out the basic block of the assertion
        node = code_meta.original_cfg.get_basic_block_node(traced_instr.node_id)
        assert node is not None, "Invalid node id"

        # the traced instruction is always the jump at the end of the bb
        original_instr = None
        for instr in reversed(tuple(node.original_instructions)):
            if instr.opcode == traced_instr.opcode:
                original_instr = instr
                break
        assert original_instr is not None, "Original instruction not found in basic block"

        unique_instr = UniqueInstruction(
            file=traced_instr.file,
            name=traced_instr.name,
            code_object_id=traced_instr.code_object_id,
            node_id=traced_instr.node_id,
            code_meta=code_meta,
            instr_original_index=traced_instr.instr_original_index,
            arg=original_instr.arg,
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
