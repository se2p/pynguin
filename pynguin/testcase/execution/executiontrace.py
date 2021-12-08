#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an execution trace"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import inf
from typing import Dict

from ordered_set import OrderedSet


@dataclass
class FileStatementData:
    """Tracks information about statements inside one file."""

    # name of the file of the module that is being tracked
    file_name: str

    # the visited statements and the number of times they were visited
    visited_statements: Dict[int, int] = field(default_factory=dict)

    # overall available statements of a file
    statements: OrderedSet[int] = field(default_factory=OrderedSet)

    # set of ids of the code_objects created for this file
    code_objects: OrderedSet[int] = field(default_factory=OrderedSet)

    def get_file_name(self):
        return self.file_name

    def visit_statement(self, line_number: int, code_object_id: int) -> None:
        """Increment the visits of an already visited statement or add a number to the visited
        statements with its first visit already being counted.

        Args:
            line_number: The line number of the visited statement.
            code_object_id: The id of the code object currently containing the line
        """
        self.code_objects.add(code_object_id)
        if line_number in self.visited_statements:
            self.visited_statements[line_number] += 1
        else:
            self.visited_statements[line_number] = 1

    def track_statement(self, line_number: int) -> None:
        """Add a statement in a line number to the tracked lines

        Args:
            line_number: The tracked line number of an executed statement.
        """
        self.statements.add(line_number)


@dataclass
class ExecutionTrace:
    """Stores trace information about the execution."""

    executed_code_objects: OrderedSet[int] = field(default_factory=OrderedSet)
    executed_predicates: Dict[int, int] = field(default_factory=dict)
    true_distances: Dict[int, float] = field(default_factory=dict)
    false_distances: Dict[int, float] = field(default_factory=dict)
    file_trackers: Dict[str, FileStatementData] = field(default_factory=dict)

    def merge(self, other: ExecutionTrace) -> None:
        """Merge the values from the other trace.

        Args:
            other: Merges the other traces into this trace
        """
        self.executed_code_objects.update(other.executed_code_objects)
        for key, value in other.executed_predicates.items():
            self.executed_predicates[key] = self.executed_predicates.get(key, 0) + value
        self._merge_min(self.true_distances, other.true_distances)
        self._merge_min(self.false_distances, other.false_distances)
        self._merge_file_trackers(self.file_trackers, other.file_trackers)

    @staticmethod
    def _merge_file_trackers(target: Dict[str, FileStatementData], source: Dict[str, FileStatementData]) -> None:
        """
        Merge source file statement data into target file statement data.
        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key in source:
            if key in target:
                target[key].statements.update(source[key].statements)
                target[key].code_objects.update(source[key].code_objects)
                for line in source[key].visited_statements:
                    if line in target[key].visited_statements:
                        source[key].visited_statements[line] += target[key].visited_statements[line]
                    else:
                        source[key].visited_statements[line] = target[key].visited_statements[line]
            else:
                target[key] = source[key]

    @staticmethod
    def _merge_min(target: Dict[int, float], source: Dict[int, float]) -> None:
        """Merge source into target. Minimum value wins.

        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key, value in source.items():
            target[key] = min(target.get(key, inf), value)

    @staticmethod
    def _merge_max(target: Dict[int, float], source: Dict[int, float]) -> None:
        """Merge source into target. Maximum value wins.

        Args:
            target: the target to merge the values in
            source: the source of the merge
        """
        for key, value in source.items():
            target[key] = max(target.get(key, -inf), value)
