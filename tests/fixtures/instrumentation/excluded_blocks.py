#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Test fixture for excluded block patterns."""
from typing import TYPE_CHECKING
import typing
import types


def regular_function():
    """This should be covered."""
    return 42


if __name__ == "__main__":
    # Lines 18-20 should be excluded
    print("Running as main")
    regular_function()


if TYPE_CHECKING:
    # Lines 23-25 should be excluded
    from typing import TypeAlias
    MyType: TypeAlias = str


if typing.TYPE_CHECKING:
    # Lines 28-30 should be excluded
    from typing import Protocol
    MyProtocol = Protocol


if types.TYPE_CHECKING:
    # Lines 33-35 should be excluded
    from typing import ClassVar
    MyClassVar = ClassVar


def another_function():
    """This should also be covered."""
    if __name__ == "__main__":
        # Lines 42-43 should be excluded (nested in function)
        return "main"

    if TYPE_CHECKING:
        # Lines 46-47 should be excluded (nested in function)
        x: int

    return "not main"


class MyClass:
    """Test class with excluded blocks."""

    if TYPE_CHECKING:
        # Lines 56-58 should be excluded (inside class)
        from typing import Self
        instance: Self

    def method(self):
        """Method that should be covered."""
        if typing.TYPE_CHECKING:
            # Lines 63-64 should be excluded (nested in method)
            y: str
        return "method"
