#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.noneassertion as nas
import pynguin.assertion.nonetraceentry as nte


def test_init():
    variable = MagicMock()
    entry = nte.NoneTraceEntry(variable, True)
    assert entry._variable == variable
    assert entry._is_none


def test_clone():
    variable = MagicMock()
    entry = nte.NoneTraceEntry(variable, True)
    cloned = entry.clone()
    assert cloned == nte.NoneTraceEntry(variable, True)


def test_get_assertions():
    variable = MagicMock()
    entry = nte.NoneTraceEntry(variable, True)
    assertions = entry.get_assertions()
    assert assertions == {nas.NoneAssertion(variable, True)}


def test_eq():
    variable = MagicMock()
    assert nte.NoneTraceEntry(variable, True) == nte.NoneTraceEntry(variable, True)


def test_neq():
    variable = MagicMock()
    assert nte.NoneTraceEntry(variable, False) != nte.NoneTraceEntry(variable, True)


def test_hash():
    variable = MagicMock()
    assert hash(nte.NoneTraceEntry(variable, True)) == hash(
        nte.NoneTraceEntry(variable, True)
    )


def test_hash_neq():
    variable = MagicMock()
    assert hash(nte.NoneTraceEntry(variable, False)) != hash(
        nte.NoneTraceEntry(variable, True)
    )
