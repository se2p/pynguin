#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/__init__.py.
"""

from .arithmetic import *
from .base import *
from .decorator import *
from .exception import *
from .inheritance import *
from .logical import *
from .loop import *
from .misc import *

SuperCallingInsert = utils.get_by_python_version([
    SuperCallingInsertPython27,
    SuperCallingInsertPython35,
])

standard_operators = {
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
}

experimental_operators = {
    ClassmethodDecoratorInsertion,
    OneIterationLoop,
    ReverseIterationLoop,
    SelfVariableDeletion,
    StatementDeletion,
    StaticmethodDecoratorInsertion,
    ZeroIterationLoop,
}
