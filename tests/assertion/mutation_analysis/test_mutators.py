#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect
import itertools

import pynguin.assertion.mutation_analysis.mutators as mu
from pynguin.assertion.mutation_analysis.mutators import FirstOrderMutator, HighOrderMutator
from pynguin.assertion.mutation_analysis.operators import (
    ArithmeticOperatorDeletion,
    ArithmeticOperatorReplacement,
    AssignmentOperatorReplacement,
    ConstantReplacement,
    experimental_operators,
    standard_operators,
)
from pynguin.assertion.mutation_analysis.operators.loop import (
    OneIterationLoop,
    ReverseIterationLoop,
    ZeroIterationLoop,
)
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer, create_module
from tests.testutils import assert_mutator_mutation

_LOOP_OPERATORS = {OneIterationLoop, ReverseIterationLoop, ZeroIterationLoop}

_ORDERING_SOURCE = inspect.cleandoc(
    """
    def f(x):
        total = 0
        for i in range(x):
            total = total + 1
        if total > 5:
            return total
        return 0
    """
)


def _build_ordering_module():
    module_ast = ParentNodeTransformer.create_ast(_ORDERING_SOURCE)
    module = create_module(module_ast, "ordering_mutant")
    return module_ast, module


def _fingerprints(mutator):
    """Return a stable, AST-identity-independent description of the mutants."""
    module_ast, module = _build_ordering_module()
    return [
        (mutations[0].operator.__name__, mutations[0].visitor_name, ast.unparse(mutant_ast))
        for mutations, mutant_ast in mutator.mutate(module_ast, module)
    ]


def _operator_sequence(mutator):
    module_ast, module = _build_ordering_module()
    return [mutations[0].operator for mutations, _ in mutator.mutate(module_ast, module)]


def test_first_order_mutator_generation():
    assert_mutator_mutation(
        FirstOrderMutator([
            ArithmeticOperatorReplacement,
            AssignmentOperatorReplacement,
        ]),
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = 0
            z += x + y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = 0
                z -= x + y
                """
            ): {(AssignmentOperatorReplacement, "mutate_Add", ast.Add, ast.Sub)},
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = 0
                z += x - y
                """
            ): {(ArithmeticOperatorReplacement, "mutate_Add", ast.Add, ast.Sub)},
        },
    )


def test_high_order_mutator_generation():
    assert_mutator_mutation(
        HighOrderMutator([
            ArithmeticOperatorReplacement,
            AssignmentOperatorReplacement,
        ]),
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = 0
            z += x + y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = 0
                z -= x - y
                """
            ): {
                (AssignmentOperatorReplacement, "mutate_Add", ast.Add, ast.Sub),
                (ArithmeticOperatorReplacement, "mutate_Add", ast.Add, ast.Sub),
            },
        },
    )


def test_high_order_mutator_generation_with_same_node():
    assert_mutator_mutation(
        HighOrderMutator([
            ArithmeticOperatorDeletion,
            ArithmeticOperatorReplacement,
        ]),
        inspect.cleandoc(
            """
            x = 1
            y = -x
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = x
                """
            ): {
                (ArithmeticOperatorDeletion, "mutate_UnaryOp", ast.UnaryOp, ast.Name),
            },
            inspect.cleandoc(
                """
                x = 1
                y = +x
                """
            ): {
                (ArithmeticOperatorReplacement, "mutate_USub", ast.USub, ast.UAdd),
            },
        },
    )


def test_round_robin_interleaves():
    assert mu._round_robin([[1, 2, 3], [4, 5]]) == [1, 4, 2, 5, 3]


def test_round_robin_empty():
    assert mu._round_robin([]) == []


def test_stratified_counts_below_cap_unchanged():
    assert mu._stratified_counts([2, 3], 100) == [2, 3]


def test_stratified_counts_sums_to_cap():
    sizes = [10, 5, 1]
    counts = mu._stratified_counts(sizes, 8)
    assert sum(counts) == 8
    # Never allocate more mutations than an operator actually has.
    assert all(count <= size for size, count in zip(sizes, counts, strict=True))


def test_default_mutator_preserves_operator_concatenation_order():
    all_operators = [*standard_operators, *experimental_operators]
    sequence = _operator_sequence(FirstOrderMutator(all_operators))
    # With no bound active, operators appear in their concatenated list order:
    # each operator's mutations are contiguous and never re-interleaved.
    first_index = {}
    last_index = {}
    for i, op in enumerate(sequence):
        first_index.setdefault(op, i)
        last_index[op] = i
    present = [op for op in all_operators if op in first_index]
    for earlier, later in itertools.pairwise(present):
        assert last_index[earlier] < first_index[later]


def test_reorder_defers_timeout_prone_operators():
    all_operators = [*standard_operators, *experimental_operators]
    sequence = _operator_sequence(FirstOrderMutator(all_operators, reorder=True))
    loop_positions = [i for i, op in enumerate(sequence) if op in _LOOP_OPERATORS]
    regular_positions = [i for i, op in enumerate(sequence) if op not in _LOOP_OPERATORS]
    assert loop_positions, "fixture should produce loop-operator mutations"
    assert regular_positions
    # Every timeout-prone mutation is scheduled after every regular one.
    assert min(loop_positions) > max(regular_positions)


def test_maximum_mutants_cap_is_honored():
    all_operators = [*standard_operators, *experimental_operators]
    full = len(_fingerprints(FirstOrderMutator(all_operators)))
    cap = max(1, full // 2)
    assert cap < full
    sampled = _fingerprints(
        FirstOrderMutator(all_operators, maximum_mutants=cap, sampling_seed=7, reorder=True)
    )
    assert len(sampled) == cap


def test_sampling_is_deterministic_for_same_seed():
    all_operators = [*standard_operators, *experimental_operators]
    cap = max(1, len(_fingerprints(FirstOrderMutator(all_operators))) // 2)
    first = _fingerprints(
        FirstOrderMutator(all_operators, maximum_mutants=cap, sampling_seed=42, reorder=True)
    )
    second = _fingerprints(
        FirstOrderMutator(all_operators, maximum_mutants=cap, sampling_seed=42, reorder=True)
    )
    assert first == second


def test_maximum_mutants_disabled_keeps_all():
    all_operators = [*standard_operators, *experimental_operators]
    full = _fingerprints(FirstOrderMutator(all_operators))
    disabled = _fingerprints(FirstOrderMutator(all_operators, maximum_mutants=-1))
    assert len(disabled) == len(full)


def test_mutation_count_is_pretruncation_total():
    all_operators = [*standard_operators, *experimental_operators]

    module_ast, module = _build_ordering_module()
    full = FirstOrderMutator(all_operators).mutation_count(module_ast, module)

    capped = FirstOrderMutator(all_operators, maximum_mutants=2, reorder=True)

    module_ast, module = _build_ordering_module()
    assert capped.mutation_count(module_ast, module) == full

    module_ast, module = _build_ordering_module()
    assert sum(1 for _ in capped.mutate(module_ast, module)) == 2


def test_high_order_mutator_generation_with_multiple_visitors():
    assert_mutator_mutation(
        HighOrderMutator([ConstantReplacement]),
        inspect.cleandoc(
            """
            x = 'test'
            """
        ),
        {
            inspect.cleandoc(
                f"""
                x = '{ConstantReplacement.FIRST_CONST_STRING}'
                """
            ): {
                (
                    ConstantReplacement,
                    "mutate_Constant_str",
                    ast.Constant,
                    ast.Constant,
                ),
            },
            inspect.cleandoc(
                """
                x = ''
                """
            ): {
                (
                    ConstantReplacement,
                    "mutate_Constant_str_empty",
                    ast.Constant,
                    ast.Constant,
                ),
            },
        },
    )
