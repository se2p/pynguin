#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

class Foo:  # pynguin: no cover
    def foo(self):
        return 42

class Bar:
    def bar(self):  # pragma: no cover
        return 84

class Baz:
    def baz(self):
        return 24
