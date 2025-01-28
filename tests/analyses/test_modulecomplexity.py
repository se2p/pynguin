#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Analyses for the module complexity.

The implementation of this module contains some code adopted from the ``mccabe``
library (https://github.com/PyCQA/mccabe), which was released by Florent Xicluna,
Tarek Ziade, and Ned Batchelder under Expad License.

Original copyright notice:
Copyright © <year> Ned Batchelder
Copyright © 2011-2013 Tarek Ziade <tarek@ziade.org>
Copyright © 2013 Florent Xicluna <florent.xicluna@gmail.com>

Licensed under the terms of the Expat License

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation files
(the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import ast

import pytest

from pynguin.analyses.modulecomplexity import mccabe_complexity


_expr_as_statement = """
def f():
    0xF00D
"""

_sequential = """
def f(n):
    k = n + 4
    s = k + n
    return s
"""

_sequential_unencapsulated = """
k = 2 + 4
s = k + 3
"""

_if_elif_else_dead_path = """
def f(n):
    if n > 3:
        return "bigger than three"
    elif n > 4:
        return "is never executed"
    else:
        return "smaller than or equal to three"
"""

_for_loop = """
def f():
    for i in range(10):
        print(i)
"""

_for_else = """
def f(my_list):
    for i in my_list:
        print(i)
    else:
        print(None)
"""

_recursive = """
def f(n):
    if n > 4:
        return f(n - 1)
    else:
        return n
"""

_nested_functions = """
def a():
    def b():
        def c():
            pass
        c()
    b()
"""

_try_else = """
try:
    print(1)
except TypeA:
    print(2)
except TypeB:
    print(3)
else:
    print(4)
"""

_async_keywords = """
async def foo_bar(a, b, c):
    await whatever(a, b, c)
    if await b:
        pass

    async with c:
        pass

    async for x in a:
        pass
"""

_annotated_assign = """
def f():
    x: Any = None
"""


@pytest.mark.parametrize(
    "code, expected_complexity",
    [
        pytest.param("def f(): pass", 1, id="trivial"),
        pytest.param(_expr_as_statement, 1, id="expression-as-statement"),
        pytest.param(_sequential, 1, id="sequential"),
        pytest.param(_sequential_unencapsulated, 0, id="sequential-unencapsulated"),
        pytest.param(_if_elif_else_dead_path, 3, id="if-elif-else-dead-path"),
        pytest.param(_for_loop, 2, id="for-loop"),
        pytest.param(_for_else, 2, id="for-else"),
        pytest.param(_recursive, 2, id="recursive"),
        pytest.param(_nested_functions, 3, id="nested-functions"),
        pytest.param(_try_else, 4, id="try-else"),
        pytest.param(_async_keywords, 3, id="async-keywords"),
        pytest.param(_annotated_assign, 1, id="annotated-assign"),
    ],
)
def test_mccabe_complexity(code: str, expected_complexity: int):
    tree = ast.parse(code)
    complexity = mccabe_complexity(tree)
    assert complexity == expected_complexity
