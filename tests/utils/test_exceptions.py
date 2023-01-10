#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pytest

from pynguin.utils.exceptions import (
    ConfigurationException,
    ConstructionFailedException,
    GenerationException,
)


def test_raise_test_generation_exception():
    with pytest.raises(GenerationException):
        raise GenerationException()


def test_raise_configuration_exception():
    with pytest.raises(ConfigurationException):
        raise ConfigurationException()


def test_raise_construction_failed_exception():
    with pytest.raises(ConstructionFailedException):
        raise ConstructionFailedException()


def test_raise_test_generation_exception_with_message():
    with pytest.raises(GenerationException) as exception:
        raise GenerationException("foo")
    assert exception.value.args[0] == "foo"


def test_raise_configuration_exception_with_message():
    with pytest.raises(ConfigurationException) as exception:
        raise ConfigurationException("foo")
    assert exception.value.args[0] == "foo"


def test_raise_construction_failed_exception_with_message():
    with pytest.raises(ConstructionFailedException) as exception:
        raise ConstructionFailedException("foo")
    assert exception.value.args[0] == "foo"
