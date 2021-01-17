#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Callable
from unittest.mock import MagicMock

import pytest

from pynguin.typeinference.nonstrategy import NoTypeInferenceStrategy
from pynguin.typeinference.strategy import InferredSignature
from pynguin.typeinference.typehintsstrategy import TypeHintsInferenceStrategy
from pynguin.typeinference.typeinference import TypeInference


def test_type_inference_strategy():
    strategy = MagicMock(TypeHintsInferenceStrategy)
    inference = TypeInference(strategies=[strategy])
    assert isinstance(inference._strategies[0], TypeHintsInferenceStrategy)


def test_type_inference_strategy_name():
    strategy = "pynguin.typeinference.typehintsstrategy.TypeHintsInferenceStrategy"
    inference = TypeInference(strategy_names=[strategy])
    assert inference


def test_type_inference_error():
    strategy = "foo.Bar"
    with pytest.raises(ImportError):
        TypeInference(strategy_names=[strategy])


def test_type_inference():
    inference = TypeInference()
    assert isinstance(inference._strategies[0], NoTypeInferenceStrategy)


def test_infer_type_info():
    strategy = MagicMock(TypeHintsInferenceStrategy)
    method_type = MagicMock(InferredSignature)
    strategy.infer_type_info.return_value = method_type
    inference = TypeInference(strategies=[strategy])
    result = inference.infer_type_info(MagicMock(Callable))
    assert result == [method_type]
