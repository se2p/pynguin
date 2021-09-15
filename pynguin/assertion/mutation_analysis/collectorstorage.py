#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Storage for collected data, which was collected during a testcase execution."""
import copy
from types import ModuleType
from typing import Any, Dict, List, Optional

import pynguin.utils.collection_utils as cu

KEY_TEST_ID = "__ID__"
KEY_POSITION = "__POS__"
KEY_RETURN_VALUE = "__RV__"
KEY_GLOBALS = "__G__"
KEY_CLASS_FIELD = "__CF__"
KEY_OBJECT_ATTRIBUTE = "__OA__"


class CollectorStorage:
    """
    Class for storing the collected data during from test instrumentation for the
    mutation analysis approach for assertion generation.
    """

    def __init__(self):
        """Creates a new CollectorStorage."""
        self._entries: List[List[Dict[str, Any]]] = [[]]
        self._execution_index: int = 0

    def insert(self, entry: Dict[str, Any]) -> None:
        """Inserts an entry to to all the class level entries.
        If an entry with the same test id and position are already in the entries,
        the other values will be merged.
        Otherwise a new item will be appended to the list.

        Args:
            entry: a dict for a new entry or an entry with more fields.
        """

        def condition(item):
            return (
                item[KEY_TEST_ID] == entry[KEY_TEST_ID]
                and item[KEY_POSITION] == entry[KEY_POSITION]
            )

        entry_list = self._entries[self._execution_index]

        index = next((i for i, d in enumerate(entry_list) if condition(d)), None)

        if index is not None:
            new = {
                **self._entries[self._execution_index][index],
                **entry,
            }
            self._entries[self._execution_index][index] = new
        else:
            self._entries[self._execution_index].append(entry)

    def append_execution(self) -> None:
        """Creates a new entry for the next execution.
        Here the index gets incremented and a new empty list is appended to the list of
        entries.
        """
        self._execution_index += 1
        self._entries.append([])

    # pylint: disable=too-many-arguments
    def collect_states(
        self,
        test_case_id: int = 0,
        position: int = 0,
        objects: Optional[List[Any]] = None,
        modules: Optional[Dict[str, Any]] = None,
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
            KEY_TEST_ID: test_case_id,
            KEY_POSITION: position,
            KEY_RETURN_VALUE: copy.deepcopy(return_value),
        }

        # Log global fields
        if modules and len(modules) > 0:
            global_dict = {}
            for module_alias, module in modules.items():
                global_dict[module_alias] = {
                    k: v for (k, v) in vars(module).items() if condition((k, v))
                }
            states[KEY_GLOBALS] = global_dict

        for index, obj in enumerate(objects):
            # Log all class variables and object attributes
            objdict = {
                KEY_CLASS_FIELD: {
                    k: v for (k, v) in vars(obj.__class__).items() if condition((k, v))
                },
                KEY_OBJECT_ATTRIBUTE: vars(obj),
            }

            # TODO(fs) find corresponding mutation and exclude those
            # Some mutations will result in type errors when performing a deepcopy
            try:
                states[self._get_object_key(index)] = copy.deepcopy(objdict)
            except TypeError:
                pass

        # Append the collected data to collector storage
        self.insert(states)

    @staticmethod
    def _get_object_key(index: int) -> str:
        return f"__OBJ-{index}__"

    def get_items(self, index: int) -> List[Dict[str, Any]]:
        """Gets the collected states of the given execution index.

        Args:
            index: The index of execution which data should be returned

        Returns: A list of all states of the execution.
        """
        return self._entries[index]

    def get_data_of_mutations(self) -> List[List[Dict[str, Any]]]:
        """Only get the data of the executions on the mutated version of the module.

        Returns: A list of all the data collected during the execution on
                 mutated modules.
        """
        # The first value in the _entries contains the data from the execution on
        # the not mutated module. But here we just need the values from the execution
        # on the mutated modules, so we omit the first value.
        return self._entries[1:]

    def get_dataframe_of_mutations(
        self, test_case_id: int, position: int
    ) -> List[Dict[str, Any]]:
        """Gets the dataframes of all mutations for a given testcase id and position.

        Args:
            test_case_id: for the id of the testcase.
            position: for the position.

        Returns: A list of all dataframes with matching test case id and position,
                 which where collected during executions on mutated modules.
        """
        dict_filter = {
            KEY_TEST_ID: test_case_id,
            KEY_POSITION: position,
        }
        dataframe: List[Dict[str, Any]] = []
        for mutation in self.get_data_of_mutations():
            dataframe.extend(cu.filter_dictlist_by_dict(dict_filter, mutation))
        return dataframe
