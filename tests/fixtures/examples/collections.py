#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import List, Set, Union


def nested_list(x: List[List[str]]):
    for e in x:
        for i in e:
            print(i)


def nested_no_param(x: List[Set]):
    for e in x:
        for i in e:
            print(i)


def list_union(x: List[Union[int, str]]):
    for e in x:
        print(e)
