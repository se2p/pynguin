#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""End-to-end test of constant seeding through :class:`TestFactory`.

Exercises the live seeding path -- ``ConstantPool`` /
``DelegatingConstantProvider`` / ``DynamicConstantProvider`` -> ``TestFactory``
-> :mod:`pynguin.testcase.literalgen` -- against a real test cluster, asserting
that seeded sentinel values show up in the rendered source of a generated test
case. This complements the pure-unit tests in ``test_literalgen.py`` by
verifying the pieces are actually wired together correctly.
"""

from __future__ import annotations

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
from pynguin.analyses.constants import (
    ConstantPool,
    DelegatingConstantProvider,
    DynamicConstantProvider,
    EmptyConstantProvider,
)
from pynguin.analyses.module import generate_test_cluster
from pynguin.utils import randomness


def _build_test_case_with_seeded_call(provider) -> tc.TestCase:
    """Build a test case invoking the sole accessible of the triangle fixture."""
    cluster = generate_test_cluster("tests.fixtures.examples.triangle")
    factory = tf.TestFactory(cluster, provider)
    test_case = tc.TestCase()
    accessible = cluster.get_random_accessible()
    assert accessible is not None
    position = factory.append_generic_accessible(test_case, accessible)
    assert position != -1
    return test_case


def test_static_pool_constant_seeding_reaches_generated_source():
    """A static-pool seeded value should appear in the generated test source."""
    randomness.RNG.seed(2024)
    original_probability = config.configuration.seeding.seeded_primitives_reuse_probability
    config.configuration.seeding.seeded_primitives_reuse_probability = 1.0
    try:
        pool = ConstantPool()
        pool.add_constant(1337)
        pool.add_constant("SENTINEL")
        provider = DelegatingConstantProvider(pool, EmptyConstantProvider(), 1.0)

        code = _build_test_case_with_seeded_call(provider).to_code()

        assert "1337" in code
    finally:
        config.configuration.seeding.seeded_primitives_reuse_probability = original_probability


def test_dynamic_pool_constant_seeding_reaches_generated_source():
    """A dynamically-seeded value should appear in the generated test source."""
    randomness.RNG.seed(2024)
    original_probability = config.configuration.seeding.seeded_primitives_reuse_probability
    config.configuration.seeding.seeded_primitives_reuse_probability = 1.0
    try:
        pool = ConstantPool()
        provider = DynamicConstantProvider(pool, EmptyConstantProvider(), 1.0, 1000)
        provider.add_value(4242)

        code = _build_test_case_with_seeded_call(provider).to_code()

        assert "4242" in code
    finally:
        config.configuration.seeding.seeded_primitives_reuse_probability = original_probability
