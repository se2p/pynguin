#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast

from pynguin.assertion.mutation_analysis.operators import (
    ArithmeticOperatorDeletion,
    AssignmentOperatorReplacement,
    ConstantReplacement,
)
from pynguin.assertion.mutation_analysis.operators.base import Mutation
from pynguin.assertion.mutation_analysis.strategies import (
    BetweenOperatorsHOMStrategy,
    EachChoiceHOMStrategy,
    FirstToLastHOMStrategy,
    RandomHOMStrategy,
)
from pynguin.utils.randomness import RNG
from tests.testutils import create_aor_mutation_on_substraction, with_children


def test_first_to_last_hom_strategy_generation():
    mutations = [
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
    ]

    order = 2

    strategy = FirstToLastHOMStrategy(order)

    mutations_to_apply = list(strategy.generate(mutations))

    assert mutations_to_apply == [
        [mutations[0], mutations[2]],
        [mutations[1]],
    ]


def test_first_to_last_hom_strategy_same_node():
    node = with_children(ast.Sub(), [])

    mutations = [
        create_aor_mutation_on_substraction(node),
        create_aor_mutation_on_substraction(node),
    ]

    order = 2

    strategy = FirstToLastHOMStrategy(order)

    mutations_to_apply = list(strategy.generate(mutations))

    assert mutations_to_apply == [
        [mutations[0]],
        [mutations[1]],
    ]


def test_first_to_last_hom_strategy_child_node_generation():
    child_node = with_children(ast.Sub(), [])
    node = with_children(ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=1)), [child_node])

    mutations = [
        create_aor_mutation_on_substraction(child_node),
        Mutation(
            node=node,
            replacement_node=with_children(ast.Name(id="foo"), []),
            operator=ArithmeticOperatorDeletion,
            visitor_name="mutate_UnaryOp",
        ),
    ]

    order = 2

    strategy = FirstToLastHOMStrategy(order)

    mutations_to_apply = list(strategy.generate(mutations))

    assert mutations_to_apply == [
        [mutations[0]],
        [mutations[1]],
    ]


def test_each_choice_hom_strategy_generation():
    mutations = [
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
    ]

    order = 2

    strategy = EachChoiceHOMStrategy(order)

    mutations_to_apply = list(strategy.generate(mutations))

    assert mutations_to_apply == [
        [mutations[0], mutations[1]],
        [mutations[2]],
    ]


def test_between_operators_hom_strategy_generation_if_one_operator():
    mutations = [
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
    ]

    order = 2

    strategy = BetweenOperatorsHOMStrategy(order)

    mutations_to_apply = list(strategy.generate(mutations))

    assert mutations_to_apply == [
        [mutations[0]],
        [mutations[1]],
    ]


def test_between_operators_hom_strategy_generation_if_two_operators():
    mutations = [
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
        Mutation(
            node=with_children(ast.Sub(), []),
            replacement_node=with_children(ast.Add(), []),
            operator=AssignmentOperatorReplacement,
            visitor_name="mutate_Sub",
        ),
    ]

    order = 2

    strategy = BetweenOperatorsHOMStrategy(order)

    mutations_to_apply = list(strategy.generate(mutations))

    assert mutations_to_apply == [
        [mutations[0], mutations[2]],
        [mutations[1], mutations[2]],
    ]


def test_between_operators_hom_strategy_generation_if_three_operators():
    mutations = [
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
        Mutation(
            node=with_children(ast.Sub(), []),
            replacement_node=with_children(ast.Add(), []),
            operator=AssignmentOperatorReplacement,
            visitor_name="mutate_Sub",
        ),
        Mutation(
            node=with_children(ast.Constant(value=1), []),
            replacement_node=with_children(ast.Constant(value=2), []),
            operator=ConstantReplacement,
            visitor_name="mutate_Constant_num",
        ),
    ]

    order = 2

    strategy = BetweenOperatorsHOMStrategy(order)

    mutations_to_apply = list(strategy.generate(mutations))

    assert mutations_to_apply == [
        [mutations[0], mutations[2]],
        [mutations[1], mutations[3]],
    ]


def test_random_hom_strategy_generation():
    mutations = [
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
        create_aor_mutation_on_substraction(),
    ]

    order = 2

    strategy = RandomHOMStrategy(order)

    RNG.seed(42)

    mutations_to_apply = list(strategy.generate(mutations))

    assert mutations_to_apply == [
        [mutations[1], mutations[0]],
        [mutations[2]],
    ]
