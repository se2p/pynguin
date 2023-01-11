#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import typing

from typing import Union

def typed_dummy(a: int, b: float, c) -> str: ...
def union_dummy(a: Union[int, float], b: Union[int, float]) -> Union[int, float]: ...
def return_tuple() -> tuple[int, int]: ...

class TypedDummy:
    def __init__(self, a: typing.Any) -> None: ...
    def get_a(self) -> typing.Any: ...
