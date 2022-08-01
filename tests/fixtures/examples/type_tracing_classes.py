#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Simulate a large test cluster.
for _ in range(100):
    exec(
        f"""
class Foo{_}:
    foo_{_} = {_}

    def __init__(self):
        pass


class Bar{_}:
    foo_{_} = {100 - _}

    def __init__(self):
        pass"""
    )
