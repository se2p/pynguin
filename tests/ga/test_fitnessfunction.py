#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pynguin.ga.fitnessfunction as ff


def test_validation_ok():
    values = ff.FitnessValues(0, 0)
    assert len(values.validate()) == 0


def test_validation_wrong_fitness():
    values = ff.FitnessValues(-1, 0)
    assert len(values.validate()) == 1


def test_validation_wrong_coverage():
    values = ff.FitnessValues(0, 5)
    assert len(values.validate()) == 1


def test_validation_both_wrong():
    values = ff.FitnessValues(-1, 5)
    assert len(values.validate()) == 2
