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
