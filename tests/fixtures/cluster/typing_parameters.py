#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Optional, Tuple, Union

from tests.fixtures.cluster.complex_dependency import SomeOtherType, YetAnotherType
from tests.fixtures.cluster.dependency import SomeArgumentType


def method_with_union(x: Union[int, SomeArgumentType]) -> None:
    print(x)
    pass


def method_with_other(x: Tuple[SomeOtherType, YetAnotherType]) -> None:
    pass


def method_with_optional(x: Optional[int]) -> None:
    pass
