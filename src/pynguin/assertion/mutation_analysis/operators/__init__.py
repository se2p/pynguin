#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/__init__.py.
"""

from pynguin.assertion.mutation_analysis.operators.arithmetic import *
from pynguin.assertion.mutation_analysis.operators.base import *
from pynguin.assertion.mutation_analysis.operators.decorator import *
from pynguin.assertion.mutation_analysis.operators.exception import *
from pynguin.assertion.mutation_analysis.operators.inheritance import *
from pynguin.assertion.mutation_analysis.operators.logical import *
from pynguin.assertion.mutation_analysis.operators.loop import *
from pynguin.assertion.mutation_analysis.operators.misc import *

standard_operators = [
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

experimental_operators = [
    OneIterationLoop,
    ReverseIterationLoop,
    ZeroIterationLoop,
]
