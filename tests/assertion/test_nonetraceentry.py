#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
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
    assert entry._variable == cloned._variable
    assert entry._is_none == cloned._is_none


def test_get_assertions():
    variable = MagicMock()
    entry = nte.NoneTraceEntry(variable, True)
    assertions = entry.get_assertions()
    assert assertions == {nas.NoneAssertion(variable, True)}
