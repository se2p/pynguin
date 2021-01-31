#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from pynguin.utils.namingscope import NamingScope


def test_naming_scope_same():
    scope = NamingScope()
    some_object = "something"
    name1 = scope.get_name(some_object)
    name2 = scope.get_name(some_object)
    assert name1 == name2


def test_naming_scope_different():
    scope = NamingScope()
    name1 = scope.get_name("one name")
    name2 = scope.get_name("another")
    assert name1 != name2


def test_naming_scope_known_indices_empty():
    scope = NamingScope()
    assert scope.known_name_indices == {}


def test_naming_scope_known_indices_not_empty():
    scope = NamingScope()
    some_object = "something"
    scope.get_name(some_object)
    assert scope.known_name_indices == {some_object: 0}
