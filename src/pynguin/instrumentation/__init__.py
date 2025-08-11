#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the instrumentation mechanisms."""

from __future__ import annotations

import enum
import logging

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from types import CodeType
from typing import TYPE_CHECKING

from bytecode import Bytecode
from bytecode import Instr

from pynguin.analyses.controlflow import CFG
from pynguin.analyses.controlflow import BasicBlockNode
from pynguin.analyses.controlflow import ControlDependenceGraph


if TYPE_CHECKING:
    from types import CodeType

    from pynguin.instrumentation.tracer import SubjectProperties


@enum.unique
class PynguinCompare(enum.IntEnum):
    """Enum of all compare operations.

    Previously we were able to use a similar enum from the bytecode library,
    because upto 3.8, there was only a single compare op. With 3.9+, there are now some
    separate compare ops, e.g., IS_OP or CONTAINS_OP. Therefore, we recreate the
    original enum here and map these new ops back.
    """

    LT = 0
    LE = 1
    EQ = 2
    NE = 3
    GT = 4
    GE = 5
    IN = 6
    NOT_IN = 7
    IS = 8
    IS_NOT = 9
    EXC_MATCH = 10


@dataclass
class CodeObjectMetaData:
    """Stores meta data of a code object."""

    # The instrumented code object.
    code_object: CodeType

    # The original code object, before instrumentation.
    original_code_object: CodeType

    # Id of the parent code object, if any
    parent_code_object_id: int | None

    # CFG of this code object
    cfg: CFG

    # CFG of the original code object, before instrumentation.
    original_cfg: CFG

    # CDG of this code object
    cdg: ControlDependenceGraph

    def __getstate__(self) -> dict:
        return {
            "code_object": self.code_object,
            "original_code_object": self.original_code_object,
            "parent_code_object_id": self.parent_code_object_id,
            "cfg": self.cfg,
            "original_cfg": self.original_cfg,
            "cdg": self.cdg,
        }

    def __setstate__(self, state: dict) -> None:
        self.code_object = state["code_object"]
        self.original_code_object = state["original_code_object"]
        self.parent_code_object_id = state["parent_code_object_id"]
        self.cfg = state["cfg"]
        self.original_cfg = state["original_cfg"]
        self.cdg = state["cdg"]


@dataclass
class PredicateMetaData:
    """Stores meta data of a predicate."""

    # Line number where the predicate is defined.
    line_no: int

    # Id of the code object where the predicate was defined.
    code_object_id: int

    # The node in the program graph, that defines this predicate.
    node: BasicBlockNode


class ArtificialInstr(Instr):
    """Marker subclass of an instruction.

    Used to distinguish between original instructions and instructions that were
    inserted by the instrumentation.
    """


class InstrumentationTransformer(ABC):
    """Applies a given list of instrumentation adapters to code objects.

    This class is responsible for traversing all nested code objects and their
    basic blocks and requesting their instrumentation from the given adapters.

    Ideally we would want something like ASM with nested visitors where changes from
    different adapters don't affect each other, but that's a bit of overkill for now.
    """

    _logger = logging.getLogger(__name__)

    def __init__(self, subject_properties: SubjectProperties):
        """Initialize the instrumentation transformer.

        Args:
            subject_properties: The properties of the subject that is being instrumented
        """
        self._subject_properties = subject_properties

    @property
    def subject_properties(self) -> SubjectProperties:
        """Get the subject properties that are used for the instrumentation.

        Returns:
            The subject properties that are used for the instrumentation.
        """
        return self._subject_properties

    def instrument_module(self, module_code: CodeType) -> CodeType:
        """Instrument the given code object of a module.

        Args:
            module_code: The code object of the module

        Returns:
            The instrumented code object of the module
        """
        self._check_module_not_instrumented(module_code)

        return self._instrument_code_recursive(module_code)

    def _check_module_not_instrumented(self, module_code: CodeType) -> None:
        for metadata in self._subject_properties.existing_code_objects.values():
            if metadata.code_object is module_code or metadata.original_code_object is module_code:
                # Abort instrumentation, since we have already
                # instrumented this code object.
                raise AssertionError("Tried to instrument already instrumented module.")

    def _instrument_code_recursive(
        self,
        code: CodeType,
        parent_code_object_id: int | None = None,
    ) -> CodeType:
        self._logger.debug("Instrumenting Code Object for %s", code.co_name)

        cfg = CFG.from_bytecode(Bytecode.from_code(code))

        code_object_id = self._subject_properties.create_code_object_id()

        instrumented_code = self._visit_nodes(
            code,
            cfg,
            code_object_id,
        )

        self._subject_properties.register_code_object(
            code_object_id,
            CodeObjectMetaData(
                code_object=instrumented_code,
                original_code_object=code,
                parent_code_object_id=parent_code_object_id,
                cfg=cfg,
                original_cfg=CFG.from_bytecode(Bytecode.from_code(code)),
                cdg=ControlDependenceGraph.compute(cfg),
            ),
        )

        return instrumented_code

    @abstractmethod
    def _visit_nodes(
        self,
        code: CodeType,
        cfg: CFG,
        code_object_id: int,
    ) -> CodeType:
        """Visit all nodes in the CFG and instrument them recursively.

        Args:
            code: The code object that should be instrumented
            cfg: The control flow graph of the code object
            code_object_id: The ID of the code object

        Returns:
            The instrumented code object
        """
