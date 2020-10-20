#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a base class for assertions."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pynguin.assertion.assertionvisitor as av
import pynguin.testcase.testcase as tc  # pylint:disable=cyclic-import
import pynguin.testcase.variable.variablereference as vr


class Assertion:
    """Base class for assertions."""

    def __init__(self, source: vr.VariableReference, value: Any) -> None:
        """Create new assertion.

        Args:
            source: the variable on which we assert something.
            value: the expected value of the assertion.
        """
        self._source = source
        self._value = value

    @property
    def source(self) -> vr.VariableReference:
        """Provides the variable on which the assertion is made.

        Returns:
            the variable on which the assertion is made.
        """
        return self._source

    @property
    def value(self) -> Any:
        """Provides the expected value of the assertion.

        Returns:
            the expected value of the assertion.
        """
        return self._value

    @abstractmethod
    def accept(self, visitor: av.AssertionVisitor) -> None:
        """Accept an assertion visitor.

        Args:
            visitor: the visitor that is accepted.
        """

    @abstractmethod
    def clone(self, new_test_case: tc.TestCase, offset: int) -> Assertion:
        """Clone this assertion into the new test case at the given offset.

        Args:
            new_test_case: the test case in which this assertion cloned.
            offset: the offset at which the assertion is cloned.

        Returns: the cloned assertion
        """

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Assertion):
            return False
        if self is other:
            return True
        return self._source == other._source and self._value == other._value

    def __hash__(self) -> int:
        return hash((self._source, self._value))
