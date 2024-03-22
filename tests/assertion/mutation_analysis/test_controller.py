#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pynguin.assertion.mutation_analysis.controller as c
import pynguin.configuration as config


def test_mutate_module():
    controller = c.MutationController()
    config.configuration.module_name = "tests.fixtures.examples.triangle"
    config.configuration.seeding.seed = 42
    mutations = controller.mutate_module()
    assert len(mutations) == 14
