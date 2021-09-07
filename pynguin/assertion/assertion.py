#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a base class for assertions."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any, Dict, Optional

import pynguin.assertion.assertionvisitor as av
import pynguin.testcase.variable.variablereference as vr


class Assertion:
    """Base class for assertions."""

    def __init__(self, source: Optional[vr.VariableReference], value: Any) -> None:
        """Create new assertion.

        Args:
            source: optional for a variable in the testcase on which we assert something.
            value: the expected value of the assertion.
        """
        self._source = source
        self._value = value

    @property
    def source(self) -> Optional[vr.VariableReference]:
        """Provides an optional for the variable on which the assertion is made.

        Returns:
            an optional for variable on which the assertion is made.
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
    def clone(
        self, memo: Dict[vr.VariableReference, vr.VariableReference]
    ) -> Assertion:
        """Clone this assertion.

        Args:
            memo: Mapping from old to new variables.

        Returns: the cloned assertion
        """

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Assertion)
            and self._source == other._source
            and self._value == other._value
        )

    def __hash__(self) -> int:
        return hash((self._source, self._value))
