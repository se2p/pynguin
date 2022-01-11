#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a base class for assertions performed on variables."""
import abc
from typing import Any

import pynguin.assertion.assertion as ass
import pynguin.testcase.variablereference as vr


class VariableAssertion(ass.Assertion, metaclass=abc.ABCMeta):
    """Base class for variable assertions."""

    def __init__(self, source: vr.VariableReference, value: Any) -> None:
        super().__init__(source, value)

    @property
    def source(self) -> vr.VariableReference:
        if self._source:
            return self._source
        raise ValueError("Source should not be none.")
