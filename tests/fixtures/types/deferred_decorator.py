#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import functools
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable


def decorate(func: Callable[..., typing.Any]) -> Callable[..., typing.Any]:
    @functools.wraps(func)
    def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        return func(*args, **kwargs)

    return wrapper
