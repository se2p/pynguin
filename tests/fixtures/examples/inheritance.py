#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from abc import ABC, abstractmethod


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
