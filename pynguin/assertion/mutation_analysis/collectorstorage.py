#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Storage for collected data, which was collected during a testcase execution."""
import copy
import enum
import logging
from types import ModuleType
from typing import Any, Dict, List, Tuple

import pynguin.testcase.statement as st
import pynguin.testcase.variablereference as vr


class EntryTypes(enum.Enum):
    """
    Enum for all different entry types which can appear in the storage.
    """

    RETURN_VALUE = enum.auto()
    CLASS_FIELD = enum.auto()
    OBJECT_ATTRIBUTE = enum.auto()
    GLOBAL_FIELD = enum.auto()


class CollectorStorage:
    """
    Class for storing the collected data during from test instrumentation for the
    mutation analysis approach for assertion generation.
    """

    _logger = logging.getLogger(__name__)

    def __init__(self):
        """Creates a new CollectorStorage."""
        self._storage: List[Dict[Tuple[Any, ...], Any]] = []

    def collect(
        self,
        statement: st.Statement,
        return_value: Any,
        objects: Dict[vr.VariableReference, Any],
        modules: Dict[str, ModuleType],
    ) -> None:
        """Collects the return value, objects fields and global fields by adding those
        to the storage. When collecting object fields both attribute values as well as
        class fields of the corresponding object classes are collected and stored.

        Args:
            statement: the statement, for which the return_value should be stored
            return_value: the value to be stored
            objects: dictionary with the variable reference of the object and
                     the value of it as its value
            modules: a dictionary of all modules, from where all module global variables
                     should be collected and stored. The key of the dictionary is the
                     module alias and the value of the dictionary is the module itself.
        """
        self._collect_return_value(statement, return_value)
        self._collect_objects(statement, objects)
        self._collect_globals(statement, modules)

    def _collect_return_value(self, statement: st.Statement, return_value: Any) -> None:
        """Collects a return value by adding it to the storage.

        Args:
            statement: the statement, for which the return_value should be stored
            return_value: the value to be stored
        """
        entry = self._get_current_exec()
        if self._filter_condition(("", return_value)):
            try:
                entry[(EntryTypes.RETURN_VALUE, statement)] = copy.deepcopy(
                    return_value
                )
            except TypeError:
                self._logger.debug("Return value couldn't be deep-copied.")

    def _collect_objects(
        self, statement: st.Statement, objects: Dict[vr.VariableReference, Any]
    ) -> None:
        """Collects all object field values by adding those to the storage.
        Here attribute values of the given objects and class fields of the
        corresponding classes are collected and stored.

        Args:
            statement: the statement of where the states of the objects should be
                       stored.
            objects: dictionary with the variable reference of the object and
                     the value of it as its value
        """
        for obj_vr, obj in objects.items():

            # Collect object attributes
            self._collect_object_attributes(obj, obj_vr, statement)

            # Collect class fields
            self._collect_class_fields(obj, statement)

    def _collect_object_attributes(
        self, obj: Any, obj_vr: vr.VariableReference, statement: st.Statement
    ):
        entry = self._get_current_exec()
        for field, value in vars(obj).items():
            if self._filter_condition((field, value)):
                try:
                    entry[
                        (
                            EntryTypes.OBJECT_ATTRIBUTE,
                            statement,
                            obj_vr,
                            field,
                        )
                    ] = copy.deepcopy(value)
                except TypeError:
                    self._logger.debug("Object attribute couldn't be deep-copied.")

    def _collect_class_fields(self, obj: Any, statement: st.Statement):
        entry = self._get_current_exec()
        for field, value in vars(obj.__class__).items():
            if self._filter_condition((field, value)):
                try:
                    entry[
                        (
                            EntryTypes.CLASS_FIELD,
                            statement,
                            obj.__class__,
                            field,
                        )
                    ] = copy.deepcopy(value)
                except TypeError:
                    self._logger.debug("Class field couldn't be deep-copied.")

    def _collect_globals(
        self, statement: st.Statement, modules: Dict[str, ModuleType]
    ) -> None:
        """Collects global values by adding them to the storage.

        Args:
            statement: statement of which the globals should be stored.
            modules: a dictionary of all modules, from where all module global variables
                     should be collected and stored. The key of the dictionary is the
                     module alias and the value of the dictionary is the module itself.
        """
        entry = self._get_current_exec()
        for _, module in modules.items():
            module_name = module.__name__
            for (field_name, field_value) in vars(module).items():
                if self._filter_condition(
                    (field_name, field_value)
                ) and not field_name.startswith("_"):
                    try:
                        entry[
                            (
                                EntryTypes.GLOBAL_FIELD,
                                statement,
                                module_name,
                                field_name,
                            )
                        ] = copy.deepcopy(field_value)
                    except TypeError:
                        self._logger.debug("Global value couldn't be deep-copied.")

    def _get_current_exec(self) -> Dict[Tuple[Any, ...], Any]:
        return self._storage[len(self._storage) - 1]

    def append_execution(self) -> None:
        """
        Creates a new entry for an execution.
        Here a new empty dict is appended to the list of stored entries.
        """
        self._storage.append({})

    def get_execution_entry(self, index: int) -> Dict[Tuple[Any, ...], Any]:
        """Gets the entry of execution at the given index.

        Args:
            index: integer value of the index of the execution, which should be fetched

        Returns:
            the dictionary containing all entries of the execution on the given index.
        """
        if len(self._storage) <= index:
            raise IndexError("Index out of range.")
        return self._storage[index]

    def get_mutations(self, key: Tuple[Any, ...]) -> List[Any]:
        """Gets all values of the executions on mutated modules to a specific key.

        Args:
            key: the key of the dicts for which should be searched for

        Returns:
            A list of all values matching the key in the dictionaries collected during
            the executions on the mutated modules
        """
        mutations = []
        for item in self._storage[1:]:
            val = item.get(key, None)
            # TODO(fk) isn't None a valid value here?
            if val is not None:
                mutations.append(val)
        return mutations

    @staticmethod
    def _filter_condition(item: Tuple[str, Any]) -> bool:
        return (
            not item[0].startswith("__")
            and not item[0].endswith("__")
            and not callable(item[1])
            and not isinstance(item[1], ModuleType)
        )
