#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
class Foo:
    def __init__(self):
        self.a = 13

    def foo(self):
        pass

    def bar(self):
        pass


class Bar(Foo):
    def __init__(self):
        super().__init__()
        self.a = 42
        self.b = "test"

    def foo(self):
        pass

    def bar(self):
        pass

    def foobar(self):
        pass


class Baz:
    def bar(self):
        pass

    def a(self):
        pass


class E:
    e = 42


class F:
    f = 42


class G(E, F):
    e = 30
    f = 40
    g = 50
