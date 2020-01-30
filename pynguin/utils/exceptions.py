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
"""Provides custom exception types."""


class ConfigurationException(BaseException):
    """An exception type that's raised if the generator has no proper configuration."""


class GenerationException(BaseException):
    """An exception during test generation.

    This type shall be used for all exceptions that occur during test generation and
    that are caused by the test-generation process.
    """


class ConstructionFailedException(BaseException):
    """An exception used when error occurs during construction of a test case."""
