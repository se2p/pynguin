#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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


class TimerError(Exception):
    """A custom exception used to report errors in use of Timer class"""


class InstructionNotFoundException(BaseException):
    """A custom exception if no matching instruction is found for a search."""


class UncertainStackEffectException(BaseException):
    """A custom exception if the simulation of the stack effect is not possible
    due to an instruction with special control flow."""


class TestTimeoutException(BaseException):
    """A custom exception if the execution of a single test took
    longer than the configured maximum duration."""


class SlicingTimeoutException(BaseException):
    """A custom exception if slicing of a single test took longer
    than the configured maximum duration."""
