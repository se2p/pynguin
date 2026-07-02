#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides mutation operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/__init__.py
and integrated in Pynguin.
"""

from pynguin.assertion.mutation_analysis.operators.arithmetic import (
    ArithmeticOperatorDeletion,
    ArithmeticOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator
from pynguin.assertion.mutation_analysis.operators.decorator import DecoratorDeletion
from pynguin.assertion.mutation_analysis.operators.exception import (
    ExceptionHandlerDeletion,
    ExceptionSwallowing,
    ExceptionTypeReplacement,
)
from pynguin.assertion.mutation_analysis.operators.inheritance import (
    HidingVariableDeletion,
    OverriddenMethodCallingPositionChange,
    OverridingMethodDeletion,
    SuperCallingDeletion,
    SuperCallingInsert,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    ConditionalOperatorDeletion,
    ConditionalOperatorInsertion,
    LogicalConnectorReplacement,
    LogicalOperatorDeletion,
    LogicalOperatorReplacement,
    RelationalOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.loop import (
    OneIterationLoop,
    ReverseIterationLoop,
    ZeroIterationLoop,
)
from pynguin.assertion.mutation_analysis.operators.misc import (
    AssignmentOperatorReplacement,
    BooleanLiteralReplacement,
    BreakContinueReplacement,
    ConstantReplacement,
    FStringReplacement,
    SliceIndexRemove,
)
from pynguin.assertion.mutation_analysis.operators.statement import (
    MatchCaseDeletion,
    ReturnValueReplacement,
)

standard_operators: list[type[MutationOperator]] = [
    ArithmeticOperatorDeletion,
    ArithmeticOperatorReplacement,
    AssignmentOperatorReplacement,
    BooleanLiteralReplacement,
    BreakContinueReplacement,
    ConditionalOperatorDeletion,
    ConditionalOperatorInsertion,
    ConstantReplacement,
    DecoratorDeletion,
    ExceptionHandlerDeletion,
    ExceptionSwallowing,
    ExceptionTypeReplacement,
    FStringReplacement,
    HidingVariableDeletion,
    LogicalConnectorReplacement,
    LogicalOperatorDeletion,
    LogicalOperatorReplacement,
    MatchCaseDeletion,
    OverriddenMethodCallingPositionChange,
    OverridingMethodDeletion,
    RelationalOperatorReplacement,
    ReturnValueReplacement,
    SliceIndexRemove,
    SuperCallingDeletion,
    SuperCallingInsert,
]

# Note: AssignmentValueReplacement and LambdaReplacement are deliberately not
# registered here: experimental operators are part of every mutation-analysis
# run, and both operators only produce noise mutants (trivially killed as
# incompetent mutants in covered code, unkillable in uncovered code).
experimental_operators: list[type[MutationOperator]] = [
    OneIterationLoop,
    ReverseIterationLoop,
    ZeroIterationLoop,
]
