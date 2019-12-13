# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from typing import Callable
from unittest.mock import MagicMock

import pytest

from pynguin.typeinference.nonstrategy import NoTypeInferenceStrategy
from pynguin.typeinference.strategy import InferredMethodType
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
    method_type = MagicMock(InferredMethodType)
    strategy.infer_type_info.return_value = method_type
    inference = TypeInference(strategies=[strategy])
    result = inference.infer_type_info(MagicMock(Callable))
    assert result == [method_type]
