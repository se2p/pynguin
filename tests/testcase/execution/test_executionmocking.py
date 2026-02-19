#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import random
import weakref
from unittest import mock
from unittest.mock import MagicMock

import pynguin.configuration as config
from pynguin.testcase import execution
from pynguin.utils import randomness as _rnd


def test_make_deterministic_seeds_module_random():
    config.configuration.seeding.seed = 42
    with mock.patch("random.seed") as m:
        execution._make_deterministic()
    m.assert_called_once_with(42)


def test_make_deterministic_reseeds_tracked_instances():
    config.configuration.seeding.seed = 99
    mock_inst = MagicMock(spec=random.Random)  # noqa: S311
    tracked: weakref.WeakSet = weakref.WeakSet([mock_inst])
    orig_seed = random.Random.seed
    try:
        random.Random.seed.__pynguin_instances__ = tracked
        with mock.patch("random.seed"):
            execution._make_deterministic()
        mock_inst.seed.assert_called_once_with(99)
    finally:
        random.Random.seed = orig_seed


def test_make_deterministic_excludes_pynguin_rng():
    """Pynguin's own RNG must not be reseeded by _make_deterministic."""
    config.configuration.seeding.seed = 7
    tracked: weakref.WeakSet = weakref.WeakSet([_rnd.RNG])
    orig_seed = random.Random.seed
    try:
        random.Random.seed.__pynguin_instances__ = tracked
        with mock.patch.object(_rnd.RNG, "seed") as rng_seed_mock, mock.patch("random.seed"):
            execution._make_deterministic()
        rng_seed_mock.assert_not_called()
    finally:
        random.Random.seed = orig_seed
