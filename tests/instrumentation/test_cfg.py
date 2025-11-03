#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import sys

from opcode import opmap
from unittest.mock import MagicMock

from bytecode import Bytecode
from bytecode.cfg import BasicBlock
from bytecode.instr import Instr

from pynguin.instrumentation.controlflow import CFG
from pynguin.instrumentation.controlflow import ArtificialNode
from pynguin.instrumentation.controlflow import BasicBlockNode
from pynguin.instrumentation.version import add_for_loop_no_yield_nodes
from tests.fixtures.programgraph.whileloop import Foo
from tests.fixtures.programgraph.yield_fun import yield_fun


def test_integration_create_cfg(conditional_jump_example_bytecode):
    cfg = CFG.from_bytecode(add_for_loop_no_yield_nodes(conditional_jump_example_bytecode))
    dot_representation = cfg.dot

    if sys.version_info >= (3, 14):
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
CALL 1
RETURN_VALUE";
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
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
CALL 1
RETURN_VALUE";
"BasicBlockNode(2)
LOAD_CONST 'no'" -> "BasicBlockNode(3)
CALL 1
RETURN_VALUE";
"BasicBlockNode(3)
CALL 1
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode";
}"""

    elif sys.version_info >= (3, 12):
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
CALL 1
RETURN_CONST None";
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
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
CALL 1
RETURN_CONST None";
"BasicBlockNode(2)
LOAD_CONST 'no'" -> "BasicBlockNode(3)
CALL 1
RETURN_CONST None";
"BasicBlockNode(3)
CALL 1
RETURN_CONST None" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_IF_FALSE BasicBlockNode";
}"""
    elif sys.version_info >= (3, 11):
        graph = """strict digraph  {
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_CONST 'no'";
"BasicBlockNode(3)
PRECALL 1
CALL 1
LOAD_CONST None
RETURN_VALUE";
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode" -> "BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode" -> "BasicBlockNode(2)
LOAD_CONST 'no'"  [branch_value=False, label=False];
"BasicBlockNode(1)
LOAD_CONST 'yes'
JUMP_FORWARD BasicBlockNode" -> "BasicBlockNode(3)
PRECALL 1
CALL 1
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(2)
LOAD_CONST 'no'" -> "BasicBlockNode(3)
PRECALL 1
CALL 1
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(3)
PRECALL 1
CALL 1
LOAD_CONST None
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
LOAD_NAME 'print'
LOAD_NAME 'test'
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode";
}"""
    else:
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
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
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


def control_flow_labelling(foo):  # pragma: no cover
    if foo:
        print("a")  # noqa: T201
    elif foo == 42:
        print("bar")  # noqa: T201
    for f in foo:
        print(f)  # noqa: T201
    if not foo:
        print("foo")  # noqa: T201


def test_all_control_flow():
    if sys.version_info >= (3, 14):
        expected = """strict digraph  {
"BasicBlockNode(0)
RESUME 0
LOAD_FAST_BORROW 'foo'
TO_BOOL
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_FAST_BORROW 'foo'
LOAD_SMALL_INT 42
COMPARE_OP EQ_CAST
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(3)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
POP_TOP";
"BasicBlockNode(4)
LOAD_FAST_BORROW 'foo'
GET_ITER";
"BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST_BORROW 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode";
"BasicBlockNode(7)
END_FOR
POP_ITER
LOAD_FAST_BORROW 'foo'
TO_BOOL
POP_JUMP_IF_TRUE BasicBlockNode";
"BasicBlockNode(8)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE";
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
"BasicBlockNode(0)
RESUME 0
LOAD_FAST_BORROW 'foo'
TO_BOOL
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(1)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(0)
RESUME 0
LOAD_FAST_BORROW 'foo'
TO_BOOL
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(2)
LOAD_FAST_BORROW 'foo'
LOAD_SMALL_INT 42
COMPARE_OP EQ_CAST
POP_JUMP_IF_FALSE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(1)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST_BORROW 'foo'
GET_ITER";
"BasicBlockNode(2)
LOAD_FAST_BORROW 'foo'
LOAD_SMALL_INT 42
COMPARE_OP EQ_CAST
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(3)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
POP_TOP"  [branch_value=True, label=True];
"BasicBlockNode(2)
LOAD_FAST_BORROW 'foo'
LOAD_SMALL_INT 42
COMPARE_OP EQ_CAST
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST_BORROW 'foo'
GET_ITER"  [branch_value=False, label=False];
"BasicBlockNode(3)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
POP_TOP" -> "BasicBlockNode(4)
LOAD_FAST_BORROW 'foo'
GET_ITER";
"BasicBlockNode(4)
LOAD_FAST_BORROW 'foo'
GET_ITER" -> "BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(5)
FOR_ITER BasicBlockNode" -> "BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST_BORROW 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(5)
FOR_ITER BasicBlockNode" -> "BasicBlockNode(7)
END_FOR
POP_ITER
LOAD_FAST_BORROW 'foo'
TO_BOOL
POP_JUMP_IF_TRUE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST_BORROW 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode" -> "BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(7)
END_FOR
POP_ITER
LOAD_FAST_BORROW 'foo'
TO_BOOL
POP_JUMP_IF_TRUE BasicBlockNode" -> "BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE"  [branch_value=True, label=True];
"BasicBlockNode(7)
END_FOR
POP_ITER
LOAD_FAST_BORROW 'foo'
TO_BOOL
POP_JUMP_IF_TRUE BasicBlockNode" -> "BasicBlockNode(8)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
LOAD_CONST None
RETURN_VALUE"  [branch_value=False, label=False];
"BasicBlockNode(8)
NOT_TAKEN
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
LOAD_CONST None
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
RESUME 0
LOAD_FAST_BORROW 'foo'
TO_BOOL
POP_JUMP_IF_FALSE BasicBlockNode";
}"""
    elif sys.version_info >= (3, 13):
        expected = """strict digraph  {
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
TO_BOOL
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ_CAST
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
POP_TOP";
"BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode";
"BasicBlockNode(7)
END_FOR
POP_TOP
LOAD_FAST 'foo'
TO_BOOL
POP_JUMP_IF_TRUE BasicBlockNode";
"BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
RETURN_CONST None";
"BasicBlockNode(9)
RETURN_CONST None";
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
TO_BOOL
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
TO_BOOL
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ_CAST
POP_JUMP_IF_FALSE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ_CAST
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
POP_TOP"  [branch_value=True, label=True];
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ_CAST
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER"  [branch_value=False, label=False];
"BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
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
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(5)
FOR_ITER BasicBlockNode" -> "BasicBlockNode(7)
END_FOR
POP_TOP
LOAD_FAST 'foo'
TO_BOOL
POP_JUMP_IF_TRUE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode" -> "BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(7)
END_FOR
POP_TOP
LOAD_FAST 'foo'
TO_BOOL
POP_JUMP_IF_TRUE BasicBlockNode" -> "BasicBlockNode(9)
RETURN_CONST None"  [branch_value=True, label=True];
"BasicBlockNode(7)
END_FOR
POP_TOP
LOAD_FAST 'foo'
TO_BOOL
POP_JUMP_IF_TRUE BasicBlockNode" -> "BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
RETURN_CONST None"  [branch_value=False, label=False];
"BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
RETURN_CONST None" -> "ArtificialNode(EXIT)";
"BasicBlockNode(9)
RETURN_CONST None" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
TO_BOOL
POP_JUMP_IF_FALSE BasicBlockNode";
}"""
    elif sys.version_info >= (3, 12):
        expected = """strict digraph  {
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE BasicBlockNode";
"BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
POP_TOP";
"BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode";
"BasicBlockNode(7)
END_FOR
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE BasicBlockNode";
"BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
RETURN_CONST None";
"BasicBlockNode(9)
RETURN_CONST None";
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
POP_TOP"  [branch_value=True, label=True];
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_IF_FALSE BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER"  [branch_value=False, label=False];
"BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
CALL 1
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
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(5)
FOR_ITER BasicBlockNode" -> "BasicBlockNode(7)
END_FOR
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode" -> "BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(7)
END_FOR
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE BasicBlockNode" -> "BasicBlockNode(9)
RETURN_CONST None"  [branch_value=True, label=True];
"BasicBlockNode(7)
END_FOR
LOAD_FAST 'foo'
POP_JUMP_IF_TRUE BasicBlockNode" -> "BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
RETURN_CONST None"  [branch_value=False, label=False];
"BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
CALL 1
POP_TOP
RETURN_CONST None" -> "ArtificialNode(EXIT)";
"BasicBlockNode(9)
RETURN_CONST None" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
POP_JUMP_IF_FALSE BasicBlockNode";
}"""
    elif sys.version_info >= (3, 11):
        expected = """strict digraph  {
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode";
"BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
PRECALL 1
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode";
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode";
"BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
PRECALL 1
CALL 1
POP_TOP";
"BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
PRECALL 1
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode";
"BasicBlockNode(7)
NOP
LOAD_FAST 'foo'
POP_JUMP_FORWARD_IF_TRUE BasicBlockNode";
"BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
PRECALL 1
CALL 1
POP_TOP
LOAD_CONST None
RETURN_VALUE";
"BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE";
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode" -> "BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
PRECALL 1
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode" -> "BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(1)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'a'
PRECALL 1
CALL 1
POP_TOP
JUMP_FORWARD BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER";
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode" -> "BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
PRECALL 1
CALL 1
POP_TOP"  [branch_value=True, label=True];
"BasicBlockNode(2)
LOAD_FAST 'foo'
LOAD_CONST 42
COMPARE_OP EQ
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode" -> "BasicBlockNode(4)
LOAD_FAST 'foo'
GET_ITER"  [branch_value=False, label=False];
"BasicBlockNode(3)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'bar'
PRECALL 1
CALL 1
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
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
PRECALL 1
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode"  [branch_value=True, label=True];
"BasicBlockNode(5)
FOR_ITER BasicBlockNode" -> "BasicBlockNode(7)
NOP
LOAD_FAST 'foo'
POP_JUMP_FORWARD_IF_TRUE BasicBlockNode"  [branch_value=False, label=False];
"BasicBlockNode(6)
STORE_FAST 'f'
LOAD_GLOBAL (True, 'print')
LOAD_FAST 'f'
PRECALL 1
CALL 1
POP_TOP
JUMP_BACKWARD BasicBlockNode" -> "BasicBlockNode(5)
FOR_ITER BasicBlockNode";
"BasicBlockNode(7)
NOP
LOAD_FAST 'foo'
POP_JUMP_FORWARD_IF_TRUE BasicBlockNode" -> "BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE"  [branch_value=True, label=True];
"BasicBlockNode(7)
NOP
LOAD_FAST 'foo'
POP_JUMP_FORWARD_IF_TRUE BasicBlockNode" -> "BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
PRECALL 1
CALL 1
POP_TOP
LOAD_CONST None
RETURN_VALUE"  [branch_value=False, label=False];
"BasicBlockNode(8)
LOAD_GLOBAL (True, 'print')
LOAD_CONST 'foo'
PRECALL 1
CALL 1
POP_TOP
LOAD_CONST None
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"BasicBlockNode(9)
LOAD_CONST None
RETURN_VALUE" -> "ArtificialNode(EXIT)";
"ArtificialNode(ENTRY)" -> "BasicBlockNode(0)
RESUME 0
LOAD_FAST 'foo'
POP_JUMP_FORWARD_IF_FALSE BasicBlockNode";
}"""
    else:
        expected = """strict digraph  {
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
"ArtificialNode(ENTRY)";
"ArtificialNode(EXIT)";
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
}"""
    cfg = CFG.from_bytecode(
        add_for_loop_no_yield_nodes(Bytecode.from_code(control_flow_labelling.__code__))
    )
    assert bytes(cfg.dot, "utf-8").decode("unicode_escape") == bytes(expected, "utf-8").decode(
        "unicode_escape"
    )


def test_integration_no_exit():
    cfg = CFG.from_bytecode(Bytecode.from_code(Foo.receive.__code__))
    assert cfg.entry_node is ArtificialNode.ENTRY
    assert cfg.exit_nodes == {ArtificialNode.EXIT}

    assert len(cfg.get_successors(ArtificialNode.ENTRY)) == 1
    assert len(cfg.get_predecessors(ArtificialNode.EXIT)) == 1


def test_cfg_from_yield():
    cfg = CFG.from_bytecode(Bytecode.from_code(yield_fun.__code__))
    assert cfg.entry_node is ArtificialNode.ENTRY
    assert cfg.exit_nodes == {ArtificialNode.EXIT}

    predecessors = list(map(cfg.get_predecessors, cfg.exit_nodes))
    empty_predecessors = list(filter(lambda x: len(x) == 0, predecessors))
    assert len(empty_predecessors) == 0


if sys.version_info >= (3, 12):
    yield_instr = Instr(name="YIELD_VALUE", arg=0)
else:
    yield_instr = Instr(name="YIELD_VALUE")


def test_yield_nodes():
    graph = CFG(MagicMock())

    yield_instr.opcode = opmap["YIELD_VALUE"]
    instructions = [yield_instr]
    basic_block = BasicBlock(instructions=instructions)
    node = BasicBlockNode(index=42, basic_block=basic_block)
    graph.add_node(node)

    yield_nodes = CFG._get_yield_nodes(graph)
    assert len(tuple(yield_nodes)) == 1


def test_yield_nodes_2():
    graph = CFG(MagicMock())

    yield_instr.opcode = opmap["YIELD_VALUE"]
    instructions = [yield_instr]
    basic_block = BasicBlock(instructions=instructions)
    node = BasicBlockNode(index=42, basic_block=basic_block)
    graph.add_node(node)

    yield_instr_2 = yield_instr.copy()
    yield_instr_2.opcode = opmap["YIELD_VALUE"]
    instructions_2 = [yield_instr_2]
    basic_block_2 = BasicBlock(instructions=instructions_2)
    node_2 = BasicBlockNode(index=43, basic_block=basic_block_2)
    graph.add_node(node_2)

    yield_nodes = CFG._get_yield_nodes(graph)
    assert len(tuple(yield_nodes)) == 2
