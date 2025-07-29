#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from bytecode import Bytecode

from pynguin.instrumentation.controlflow import CFG
from pynguin.instrumentation.controlflow import ArtificialNode
from tests.fixtures.programgraph.whileloop import Foo
from tests.fixtures.programgraph.yield_fun import yield_fun
from tests.utils.version import only_3_10


@only_3_10
def test_integration_create_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    dot_representation = cfg.dot
    graph = """strict digraph  {
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_CONST 'no'";
"BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)";
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(2)
LOAD_CONST 'no'"  [branch_value=False, label=False];
"BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode" -> "BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(2)
LOAD_CONST 'no'" -> "BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode";
}"""
    assert cfg.cyclomatic_complexity == 2
    assert cfg.diameter == 6
    assert isinstance(cfg.entry_node, ArtificialNode)
    assert len(cfg.exit_nodes) == 1
    # Stupid string encoding >:[
    assert bytes(dot_representation, "utf-8").decode("unicode_escape") == bytes(
        graph, "utf-8"
    ).decode("unicode_escape")


@only_3_10
def test_integration_reverse_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    reversed_cfg = cfg.reversed()
    dot_representation = reversed_cfg.dot
    graph = """strict digraph  {
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_CONST 'no'";
"BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
"ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)";
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode" -> "ArtificialNode(ENTRY)";
"BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode" -> "BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(2)
LOAD_CONST 'no'" -> "BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode"  [branch_value=False, label=False];
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
"ArtificialNode(EXIT)" -> "BasicBlockNode(3)
CALL_FUNCTION 1
LOAD_CONST None
RETURN_VALUE";
}"""
    assert reversed_cfg.cyclomatic_complexity == 2
    assert cfg.diameter == 6
    assert isinstance(cfg.entry_node, ArtificialNode)
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


@only_3_10
@pytest.mark.parametrize(
    "expected",
    [
        pytest.param(
            """strict digraph  {
"BasicBlockNode(0)
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
LOAD_GLOBAL 'print'
LOAD_CONST 'a'
CALL_FUNCTION 1
POP_TOP
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(3)
LOAD_GLOBAL 'print'
LOAD_CONST 'bar'
CALL_FUNCTION 1
POP_TOP";
"BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL 'print'
LOAD_FAST 'f'
CALL_FUNCTION 1
POP_TOP
JUMP_ABSOLUTE BasicBlockNode";
"BasicBlockNode(7)
NOP
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE BasicBlockNode";
"BasicBlockNode(8)
LOAD_GLOBAL 'print'
LOAD_CONST 'foo'
CALL_FUNCTION 1
POP_TOP
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE";
"ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)";
"BasicBlockNode(0)
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(1)
LOAD_GLOBAL 'print'
LOAD_CONST 'a'
CALL_FUNCTION 1
POP_TOP
JUMP_FORWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(0)
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(1)
LOAD_GLOBAL 'print'
LOAD_CONST 'a'
CALL_FUNCTION 1
POP_TOP
JUMP_FORWARD BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(3)
LOAD_GLOBAL 'print'
LOAD_CONST 'bar'
CALL_FUNCTION 1
POP_TOP"  [branch_value=True, label=True];
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER"  [branch_value=False, label=False];
"BasicBlockNode(3)
LOAD_GLOBAL 'print'
LOAD_CONST 'bar'
CALL_FUNCTION 1
POP_TOP" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER" -> "BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(5)
FOR_ITER BasicBlockNode" -> "BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL 'print'
LOAD_FAST 'f'
CALL_FUNCTION 1
POP_TOP
JUMP_ABSOLUTE BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(5)
FOR_ITER BasicBlockNode" -> "BasicBlockNode(7)
NOP
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL 'print'
LOAD_FAST 'f'
CALL_FUNCTION 1
POP_TOP
JUMP_ABSOLUTE BasicBlockNode" -> "BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(7)
NOP
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE BasicBlockNode" -> "BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE"  [branch_value=True, label=True];
"BasicBlockNode(7)
NOP
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE BasicBlockNode" -> "BasicBlockNode(8)
LOAD_GLOBAL 'print'
LOAD_CONST 'foo'
CALL_FUNCTION 1
POP_TOP
LOAD_CONST None
RETURN_VALUE"  [branch_value=False, label=False];
"BasicBlockNode(8)
LOAD_GLOBAL 'print'
LOAD_CONST 'foo'
CALL_FUNCTION 1
POP_TOP
LOAD_CONST None
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE BasicBlockNode";
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


@only_3_10
def test_integration_copy_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(conditional_jump_example_bytecode)
    copied_cfg = cfg.copy()
    assert copied_cfg.dot == cfg.dot


def test_integration_no_exit():
    with pytest.raises(AssertionError):
        CFG.from_bytecode(Bytecode.from_code(Foo.receive.__code__))


@only_3_10
def test_cfg_from_yield():
    cfg = CFG.from_bytecode(Bytecode.from_code(yield_fun.__code__))
    assert cfg.entry_node is not None
    assert cfg.exit_nodes is not None

    predecessors = list(map(cfg.get_predecessors, cfg.exit_nodes))
    empty_predecessors = list(filter(lambda x: len(x) == 0, predecessors))
    assert len(empty_predecessors) == 0
