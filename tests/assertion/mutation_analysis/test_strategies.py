#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast

from pynguin.assertion.mutation_analysis.operators import ArithmeticOperatorDeletion
from pynguin.assertion.mutation_analysis.operators import AssignmentOperatorReplacement
from pynguin.assertion.mutation_analysis.operators import ConstantReplacement
from pynguin.assertion.mutation_analysis.operators.base import Mutation
from pynguin.assertion.mutation_analysis.strategies import BetweenOperatorsHOMStrategy
from pynguin.assertion.mutation_analysis.strategies import EachChoiceHOMStrategy
from pynguin.assertion.mutation_analysis.strategies import FirstToLastHOMStrategy
from pynguin.assertion.mutation_analysis.strategies import RandomHOMStrategy
from pynguin.utils.randomness import RNG
from tests.testutils import create_aor_mutation_on_substraction


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
    node = ast.Sub(children=[])

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
    child_node = ast.Sub(children=[])
    node = ast.UnaryOp(children=[child_node])

    mutations = [
        create_aor_mutation_on_substraction(child_node),
        Mutation(
            node=node,
            replacement_node=ast.Name(id="foo", children=[]),
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
            node=ast.Sub(children=[]),
            replacement_node=ast.Add(children=[]),
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
            node=ast.Sub(children=[]),
            replacement_node=ast.Add(children=[]),
            operator=AssignmentOperatorReplacement,
            visitor_name="mutate_Sub",
        ),
        Mutation(
            node=ast.Constant(value=1, children=[]),
            replacement_node=ast.Constant(value=2, children=[]),
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
