#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Dict, List, Set, Tuple, Union


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


def check_tuple(x: Tuple[int, str]):
    if x[0] == 5:
        print("foo")


def untyped_tuple(x: Tuple):
    if len(x) == 3:
        print("foo")


def untyped_list(x):
    if isinstance(x, list):
        print("foo")


def dict_str_int(dic: Dict[str, int]):
    for x, y in dic.items():
        print(f"{x}: {y+1}")
