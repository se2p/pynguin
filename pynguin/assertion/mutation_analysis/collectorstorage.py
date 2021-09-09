#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Storage for collected data, which was collected during a testcase execution."""
import copy
from types import ModuleType
from typing import Any, Dict, List

import pynguin.utils.collection_utils as cu


class CollectorStorage:
    """
    Class for storing the collected data during from test instrumentation for the
    mutation analysis approach for assertion generation.
    """

    KEY_TEST_ID = "__ID__"
    KEY_POSITION = "__POS__"
    KEY_RETURN_VALUE = "__RV__"
    KEY_GLOBALS = "__G__"
    KEY_CLASS_FIELD = "__CF__"
    KEY_OBJECT_ATTRIBUTE = "__OA__"

    _entries: List[List[Dict[str, Any]]] = [[]]
    _execution_index: int = 0

    @staticmethod
    def insert(entry: Dict[str, Any]) -> None:
        """Inserts an entry to to all the class level entries.
        If an entry with the same test id and position are already in the entries,
        the other values will be merged.
        Otherwise a new item will be appended to the list.

        Args:
            entry: a dict for a new entry or an entry with more fields.
        """
        entry_list = CollectorStorage._entries[CollectorStorage._execution_index]
        index = next(
            (
                i
                for i, d in enumerate(entry_list)
                if d[CollectorStorage.KEY_TEST_ID]
                == entry[CollectorStorage.KEY_TEST_ID]
                and d[CollectorStorage.KEY_POSITION]
                == entry[CollectorStorage.KEY_POSITION]
            ),
            None,
        )
        if index is not None:
            new = {
                **CollectorStorage._entries[CollectorStorage._execution_index][index],
                **entry,
            }
            CollectorStorage._entries[CollectorStorage._execution_index][index] = new
        else:
            CollectorStorage._entries[CollectorStorage._execution_index].append(entry)

    @staticmethod
    def append_execution() -> None:
        """Creates a new entry for the next execution.
        Here the index gets incremented and a new empty list is appended to the list of
        entries.
        """
        CollectorStorage._execution_index += 1
        CollectorStorage._entries.append([])

    @staticmethod
    def collect_states(
        test_case_id: int = 0,
        position: int = 0,
        objects: List[object] = None,
        modules: Dict[str, Any] = None,
        return_value=None,
    ) -> None:
        """Collects the states of all fields. These include fields at global level as
        well as class level and attributes of the given object.

        Args:
            test_case_id: Integer value of the current test case id.
            position: Integer value of the current position in the test case.
            objects: List of objects for which the states should be collected.
            modules: Dict of modules with their respective representation.
            return_value: The return value of the preceding invoke.
        """
        if objects is None:
            objects = []

        def condition(item) -> bool:
            return (
                not item[0].startswith("__")
                and not item[0].endswith("__")
                and not callable(item[1])
                and not isinstance(item[1], ModuleType)
            )

        # Log testcase id, position in the test case and return value
        states = {
            CollectorStorage.KEY_TEST_ID: test_case_id,
            CollectorStorage.KEY_POSITION: position,
            CollectorStorage.KEY_RETURN_VALUE: copy.deepcopy(return_value),
        }

        # Log global fields
        if modules and len(modules) > 0:
            global_dict = {}
            for module_alias, module in modules.items():
                global_dict[module_alias] = dict(
                    filter(condition, vars(module).items())
                )
            states[CollectorStorage.KEY_GLOBALS] = global_dict

        for index, obj in enumerate(objects):
            # Log all class variables and object attributes
            objdict = {
                CollectorStorage.KEY_CLASS_FIELD: dict(
                    filter(condition, vars(obj.__class__).items())
                ),
                CollectorStorage.KEY_OBJECT_ATTRIBUTE: vars(obj),
            }

            # TODO(fs) find corresponding mutation and exclude those
            # Some mutations will result in type errors when performing a deepcopy
            try:
                states[CollectorStorage._get_object_key(index)] = copy.deepcopy(objdict)
            except TypeError:
                pass

        # Append the collected data to collector storage
        CollectorStorage.insert(states)

    @staticmethod
    def _get_object_key(index: int) -> str:
        return f"__OBJ-{index}__"

    @staticmethod
    def get_items(index: int) -> List[Dict[str, Any]]:
        """Gets the collected states of the given execution index.

        Args:
            index: The index of execution which data should be returned

        Returns: A list of all states of the execution.
        """
        return CollectorStorage._entries[index]

    @staticmethod
    def get_data_of_mutations() -> List[List[Dict[str, Any]]]:
        """Only get the data of the executions on the mutated version of the module.

        Returns: A list of all the data collected during the execution on
                 mutated modules.
        """
        return CollectorStorage._entries[1:]

    @staticmethod
    def get_dataframe_of_mutations(
        test_case_id: int, position: int
    ) -> List[Dict[str, Any]]:
        """Gets the dataframes of all mutations for a given testcase id and position.

        Args:
            test_case_id: for the id of the testcase.
            position: for the position.

        Returns: A list of all dataframes with matching test case id and position,
                 which where collected during executions on mutated modules.
        """

        dict_filter = {
            CollectorStorage.KEY_TEST_ID: test_case_id,
            CollectorStorage.KEY_POSITION: position,
        }
        dataframe: List[Dict[str, Any]] = []
        for mutation in CollectorStorage.get_data_of_mutations():
            dataframe = [*dataframe, *cu.filter_dictlist_by_dict(dict_filter, mutation)]
        return dataframe
