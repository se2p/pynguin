#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from pynguin.analyses.module import parse_module


def test_parse_module():
    module_name = "tests.fixtures.cluster.no_dependencies"
    parse_result = parse_module(module_name)
    assert parse_result.module.__name__ == module_name
    assert parse_result.module_name == module_name
    assert parse_result.syntax_tree is not None


def test_parse_c_module():
    module_name = "jellyfish.cjellyfish"
    parse_result = parse_module(module_name)
    assert parse_result.module.__name__ == module_name
    assert parse_result.module_name == module_name
    assert parse_result.syntax_tree is None
