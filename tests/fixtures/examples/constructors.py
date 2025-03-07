#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
class Base:
    def __init__(self):
        pass

    def instance_constructor(self) -> 'Base':
        return Base()

    def instance_constructor_with_args(self, a: int, b: str) -> 'Base':
        return Base()

    @staticmethod
    def static_constructor() -> 'Base':
        return Base()


def external_constructor() -> Base:
    return Base()


class Overload(Base):
    def __init__(self):
        super().__init__()

    def instance_constructor(self) -> 'Overload':
        return Overload()

    @staticmethod
    def static_constructor() -> 'Overload':
        return Overload()


def external_overload_constructor() -> Overload:
    return Overload()


class Derived1(Base):
    def __init__(self):
        super().__init__()


class Derived2(Derived1):
    def __init__(self):
        super().__init__()
