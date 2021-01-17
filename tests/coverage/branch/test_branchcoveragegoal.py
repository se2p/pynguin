#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

from pynguin.coverage.branch.branchcoveragegoal import Branch, BranchCoverageGoal


@pytest.fixture
def branch_coverage_goal():
    return BranchCoverageGoal(
        value=True,
        module_name="test",
        function_name="foo",
    )


def test_branch_coverage_goal():
    branch = MagicMock(Branch)
    goal = BranchCoverageGoal(
        branch=branch,
        value=True,
        module_name="test",
        class_name="BranchCoverageGoal",
        function_name="test_branch_coverage_goal",
    )
    assert goal.branch == branch
    assert goal.value
    assert goal.module_name == "test"
    assert goal.class_name == "BranchCoverageGoal"
    assert goal.function_name == "test_branch_coverage_goal"


def test_hash(branch_coverage_goal):
    assert branch_coverage_goal.__hash__() != 0


def test_eq_same(branch_coverage_goal):
    assert branch_coverage_goal.__eq__(branch_coverage_goal)


def test_eq_other_type(branch_coverage_goal):
    assert not branch_coverage_goal.__eq__(MagicMock())


def test_eq_other(branch_coverage_goal):
    other = BranchCoverageGoal(value=True, module_name="test", function_name="foo")
    assert branch_coverage_goal.__eq__(other)


def test_get_distance(branch_coverage_goal, mocker):
    mock = mocker.patch(
        "pynguin.coverage.branch.branchcoveragegoal.cfd"
        ".calculate_control_flow_distance",
        return_value=42,
    )
    distance = branch_coverage_goal.get_distance(MagicMock())
    assert distance == 42
    mock.assert_called_once()
