#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import numpy as np

from pynguin.utils.pynguinml import np_rng


def test_get_rng_returns_instance(monkeypatch):
    dummy_rng = np.random.default_rng()
    monkeypatch.setattr(np_rng, "NP_RNG", dummy_rng)

    result = np_rng.get_rng()
    assert result is dummy_rng
