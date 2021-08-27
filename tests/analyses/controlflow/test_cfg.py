#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import sys

from bytecode import Bytecode

from pynguin.analyses.controlflow.cfg import CFG
from tests.fixtures.programgraph.whileloop import Foo


def test_integration_create_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    dot_representation = cfg.dot
    graph = """strict digraph  {
"ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode";
"ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode";
"ProgramGraphNode(2)
LOAD_CONST 'no'";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE ";
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)";
"ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode" -> "ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode"  [branch_value=True, label=True];
"ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode" -> "ProgramGraphNode(2)
LOAD_CONST 'no'"  [branch_value=False, label=False];
"ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode" -> "ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE ";
"ProgramGraphNode(2)
LOAD_CONST 'no'" -> "ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE ";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE " -> "ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)" -> "ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode";
}
"""
    assert cfg.cyclomatic_complexity == 2
    assert cfg.diameter == 6
    assert cfg.entry_node.is_artificial
    assert len(cfg.exit_nodes) == 1
    # Stupid string encoding >:[
    assert bytes(dot_representation, "utf-8").decode("unicode_escape") == bytes(
        graph, "utf-8"
    ).decode("unicode_escape")


def test_integration_reverse_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    reversed_cfg = cfg.reversed()
    dot_representation = reversed_cfg.dot
    graph = """strict digraph  {
"ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode";
"ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode";
"ProgramGraphNode(2)
LOAD_CONST 'no'";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE ";
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)";
"ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode" -> "ProgramGraphNode(-1)";
"ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode" -> "ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode"  [branch_value=True, label=True];
"ProgramGraphNode(2)
LOAD_CONST 'no'" -> "ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode"  [branch_value=False, label=False];
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE " -> "ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE " -> "ProgramGraphNode(2)
LOAD_CONST 'no'";
"ProgramGraphNode(9223372036854775807)" -> "ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE ";
}
"""
    assert reversed_cfg.cyclomatic_complexity == 2
    assert cfg.diameter == 6
    assert cfg.entry_node.is_artificial
    assert len(cfg.exit_nodes) == 1
    assert bytes(dot_representation, "utf-8").decode("unicode_escape") == bytes(graph, "utf-8").decode("unicode_escape")


def control_flow_labelling(foo):
    if foo:
        print("a")
    elif foo == 42:
        print("bar")
    for f in foo:
        print(f)
    if not foo:
        print("foo")


def test_all_control_flow():
    graph = ""
    cfg = CFG.from_bytecode(Bytecode.from_code(control_flow_labelling.__code__))
    print(bytes(cfg.dot, "utf-8").decode("unicode_escape"))
    assert bytes(cfg.dot, "utf-8").decode("unicode_escape") == bytes(graph, "utf-8").decode("unicode_escape")


def test_integration_copy_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    copied_cfg = cfg.copy()
    assert copied_cfg.dot == cfg.dot


def test_integration_while_loop():
    while_loop_cfg = CFG.from_bytecode(Bytecode.from_code(Foo.receive.__code__))
    assert len(while_loop_cfg.nodes) == 3
    assert while_loop_cfg.entry_node.index == -1
    assert while_loop_cfg.exit_nodes.pop().index == sys.maxsize
