# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
import sys
from unittest.mock import MagicMock

import pytest

import pynguin.analyses.controlflow.cfg as cfg
import pynguin.analyses.controlflow.postdominatortree as pdt


@pytest.fixture
def node() -> pdt.PostDominatorTreeNode:
    return pdt.PostDominatorTreeNode(
        index=42, cfg_node=MagicMock(cfg.CFGNode), incoming_edges=[], outgoing_edges=[],
    )


def test_node_cfg_node(node):
    assert isinstance(node.cfg_node, cfg.CFGNode)


def test_node_equals_other(node):
    assert not node.__eq__("foo")


def test_node_equals_self(node):
    assert node.__eq__(node)


def test_node_equals_other_node(node):
    other_node = pdt.PostDominatorTreeNode(
        index=42, cfg_node=MagicMock(cfg.CFGNode), incoming_edges=[], outgoing_edges=[]
    )
    assert node.__eq__(other_node)


def test_integration_post_dominator_tree(conditional_jump_example_bytecode):
    control_flow_graph = cfg.CFG.from_bytecode(conditional_jump_example_bytecode)
    post_dominator_tree = pdt.PostDominatorTree.compute(control_flow_graph)
    assert post_dominator_tree.entry_node.index == sys.maxsize
    assert len(post_dominator_tree.edges) == 4
    assert len(post_dominator_tree.nodes) == 5


def test_integration(small_control_flow_graph):
    post_dominator_tree = pdt.PostDominatorTree.compute(small_control_flow_graph)
    assert post_dominator_tree.entry_node.index == sys.maxsize
    assert len(post_dominator_tree.edges) == 6
    assert len(post_dominator_tree.nodes) == 7
