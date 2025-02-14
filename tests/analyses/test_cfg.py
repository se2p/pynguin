#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from bytecode import Bytecode

from pynguin.analyses.controlflow import CFG
from tests.fixtures.programgraph.whileloop import Foo
from tests.fixtures.programgraph.yield_fun import yield_fun


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
RETURN_VALUE";
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
RETURN_VALUE";
"ProgramGraphNode(2)
LOAD_CONST 'no'" -> "ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)" -> "ProgramGraphNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE ProgramGraphNode";
}"""
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
RETURN_VALUE";
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
RETURN_VALUE" -> "ProgramGraphNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD ProgramGraphNode";
"ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "ProgramGraphNode(2)
LOAD_CONST 'no'";
"ProgramGraphNode(9223372036854775807)" -> "ProgramGraphNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
}"""
    assert reversed_cfg.cyclomatic_complexity == 2
    assert cfg.diameter == 6
    assert cfg.entry_node.is_artificial
    assert len(cfg.exit_nodes) == 1
    assert bytes(dot_representation, "utf-8").decode("unicode_escape") == bytes(
        graph, "utf-8"
    ).decode("unicode_escape")


def control_flow_labelling(foo):  # pragma: no cover
    if foo:
        print("a")  # noqa: T201
    elif foo == 42:
        print("bar")  # noqa: T201
    for f in foo:
        print(f)  # noqa: T201
    if not foo:
        print("foo")  # noqa: T201


@pytest.mark.parametrize(
    "expected",
    [
        pytest.param(
            """strict digraph  {
"ProgramGraphNode(0)
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE ProgramGraphNode";
"ProgramGraphNode(1)
LOAD_GLOBAL 'print'
LOAD_CONST 'a'
CALL_FUNCTION 1
POP_TOP
JUMP_FORWARD ProgramGraphNode";
"ProgramGraphNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE ProgramGraphNode";
"ProgramGraphNode(3)
LOAD_GLOBAL 'print'
LOAD_CONST 'bar'
CALL_FUNCTION 1
POP_TOP";
"ProgramGraphNode(4)
LOAD_FAST 'foo'
GET_ITER";
"ProgramGraphNode(5)
FOR_ITER ProgramGraphNode";
"ProgramGraphNode(6)
STORE_FAST 'f'
LOAD_GLOBAL 'print'
LOAD_FAST 'f'
CALL_FUNCTION 1
POP_TOP
JUMP_ABSOLUTE ProgramGraphNode";
"ProgramGraphNode(7)
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE ProgramGraphNode";
"ProgramGraphNode(8)
LOAD_GLOBAL 'print'
LOAD_CONST 'foo'
CALL_FUNCTION 1
POP_TOP
LOAD_CONST None
RETURN_VALUE";
"ProgramGraphNode(9)
LOAD_CONST None
RETURN_VALUE";
"ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)";
"ProgramGraphNode(0)
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE ProgramGraphNode" -> "ProgramGraphNode(1)
LOAD_GLOBAL 'print'
LOAD_CONST 'a'
CALL_FUNCTION 1
POP_TOP
JUMP_FORWARD ProgramGraphNode"  [branch_value=True, label=True];
"ProgramGraphNode(0)
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE ProgramGraphNode" -> "ProgramGraphNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE ProgramGraphNode"  [branch_value=False, label=False];
"ProgramGraphNode(1)
LOAD_GLOBAL 'print'
LOAD_CONST 'a'
CALL_FUNCTION 1
POP_TOP
JUMP_FORWARD ProgramGraphNode" -> "ProgramGraphNode(4)
LOAD_FAST 'foo'
GET_ITER";
"ProgramGraphNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE ProgramGraphNode" -> "ProgramGraphNode(3)
LOAD_GLOBAL 'print'
LOAD_CONST 'bar'
CALL_FUNCTION 1
POP_TOP"  [branch_value=True, label=True];
"ProgramGraphNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE ProgramGraphNode" -> "ProgramGraphNode(4)
LOAD_FAST 'foo'
GET_ITER"  [branch_value=False, label=False];
"ProgramGraphNode(3)
LOAD_GLOBAL 'print'
LOAD_CONST 'bar'
CALL_FUNCTION 1
POP_TOP" -> "ProgramGraphNode(4)
LOAD_FAST 'foo'
GET_ITER";
"ProgramGraphNode(4)
LOAD_FAST 'foo'
GET_ITER" -> "ProgramGraphNode(5)
FOR_ITER ProgramGraphNode";
"ProgramGraphNode(5)
FOR_ITER ProgramGraphNode" -> "ProgramGraphNode(6)
STORE_FAST 'f'
LOAD_GLOBAL 'print'
LOAD_FAST 'f'
CALL_FUNCTION 1
POP_TOP
JUMP_ABSOLUTE ProgramGraphNode"  [branch_value=True, label=True];
"ProgramGraphNode(5)
FOR_ITER ProgramGraphNode" -> "ProgramGraphNode(7)
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE ProgramGraphNode"  [branch_value=False, label=False];
"ProgramGraphNode(6)
STORE_FAST 'f'
LOAD_GLOBAL 'print'
LOAD_FAST 'f'
CALL_FUNCTION 1
POP_TOP
JUMP_ABSOLUTE ProgramGraphNode" -> "ProgramGraphNode(5)
FOR_ITER ProgramGraphNode";
"ProgramGraphNode(7)
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE ProgramGraphNode" -> "ProgramGraphNode(9)
LOAD_CONST None
RETURN_VALUE"  [branch_value=True, label=True];
"ProgramGraphNode(7)
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE ProgramGraphNode" -> "ProgramGraphNode(8)
LOAD_GLOBAL 'print'
LOAD_CONST 'foo'
CALL_FUNCTION 1
POP_TOP
LOAD_CONST None
RETURN_VALUE"  [branch_value=False, label=False];
"ProgramGraphNode(8)
LOAD_GLOBAL 'print'
LOAD_CONST 'foo'
CALL_FUNCTION 1
POP_TOP
LOAD_CONST None
RETURN_VALUE" -> "ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(9)
LOAD_CONST None
RETURN_VALUE" -> "ProgramGraphNode(9223372036854775807)";
"ProgramGraphNode(-1)" -> "ProgramGraphNode(0)
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE ProgramGraphNode";
}""",
            id="Python 3.10+, extract return None into separate node",
        ),
    ],
)
def test_all_control_flow(expected):
    cfg = CFG.from_bytecode(Bytecode.from_code(control_flow_labelling.__code__))
    assert bytes(cfg.dot, "utf-8").decode("unicode_escape") == bytes(expected, "utf-8").decode(
        "unicode_escape"
    )


def test_integration_copy_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    copied_cfg = cfg.copy()
    assert copied_cfg.dot == cfg.dot


def test_integration_no_exit():
    with pytest.raises(AssertionError):
        CFG.from_bytecode(Bytecode.from_code(Foo.receive.__code__))


def test_cfg_from_yield():
    cfg = CFG.from_bytecode(Bytecode.from_code(yield_fun.__code__))
    assert cfg.entry_node is not None
    assert cfg.exit_nodes is not None

    predecessors = list(map(cfg.get_predecessors, cfg.exit_nodes))
    empty_predecessors = list(filter(lambda x: len(x) == 0, predecessors))
    assert len(empty_predecessors) == 0
