#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

from tests.fixtures.slicer.module_dependency_def import Foo, module_list


def func():
    result = module_list + Foo.get_class_list()
    return result
