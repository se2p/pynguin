#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
"""Provides tools to build an inheritance graph of the subject under test."""
from __future__ import annotations

import inspect
from typing import Any, NamedTuple, overload

import networkx as nx


class ClassInformation(NamedTuple):
    """Stores class information in form of fully-qualified name and class object."""

    name: str
    class_object: type

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, ClassInformation):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)

    def __str__(self) -> str:
        return f"ClassInformation({self.name}, {self.class_object})"

    def __repr__(self) -> str:
        return f"ClassInformation({self.name}, {self.class_object})"


class InheritanceGraph:
    """Represents the inheritance structure of the found types."""

    def __init__(self) -> None:
        self._graph = nx.DiGraph()

    def add_edge(self, source: ClassInformation, target: ClassInformation) -> None:
        """Adds an edge to the graph.

        An edge is a sub-type relation between two classes, as yielded, for example,
        by querying the method-resolution order.

        Args:
            source: The super class
            target: The sub class
        """
        self._graph.add_edge(source, target)

    def find(self, class_information: ClassInformation) -> ClassInformation | None:
        """Finds a class in the inheritance graph.

        Args:
            class_information: The class to search for

        Returns:
            The class, if it was found.  None otherwise.
        """
        if self._graph.has_node(class_information):
            for node in self._graph.nodes.keys():
                if class_information == node:
                    return node
        return None

    def get_sub_types(
        self, class_information: ClassInformation
    ) -> set[ClassInformation]:
        """Provides a set of sub types for a class.

        If there are no sub types, the returned set is empty.

        Args:
            class_information: The class to start

        Returns:
            The sub types of the class
        """
        if graph_node := self.find(class_information):
            return self._get_transitive_successors(graph_node, set())
        raise ValueError("Node for class not found in inheritance graph.")

    def _get_transitive_successors(
        self, node: ClassInformation, done: set[ClassInformation]
    ) -> set[ClassInformation]:
        successors: set[ClassInformation] = set()
        for successor_node in self._get_successors(node):
            if successor_node not in done:
                successors.add(successor_node)
                done.add(successor_node)
                successors.update(self._get_transitive_successors(successor_node, done))
        return successors

    def _get_successors(self, node: ClassInformation) -> set[ClassInformation]:
        successors: set[ClassInformation] = set()
        for successor in self._graph.successors(node):
            successors.add(successor)
        return successors

    def get_super_types(
        self, class_information: ClassInformation
    ) -> set[ClassInformation]:
        """Provides a set of super types for a class.

        If there are no super types, the returned set is empty.

        Args:
            class_information: The class to start

        Returns:
            The super types of the class
        """
        if graph_node := self.find(class_information):
            return self._get_transitive_predecessors(graph_node, set())
        raise ValueError("Node for class not found in inheritance graph.")

    def _get_transitive_predecessors(
        self, node: ClassInformation, done: set[ClassInformation]
    ) -> set[ClassInformation]:
        predecessors: set[ClassInformation] = set()
        for predecessor_node in self._get_predecessors(node):
            if predecessor_node not in done:
                predecessors.add(predecessor_node)
                done.add(predecessor_node)
                predecessors.update(
                    self._get_transitive_predecessors(predecessor_node, done)
                )
        return predecessors

    def _get_predecessors(self, node: ClassInformation) -> set[ClassInformation]:
        predecessors: set[ClassInformation] = set()
        for predecessor in self._graph.predecessors(node):
            predecessors.add(predecessor)
        return predecessors

    def get_distance(self, source: ClassInformation, target: ClassInformation) -> int:
        """Computes the shortest distance between two nodes of the graph.

        The distance will be positive if target is a sub-type of source and negative
        if target is a super-type of source.  If source and target are the same node,
        the distance will be 0.

        Args:
            source: The source node
            target: The target node

        Returns:
            The (shortest) distance between the two nodes in the graph

        Raises:
            ValueError: if one of the class-information objects are not part of the
            graph
            nx.NetworkXNoPath: if no path between the nodes exists
        """
        if self.find(source) is None or self.find(target) is None:
            raise ValueError("Both elements need to be part of the graph")
        try:
            return nx.shortest_path_length(self._graph, source, target)
        except nx.NetworkXNoPath:
            return (-1) * nx.shortest_path_length(self._graph, target, source)

    def number_of_nodes(self) -> int:
        """Provides the number of nodes in the graph.

        Returns:
            The number of nodes in the graph
        """
        return self._graph.number_of_nodes()

    def number_of_edges(self) -> int:
        """Provides the number of edges in the graph.

        Returns:
            The number of edges in the graph
        """
        return self._graph.number_of_edges()


def build_inheritance_graph(analysed_classes: set[type]) -> InheritanceGraph:
    """Builds an inheritance graph for a set of types.

    Args:
        analysed_classes: The set of available types in the program

    Returns:
        The inheritance graph for these types
    """
    graph = InheritanceGraph()
    for analysed_class in analysed_classes:
        mro_class_information = [
            _retrieve_class_information(class_)
            for class_ in inspect.getmro(analysed_class)
        ]
        for target, source in zip(mro_class_information, mro_class_information[1:]):
            graph.add_edge(source, target)
    return graph


@overload
def build_class_information(value: ClassInformation) -> ClassInformation:
    ...  # pragma: no cover


@overload
def build_class_information(value: str) -> ClassInformation:
    ...  # pragma: no cover


@overload
def build_class_information(value: type) -> ClassInformation:
    ...  # pragma: no cover


def build_class_information(value) -> ClassInformation:
    """Builds the class-information object.

    The parameter can either be of type `ClassInformation`, `str`, or `type`.  For
    other inputs, a `ValueError` is raised.

    Args:
        value: The value to build the class-information object from

    Returns:
        A class-information object

    Raises:
        ValueError: In case no appropriate input was given
    """
    if isinstance(value, ClassInformation):
        return value
    if isinstance(value, str):
        return ClassInformation(name=value, class_object=type(None))
    if isinstance(value, type):
        return _retrieve_class_information(value)
    raise ValueError(f"Cannot build ClassInformation for {value}")


def _retrieve_class_information(class_object: type) -> ClassInformation:
    qualified_name = class_object.__qualname__
    name = class_object.__name__
    module_name = class_object.__module__
    if name == qualified_name:
        qualified_name = f"{module_name}.{name}"
    class_information = ClassInformation(name=qualified_name, class_object=class_object)
    return class_information
