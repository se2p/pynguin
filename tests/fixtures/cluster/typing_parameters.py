#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.cluster.complex_dependency import SomeOtherType
from tests.fixtures.cluster.complex_dependency import YetAnotherType
from tests.fixtures.cluster.dependency import SomeArgumentType


def method_with_union(x: int | SomeArgumentType) -> None:
    print(x)
    pass


def method_with_other(x: tuple[SomeOtherType, YetAnotherType]) -> None:
    pass


def method_with_optional(x: int | None) -> None:
    pass
