#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
import importlib
import inspect
from unittest.mock import MagicMock

import pytest

from pynguin.analyses.module.inheritance import (
    ClassInformation,
    build_class_information,
    build_inheritance_graph,
)


class _Dummy:
    def dummy(self):
        pass  # pragma: no cover


@pytest.fixture
def class_information() -> ClassInformation:
    dummy = _Dummy
    information = ClassInformation(name=dummy.__qualname__, class_object=dummy)
    return information


@pytest.fixture(scope="module")
def inheritance_graph():
    return build_inheritance_graph(
        _extract_classes_from_module("tests.fixtures.cluster.complex_dependencies")
    )


def test_class_information_eq_same(class_information):
    assert class_information.__eq__(class_information)


def test_class_information_eq_other_type(class_information):
    assert not class_information.__eq__("foo")
    assert not class_information.__eq__(
        ClassInformation(name="foo", class_object=class_information.class_object)
    )


def test_class_information_eq_other(class_information):
    other = ClassInformation(name=class_information.name, class_object=ClassInformation)
    assert class_information.__eq__(other)


def test_class_information_hash(class_information):
    assert class_information.__hash__() != 0


@pytest.mark.parametrize(
    "module_name, number_of_nodes, number_of_edges",
    [
        pytest.param("tests.fixtures.cluster.complex_dependencies", 3, 2),
        pytest.param("tests.fixtures.cluster.complex_dependency", 3, 2),
        pytest.param("tests.fixtures.cluster.dependency", 2, 1),
        pytest.param("tests.fixtures.cluster.no_dependencies", 2, 1),
        pytest.param("tests.fixtures.cluster.overridden_inherited_methods", 3, 2),
        pytest.param("tests.fixtures.cluster.typing_parameters", 4, 3),
    ],
)
def test_build_inheritance_graph(module_name, number_of_nodes, number_of_edges):
    graph = build_inheritance_graph(_extract_classes_from_module(module_name))
    assert graph.number_of_nodes() == number_of_nodes
    assert graph.number_of_edges() == number_of_edges


def _extract_classes_from_module(module_name: str) -> set[type]:
    module = importlib.import_module(module_name)
    return {v for _, v in inspect.getmembers(module, inspect.isclass)}


def test_build_class_information():
    dummy = _Dummy
    ci_1 = build_class_information(dummy)
    ci_2 = build_class_information(f"{__name__}._Dummy")
    ci_3 = build_class_information(ci_1)
    assert ci_1 == ci_2 == ci_3


def test_build_class_information_illegal():
    with pytest.raises(ValueError):
        build_class_information(MagicMock())


@pytest.mark.parametrize(
    "type_, expected",
    [
        pytest.param(
            object,
            ClassInformation(name="builtins.object", class_object=object),
        ),
        pytest.param(
            "tests.fixtures.cluster.complex_dependencies.SomeClass",
            ClassInformation(
                name="tests.fixtures.cluster.complex_dependencies.SomeClass",
                class_object=type(None),
            ),
        ),
        pytest.param(MagicMock, None),
    ],
)
def test_inheritance_graph_find(type_, expected, inheritance_graph):
    class_information = build_class_information(type_)
    result = inheritance_graph.find(class_information)
    assert result == expected


def test_inheritance_graph_get_sub_types(inheritance_graph):
    class_information = build_class_information(object)
    result = inheritance_graph.get_sub_types(class_information)
    assert len(result) == 2


def test_inheritance_graph_get_super_types(inheritance_graph):
    class_information = build_class_information(
        "tests.fixtures.cluster.complex_dependencies.SomeClass"
    )
    result = inheritance_graph.get_super_types(class_information)
    assert len(result) == 1


def test_inheritance_graph_get_sub_types_illegal(inheritance_graph):
    with pytest.raises(ValueError):
        inheritance_graph.get_sub_types(build_class_information(MagicMock))


def test_inheritance_graph_get_super_types_illegal(inheritance_graph):
    with pytest.raises(ValueError):
        inheritance_graph.get_super_types(build_class_information(MagicMock))


def test_inheritance_graph_get_distance():
    inheritance_graph = build_inheritance_graph(
        _extract_classes_from_module(
            "tests.fixtures.cluster.overridden_inherited_methods"
        )
    )
    nodes = list(inheritance_graph._graph.nodes)
    nodes.sort(key=lambda n: n.name)
    ci_object, ci_bar, ci_foo = tuple(nodes)
    assert inheritance_graph.get_distance(ci_bar, ci_bar) == 0
    assert inheritance_graph.get_distance(ci_foo, ci_bar) == 1
    assert inheritance_graph.get_distance(ci_bar, ci_object) == -2
    with pytest.raises(ValueError):
        inheritance_graph.get_distance(ci_object, None)
    with pytest.raises(ValueError):
        inheritance_graph.get_distance(None, ci_bar)
