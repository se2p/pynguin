#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

from bytecode import Bytecode

from pynguin.instrumentation.controlflow import CFG
from pynguin.instrumentation.controlflow import ArtificialNode
from pynguin.instrumentation.controlflow import BasicBlockNode
from pynguin.instrumentation.controlflow import DominatorTree
from tests.fixtures.programgraph.samples import for_loop
from tests.utils.version import only_3_10


@only_3_10
def test_integration_post_dominator_tree(conditional_jump_example_bytecode):
    control_flow_graph = CFG.from_bytecode(conditional_jump_example_bytecode)
    post_dominator_tree = DominatorTree.compute_post_dominator_tree(control_flow_graph)
    dot_representation = post_dominator_tree.dot
    graph = """strict digraph  {
"ArtificialNode(EXIT)";
"BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_CONST 'no'";
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)" -> "BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "BasicBlockNode(2)
LOAD_CONST 'no'";
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode" -> "ArtificialNode(ENTRY)";
}"""
    assert bytes(dot_representation, "utf-8").decode("unicode_escape") == bytes(
        graph, "utf-8"
    ).decode("unicode_escape")
    assert isinstance(post_dominator_tree.entry_node, ArtificialNode)


def test_integration(small_control_flow_graph):
    post_dominator_tree = DominatorTree.compute_post_dominator_tree(small_control_flow_graph)
    dot_representation = post_dominator_tree.dot
    graph = """strict digraph  {
"ArtificialNode(EXIT)";
"BasicBlockNode(2)
";
"BasicBlockNode(3)
";
"BasicBlockNode(4)
";
"BasicBlockNode(5)
";
"BasicBlockNode(6)
";
"BasicBlockNode(0)
";
"ArtificialNode(EXIT)" -> "BasicBlockNode(2)
";
"BasicBlockNode(2)
" -> "BasicBlockNode(3)
";
"BasicBlockNode(2)
" -> "BasicBlockNode(4)
";
"BasicBlockNode(2)
" -> "BasicBlockNode(5)
";
"BasicBlockNode(5)
" -> "BasicBlockNode(6)
";
"BasicBlockNode(6)
" -> "BasicBlockNode(0)
";
}"""
    assert dot_representation == graph
    assert post_dominator_tree.entry_node == ArtificialNode.EXIT


def test_integration_post_domination(larger_control_flow_graph):
    post_dominator_tree = DominatorTree.compute_post_dominator_tree(larger_control_flow_graph)
    node = next(
        n
        for n in larger_control_flow_graph.nodes
        if isinstance(n, BasicBlockNode) and n.index == 110
    )
    successors = post_dominator_tree.get_transitive_successors(node)
    successor_indices = {n if isinstance(n, ArtificialNode) else n.index for n in successors}
    expected_indices = {
        ArtificialNode.ENTRY,
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
