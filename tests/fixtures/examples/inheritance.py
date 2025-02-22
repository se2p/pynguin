#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from abc import ABC
from abc import abstractmethod


class Foo(ABC):
    @abstractmethod
    def foo(self):
        pass

    def bar(self):
        print("bar")


class Bar(Foo):
    def __init__(self):
        pass

    def foo(self):
        print("sub_bar")
