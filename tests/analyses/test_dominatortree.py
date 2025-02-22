#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import sys

from bytecode import Bytecode

from pynguin.analyses.controlflow import CFG
from pynguin.analyses.controlflow import DominatorTree
from tests.fixtures.programgraph.samples import for_loop


def test_integration_post_dominator_tree(conditional_jump_example_bytecode):
    control_flow_graph = CFG.from_bytecode(conditional_jump_example_bytecode)
    post_dominator_tree = DominatorTree.compute_post_dominator_tree(control_flow_graph)
    dot_representation = post_dominator_tree.dot
    graph = """strict digraph  {
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"ProgramGraphNode(2)
LOAD_CONST 'no'";
"ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode";
"ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode";
"ProgramGraphNode(-1)";
"ProgramGraphNode(9223372036854775807)" -> "ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "ProgramGraphNode(2)
LOAD_CONST 'no'";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode";
"ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode" -> "ProgramGraphNode(-1)";
}"""
    assert bytes(dot_representation, "utf-8").decode("unicode_escape") == bytes(
        graph, "utf-8"
    ).decode("unicode_escape")
    assert post_dominator_tree.entry_node.index == sys.maxsize


def test_integration(small_control_flow_graph):
    post_dominator_tree = DominatorTree.compute_post_dominator_tree(small_control_flow_graph)
    dot_representation = post_dominator_tree.dot
    graph = """strict digraph  {
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(2)";
"ProgramGraphNode(4)";
"ProgramGraphNode(3)";
"ProgramGraphNode(5)";
"ProgramGraphNode(6)";
"ProgramGraphNode(0)";
"ProgramGraphNode(9223372036854775807)" -> "ProgramGraphNode(2)";
"ProgramGraphNode(2)" -> "ProgramGraphNode(4)";
"ProgramGraphNode(2)" -> "ProgramGraphNode(3)";
"ProgramGraphNode(2)" -> "ProgramGraphNode(5)";
"ProgramGraphNode(5)" -> "ProgramGraphNode(6)";
"ProgramGraphNode(6)" -> "ProgramGraphNode(0)";
}"""
    assert dot_representation == graph
    assert post_dominator_tree.entry_node.index == sys.maxsize


def test_integration_post_domination(larger_control_flow_graph):
    post_dominator_tree = DominatorTree.compute_post_dominator_tree(larger_control_flow_graph)
    node = next(n for n in larger_control_flow_graph.nodes if n.index == 110)
    successors = post_dominator_tree.get_transitive_successors(node)
    successor_indices = {n.index for n in successors}
    expected_indices = {
        -sys.maxsize,
        1,
        2,
        3,
        5,
        100,
        120,
        130,
        140,
        150,
        160,
        170,
        180,
        190,
        200,
        210,
    }
    assert successor_indices == expected_indices


def test_integration_dominator_tree():
    for_loop_cfg = CFG.from_bytecode(Bytecode.from_code(for_loop.__code__))
    dom_tree = DominatorTree.compute(for_loop_cfg)
    # Every node of the cfg should be in the dominator tree
    assert for_loop_cfg.nodes == dom_tree.nodes
