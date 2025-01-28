#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
class SimpleSample:
    def __init__(self, foo: str, bar: int):
        self._foo: str = foo
        self._bar: int = bar


class EqualsSample(SimpleSample):
    def __eq__(self, other) -> bool:
        return (
            isinstance(other, EqualsSample)
            and self._foo == other._foo
            and self._bar == other._bar
        )

    def __hash__(self):
        return hash((self._foo, self._bar))


class ComplexSample:
    def __init__(self, simple: EqualsSample):
        self._simple: EqualsSample = simple
