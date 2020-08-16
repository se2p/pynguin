#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from pynguin.utils.string import String


def test_eq():
    test = String("Test")
    var = test == "Search"
    assert "Search" in String.observed
    assert not var


def test_not_eq():
    test = String("Test")
    var = test == 42
    assert not var


def test_startswith():
    test = String("Test")
    var = test.startswith("Startswith")
    assert "Startswith" in String.observed
    assert not var


def test_endswith():
    test = String("Test")
    var = test.endswith("Endswith")
    assert "Endswith" in String.observed
    assert not var


def test_hash():
    test = String("Test")
    assert test.__hash__() == hash("Test")
