#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# flake8: noqa
import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


def seed_test_case():
    # Needed for checking if testcases with wrong functionname as input are handled properly
    var2 = module0.i_have_a_wrong_name()
