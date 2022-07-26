#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

from pynguin.testcase.execution import ExecutedInstruction


def test_instruction_equal():
    module = "foo"
    code_object_id = 1
    node_id = 1
    opcode = 1
    arg = None
    lineno = 42
    offset = 42
    instr1 = ExecutedInstruction(
        module, code_object_id, node_id, opcode, arg, lineno, offset
    )
    instr2 = ExecutedInstruction(
        module, code_object_id, node_id, opcode, arg, lineno, offset
    )

    assert instr1 == instr2
