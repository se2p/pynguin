#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from ordered_set import OrderedSet

from pynguin.testcase.execution import FileStatementData


def test_visit_statement():
    file_tracker = FileStatementData("foo.py")
    file_tracker.statements = OrderedSet({0, 1, 2})

    file_tracker.visit_statement(0, 0)
    file_tracker.visit_statement(0, 1)
    file_tracker.visit_statement(1, 1)

    assert file_tracker.visited_statements[0] == 2
    assert file_tracker.visited_statements[1] == 1
    assert 2 not in file_tracker.visited_statements
    assert file_tracker.code_objects == {0, 1}


def test_track_statement():
    file_tracker = FileStatementData("foo.py")
    file_tracker.track_statement(0)
    file_tracker.track_statement(0)
    file_tracker.track_statement(1)
    assert file_tracker.statements == {0, 1}
