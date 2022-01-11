#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.primitiveassertion as pas
import pynguin.assertion.primitivetraceentry as pte


def test_init():
    variable = MagicMock()
    entry = pte.PrimitiveTraceEntry(variable, True)
    assert entry._variable == variable
    assert entry._value


def test_clone():
    variable = MagicMock()
    entry = pte.PrimitiveTraceEntry(variable, True)
    cloned = entry.clone()
    assert cloned == pte.PrimitiveTraceEntry(variable, True)


def test_get_assertions():
    variable = MagicMock()
    entry = pte.PrimitiveTraceEntry(variable, True)
    assertions = entry.get_assertions()
    assert assertions == {pas.PrimitiveAssertion(variable, True)}


def test_eq():
    variable = MagicMock()
    assert pte.PrimitiveTraceEntry(variable, True) == pte.PrimitiveTraceEntry(
        variable, True
    )


def test_neq():
    variable = MagicMock()
    assert pte.PrimitiveTraceEntry(variable, False) != pte.PrimitiveTraceEntry(
        variable, True
    )


def test_hash():
    variable = MagicMock()
    assert hash(pte.PrimitiveTraceEntry(variable, True)) == hash(
        pte.PrimitiveTraceEntry(variable, True)
    )


def test_hash_neq():
    variable = MagicMock()
    assert hash(pte.PrimitiveTraceEntry(variable, False)) != hash(
        pte.PrimitiveTraceEntry(variable, True)
    )
