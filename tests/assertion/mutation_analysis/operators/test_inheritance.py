#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.operators.inheritance import (
    HidingVariableDeletion,
)
from pynguin.assertion.mutation_analysis.operators.inheritance import (
    OverriddenMethodCallingPositionChange,
)
from pynguin.assertion.mutation_analysis.operators.inheritance import (
    OverridingMethodDeletion,
)
from pynguin.assertion.mutation_analysis.operators.inheritance import (
    SuperCallingDeletion,
)
from pynguin.assertion.mutation_analysis.operators.inheritance import SuperCallingInsert
from tests.testutils import assert_mutation


def test_hiding_variable_deletion():
    assert_mutation(
        HidingVariableDeletion,
        inspect.cleandoc(
            """
            class Foo:
                x = 1
            class Bar(Foo):
                x = 2
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    x = 1
                class Bar(Foo):
                    pass
                """
            ): ("mutate_Assign", ast.Assign, ast.Pass),
        },
    )


def test_hiding_variable_in_2_elements_tuple_deletion():
    assert_mutation(
        HidingVariableDeletion,
        inspect.cleandoc(
            """
            class Foo:
                x = 1
            class Baz(Foo):
                x, y = 2, 3
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    x = 1
                class Baz(Foo):
                    y = 3
                """
            ): ("mutate_Assign", ast.Assign, ast.Assign),
        },
    )


def test_hiding_variable_in_3_elements_tuple_deletion():
    assert_mutation(
        HidingVariableDeletion,
        inspect.cleandoc(
            """
            class Foo:
                x = 1
            class Baz(Foo):
                x, y, z = 2, 3, 4
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    x = 1
                class Baz(Foo):
                    y, z = 3, 4
                """
            ): ("mutate_Assign", ast.Assign, ast.Assign),
        },
    )


def test_hiding_tuple_deletion():
    assert_mutation(
        HidingVariableDeletion,
        inspect.cleandoc(
            """
            class Foo:
                x, y = 1, 2
            class Baz(Foo):
                x, y = 3, 4
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    x, y = 1, 2
                class Baz(Foo):
                    pass
                """
            ): ("mutate_Assign", ast.Assign, ast.Pass),
        },
    )


def test_super_call_position_change_from_first_to_last():
    assert_mutation(
        OverriddenMethodCallingPositionChange,
        inspect.cleandoc(
            """
            class Foo:
                def baz(self, x: int):
                    pass
            class Bar(Foo):
                def baz(self, x: int):
                    super().baz(x)
                    pass
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    def baz(self, x: int):
                        pass
                class Bar(Foo):
                    def baz(self, x: int):
                        pass
                        super().baz(x)
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.FunctionDef),
        },
    )


def test_super_call_position_change_from_last_to_first():
    assert_mutation(
        OverriddenMethodCallingPositionChange,
        inspect.cleandoc(
            """
            class Foo:
                def baz(self, x: int):
                    pass
            class Bar(Foo):
                def baz(self, x: int):
                    pass
                    super().baz(x)
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    def baz(self, x: int):
                        pass
                class Bar(Foo):
                    def baz(self, x: int):
                        super().baz(x)
                        pass
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.FunctionDef),
        },
    )


def test_super_call_position_ignore_when_only_one_statement():
    assert_mutation(
        OverriddenMethodCallingPositionChange,
        inspect.cleandoc(
            """
            class Foo:
                def baz(self, x: int):
                    pass
            class Bar(Foo):
                def baz(self, x: int):
                    super().baz(x)
            """
        ),
        {},
    )


def test_overriding_method_deletion():
    assert_mutation(
        OverridingMethodDeletion,
        inspect.cleandoc(
            """
            class Foo:
                def baz(self, x: int):
                    pass
            class Bar(Foo):
                def baz(self, x: int):
                    pass
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    def baz(self, x: int):
                        pass
                class Bar(Foo):
                    pass
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.Pass),
        },
    )


def test_overriding_method_deletion_in_inner_class():
    assert_mutation(
        OverridingMethodDeletion,
        inspect.cleandoc(
            """
            class Outer:
                class Foo:
                    def baz(self, x: int):
                        pass
                class Bar(Foo):
                    def baz(self, x: int):
                        pass
            """
        ),
        {
            inspect.cleandoc(
                """
                class Outer:
                    class Foo:
                        def baz(self, x: int):
                            pass
                    class Bar(Foo):
                        pass
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.Pass),
        },
    )


def test_overriding_method_deletion_when_base_class_in_another_module():
    assert_mutation(
        OverridingMethodDeletion,
        inspect.cleandoc(
            """
            from ast import NodeTransformer

            class Foo(NodeTransformer):
                def visit(self, node):
                    pass
            """
        ),
        {
            inspect.cleandoc(
                """
                from ast import NodeTransformer

                class Foo(NodeTransformer):
                    pass
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.Pass),
        },
    )


def test_super_call_deletion():
    assert_mutation(
        SuperCallingDeletion,
        inspect.cleandoc(
            """
            class Foo:
                def baz(self, x: int):
                    pass
            class Bar(Foo):
                def baz(self, x: int):
                    super().baz(x)
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    def baz(self, x: int):
                        pass
                class Bar(Foo):
                    def baz(self, x: int):
                        pass
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.FunctionDef),
        },
    )


def test_super_call_insertion():
    assert_mutation(
        SuperCallingInsert,
        inspect.cleandoc(
            """
            class Foo:
                def baz(self, x: int):
                    pass
            class Bar(Foo):
                def baz(self, x: int):
                    pass
            """
        ),
        {
            inspect.cleandoc(
                """
                class Foo:
                    def baz(self, x: int):
                        pass
                class Bar(Foo):
                    def baz(self, x: int):
                        super().baz(x)
                        pass
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.FunctionDef),
        },
    )
