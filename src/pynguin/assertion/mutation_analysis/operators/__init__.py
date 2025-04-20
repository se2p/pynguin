#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides mutation operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/__init__.py
and integrated in Pynguin.
"""

from pynguin.assertion.mutation_analysis.operators.arithmetic import (
    ArithmeticOperatorDeletion,
)
from pynguin.assertion.mutation_analysis.operators.arithmetic import (
    ArithmeticOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator
from pynguin.assertion.mutation_analysis.operators.decorator import DecoratorDeletion
from pynguin.assertion.mutation_analysis.operators.exception import (
    ExceptionHandlerDeletion,
)
from pynguin.assertion.mutation_analysis.operators.exception import ExceptionSwallowing
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
from pynguin.assertion.mutation_analysis.operators.logical import (
    ConditionalOperatorDeletion,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    ConditionalOperatorInsertion,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    LogicalConnectorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    LogicalOperatorDeletion,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    LogicalOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    RelationalOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.loop import OneIterationLoop
from pynguin.assertion.mutation_analysis.operators.loop import ReverseIterationLoop
from pynguin.assertion.mutation_analysis.operators.loop import ZeroIterationLoop
from pynguin.assertion.mutation_analysis.operators.misc import (
    AssignmentOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.misc import BreakContinueReplacement
from pynguin.assertion.mutation_analysis.operators.misc import ConstantReplacement
from pynguin.assertion.mutation_analysis.operators.misc import SliceIndexRemove


standard_operators: list[type[MutationOperator]] = [
    ArithmeticOperatorDeletion,
    ArithmeticOperatorReplacement,
    AssignmentOperatorReplacement,
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
    SliceIndexRemove,
    SuperCallingDeletion,
    SuperCallingInsert,
]

experimental_operators: list[type[MutationOperator]] = [
    OneIterationLoop,
    ReverseIterationLoop,
    ZeroIterationLoop,
]
