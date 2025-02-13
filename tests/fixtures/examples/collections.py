#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def nested_list(x: list[list[str]]):
    for e in x:
        for i in e:
            print(i)


def nested_no_param(x: list[set]):
    for e in x:
        for i in e:
            print(i)


def list_union(x: list[int | str]):
    for e in x:
        print(e)


def check_tuple(x: tuple[int, str]):
    if x[0] == 5:
        print("foo")


def untyped_tuple(x: tuple):
    if len(x) == 3:
        print("foo")


def untyped_list(x):
    if isinstance(x, list):
        print("foo")


def dict_str_int(dic: dict[str, int]):
    for x, y in dic.items():
        print(f"{x}: {y+1}")
