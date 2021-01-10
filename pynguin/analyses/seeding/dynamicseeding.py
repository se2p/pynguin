#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Instruments the bytecode to perform dynamic constant seeding."""
from __future__ import annotations

import logging
from types import CodeType
from typing import Optional, Set, cast, AnyStr

from bytecode import BasicBlock, Bytecode, Instr

from pynguin.analyses.controlflow.cfg import CFG
from pynguin.analyses.controlflow.programgraph import ProgramGraphNode
from pynguin.utils import randomness


# pylint:disable=too-few-public-methods
class DynamicSeedingInstrumentation:
    """Instruments code objects to enable dynamic constant seeding.

    Supported is collecting values of the types int, float and string.

    Instrumented are the common compare operations (==, !=, <, >, <=, >=) and the string methods contained in the
    STRING_FUNCTION_NAMES list. This means, if one of the above operations and methods is used in an if-conditional,
     corresponding values are added to the dynamic constant pool.

    General notes:

    When calling a method on an object, the arguments have to be on top of the stack.
    In most cases, we need to rotate the items on the stack with ROT_THREE or ROT_FOUR
    to reorder the elements accordingly.

    A POP_TOP instruction is required after calling a method, because each method
    implicitly returns None."""

    # Compare operations are only followed by one jump operation, hence they are on the second to last position of the
    # block.
    _COMPARE_OP_POS = -2

    #  If one of the considered string functions needing no argument is used in the if statement, it will be loaded in
    #  the third last position. After it comes the call of the method and the jump operation.
    _STRING_FUNC_POS = -3

    # If one of the considered string functions needing one argument is used in the if statement, it will be loaded
    # in the fourth last position. After it comes the load of the argument, the call of the method and the jump
    # operation.
    _STRING_FUNC_POS_WITH_ARG = -4

    # A list containing the names of all string functions which are instrumented.
    _STRING_FUNCTION_NAMES = ["startswith", "endswith", "isalnum", "isalpha", "isdecimal", "isdigit", "isidentifier",
                              "islower", "isnumeric", "isprintable", "isspace", "istitle", "isupper"]

    _logger = logging.getLogger(__name__)
    _instance: Optional[DynamicSeedingInstrumentation] = None
    _dynamic_pool: Optional[Set] = None
    _codeobject_counter: int = None
    _predicate_id_counter: int = None

    def __new__(cls) -> DynamicSeedingInstrumentation:
        if cls._instance is None:
            cls._instance = super(DynamicSeedingInstrumentation, cls).__new__(cls)
            cls._dynamic_pool = set()
            cls._codeobject_counter = 0
            cls._predicate_id_counter = 0
        return cls._instance

    def _instrument_inner_code_objects(
        self, code: CodeType
    ) -> CodeType:
        """Apply the instrumentation to all constants of the given code object.

        Args:
            code: the Code Object that should be instrumented.

        Returns:
            the code object whose constants were instrumented.
        """
        new_consts = []
        for const in code.co_consts:
            if isinstance(const, CodeType):
                # The const is an inner code object
                new_consts.append(
                    self._instrument_code_recursive(
                        const
                    )
                )
            else:
                new_consts.append(const)
        return code.replace(co_consts=tuple(new_consts))

    def _instrument_code_recursive(
        self,
        code: CodeType,
    ) -> CodeType:
        """Instrument the given Code Object recursively.

        Args:
            code: The code object that should be instrumented

        Returns:
            The instrumented code object
        """
        self._logger.debug("Instrumenting Code Object for dynamic seeding for %s", code.co_name)
        cfg = CFG.from_bytecode(Bytecode.from_code(code))

        assert cfg.entry_node is not None, "Entry node cannot be None."
        real_entry_node = cfg.get_successors(cfg.entry_node).pop()  # Only one exists!
        assert real_entry_node.basic_block is not None, "Basic block cannot be None."

        self._instrument_cfg(cfg)
        return self._instrument_inner_code_objects(
            cfg.bytecode_cfg().to_code()
        )

    def _instrument_compare_op(self, block: BasicBlock):
        """ Instruments the compare operations in bytecode. Stores the values extracted at runtime.

        Args:
            block: The containing basic block.

        Returns:
            The id that was assigned to the predicate.
        """
        lineno = block[self._COMPARE_OP_POS].lineno
        block[self._COMPARE_OP_POS: self._COMPARE_OP_POS] = [
            Instr("DUP_TOP_TWO", lineno=lineno),

            Instr("LOAD_CONST", self._dynamic_pool, lineno=lineno),
            Instr("LOAD_METHOD", set.add.__name__, lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),

            Instr("LOAD_CONST", self._dynamic_pool, lineno=lineno),
            Instr("LOAD_METHOD", set.add.__name__, lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno)
        ]
        self._logger.info("Instrumented compare_op")

    def _instrument_startswith_function(self, block: BasicBlock):
        """Instruments the startswith function in bytecode. Stores for the expression 'string1.startswith(string2)' the
           value 'string2 + string1' in the _dynamic_pool.

        Args:
            block: The basic block where the new instructions are inserted.

        Returns:
            The id that was assigned to the predicate.
        """
        insert_pos = self._STRING_FUNC_POS_WITH_ARG + 2  # +2 because we want to insert after the argument is put on the stack
        lineno = block[insert_pos].lineno
        block[insert_pos: insert_pos] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("ROT_TWO", lineno=lineno),
            Instr("BINARY_ADD", lineno=lineno),
            Instr("LOAD_CONST", self._dynamic_pool, lineno=lineno),
            Instr("LOAD_METHOD", set.add.__name__, lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented startswith function")

    def _instrument_endswith_function(self, block: BasicBlock):
        """Instruments the endswith function in bytecode. Stores for the expression 'string1.startswith(string2)' the
           value 'string2 + string1' in the _dynamic_pool.

        Args:
            block: The basic block where the new instructions are inserted.

        Returns:
            The id that was assigned to the predicate.
        """
        insert_pos = self._STRING_FUNC_POS_WITH_ARG + 2  # +2 because we want to insert after the argument is put on the stack
        lineno = block[insert_pos].lineno
        block[insert_pos: insert_pos] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("BINARY_ADD", lineno=lineno),
            Instr("LOAD_CONST", self._dynamic_pool, lineno=lineno),
            Instr("LOAD_METHOD", set.add.__name__, lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented endswith function")

    def _instrument_isalnum_function(self, block: BasicBlock):
        """Instruments the isalnum function in bytecode. If the isalnum() evaluates to true, a value is added to the
        pool for which the isalnum()

        Args:
            block: The basic block where the new instructions are inserted.

        Returns:
            The id that was assigned to the predicate.
        """
        insert_pos = self._STRING_FUNC_POS_WITH_ARG + 2  # +2 because we want to insert after the argument is put on the stack
        lineno = block[insert_pos].lineno
        block[insert_pos: insert_pos] = [
            Instr("DUP_TOP_TWO", lineno=lineno),
            Instr("BINARY_ADD", lineno=lineno),
            Instr("LOAD_CONST", self._dynamic_pool, lineno=lineno),
            Instr("LOAD_METHOD", set.add.__name__, lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("ROT_THREE", lineno=lineno),
            Instr("CALL_METHOD", 1, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]
        self._logger.info("Instrumented endswith function")

    def _instrument_cfg(self, cfg: CFG) -> None:
        """Instrument the bytecode cfg associated with the given CFG.

        Args:
            cfg: The CFG that overlays the bytecode cfg.
        """
        # Attributes which store the predicate ids assigned to instrumented nodes.
        for node in cfg.nodes:
            self._instrument_node(
                node
            )

    def _instrument_string_func(self, block: BasicBlock, function_name: str):
        method_name = "_instrument_" + function_name + "_function"
        method_to_call = getattr(self, method_name)
        method_to_call(block)

    def _instrument_node(
        self,
        node: ProgramGraphNode,
    ):
        """Instrument a single node in the CFG.

        Currently we only instrument conditional jumps and for loops.

        Args:
            node: The node that should be instrumented.

        Returns:
            A predicate id, if the contained a predicate which was instrumented.
        """
        # Not every block has an associated basic block, e.g. the artificial exit node.
        # TODO: check if last instruction of the block is a jump instruction.
        if not node.is_artificial:
            assert (
                node.basic_block is not None
            ), "Non artificial node does not have a basic block."
            assert len(node.basic_block) > 0, "Empty basic block in CFG."
            maybe_compare: Optional[Instr] = (
                node.basic_block[self._COMPARE_OP_POS]
                if len(node.basic_block) > 1
                else None
            )
            maybe_string_func: Optional[Instr] = (
                node.basic_block[self._STRING_FUNC_POS]
                if len(node.basic_block) > 2
                else None
            )
            maybe_string_func_with_arg: Optional[Instr] = (
                node.basic_block[self._STRING_FUNC_POS_WITH_ARG]
                if len(node.basic_block) > 3
                else None
            )
            if isinstance(maybe_compare, Instr) and maybe_compare.name == "COMPARE_OP":
                self._instrument_compare_op(node.basic_block)
            if (
                isinstance(maybe_string_func, Instr) and
                maybe_string_func.name == "LOAD_METHOD" and
                maybe_string_func.arg in self._STRING_FUNCTION_NAMES
            ):
                self._instrument_string_func(node.basic_block, maybe_string_func.arg)
            if (
                isinstance(maybe_string_func_with_arg, Instr) and
                maybe_string_func_with_arg.name == "LOAD_METHOD" and
                maybe_string_func_with_arg.arg in self._STRING_FUNCTION_NAMES
            ):
                self._instrument_string_func(node.basic_block, maybe_string_func_with_arg.arg)

    def instrument_module(self, module_code: CodeType) -> CodeType:
        """Instrument the given code object of a module.

        Args:
            module_code: The code objects of the module

        Returns:
            The instrumented code objects of the module
        """
        return self._instrument_code_recursive(module_code)

    def has_value(self) -> bool:
        """Returns True if at least one value was collected."""
        if len(self._dynamic_pool) > 0:
            return True
        else:
            return False

    def random_int(self) -> int:
        rand_value = cast(int, randomness.choice(tuple(self._dynamic_pool)))
        return rand_value

    def random_string(self) -> AnyStr:
        rand_value = cast(str, randomness.choice(tuple(self._dynamic_pool)))
        return rand_value
