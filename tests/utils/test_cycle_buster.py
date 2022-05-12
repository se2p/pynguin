#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pathlib

from pynguin.utils.cyclicimports import find_cyclic_imports


def test_do_not_create_cyclic_imports():
    # Do not move this test or this breaks.
    root_dir = pathlib.Path(__file__).parents[2]
    # If you break this test, you win a prize :)
    assert find_cyclic_imports(root_dir, ["pynguin", "tests"]) == []
