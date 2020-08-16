#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib

from pynguin.utils.utils import get_members_from_module


def test_get_members_from_module():
    module = importlib.import_module("tests.fixtures.examples.triangle")
    members = get_members_from_module(module)
    assert len(members) == 1
    assert members[0][0] == "triangle"
