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
    SliceIndexRemove,
)
from pynguin.assertion.mutation_analysis.operators.statement import (
    AssertionRemoval,
    ReturnValueReplacement,
)

standard_operators: list[type[MutationOperator]] = [
    ArithmeticOperatorDeletion,
    ArithmeticOperatorReplacement,
    AssertionRemoval,
    AssignmentOperatorReplacement,
    BooleanLiteralReplacement,
    BreakContinueReplacement,
    ConditionalOperatorDeletion,
    ConditionalOperatorInsertion,
    ConstantReplacement,
    DecoratorDeletion,
    ExceptionHandlerDeletion,
    ExceptionSwallowing,
    HidingVariableDeletion,
    LogicalConnectorReplacement,
    LogicalOperatorDeletion,
    LogicalOperatorReplacement,
    OverriddenMethodCallingPositionChange,
    OverridingMethodDeletion,
    RelationalOperatorReplacement,
    ReturnValueReplacement,
    SliceIndexRemove,
    SuperCallingDeletion,
    SuperCallingInsert,
]

experimental_operators: list[type[MutationOperator]] = [
    OneIterationLoop,
    ReverseIterationLoop,
    ZeroIterationLoop,
]
