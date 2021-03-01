#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from pynguin.typeinference.nonstrategy import NoTypeInferenceStrategy


def _func_1(x: int) -> int:
    return x  # pragma: no cover


def test_strategy():
    strategy = NoTypeInferenceStrategy()
    result = strategy.infer_type_info(_func_1)
    assert result.parameters == {"x": None}
    assert result.return_type is None
