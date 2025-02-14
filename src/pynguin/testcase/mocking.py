#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Classes that should be mocked during the execution of the test cases.

While replacing any module with an EmptyClass works in principle, a test case
will crash upon calling anything on it leading to only xfail test cases.
On the other hand, using MagicMock from the unittest.mock module allows everything to
be called on it without crashing, which also results in wrong test cases being generated.
Thus, the best solution is to create a custom Mock for every module to mock and overwrite
the problematic methods with a no-op. This is also what EvoSuite does.
"""

import types

from logging import Logger
from types import MappingProxyType
from types import ModuleType


class MockedLogger(Logger):
    """A mocked logger that does not register any handlers."""

    def __init__(self, name="any"):
        """Create a new mocked logger."""
        super().__init__(name)

    def addHandler(self, handler):  # noqa: N802
        """Do not add any handlers."""


mocked_logging: ModuleType = types.ModuleType("logging")
mocked_logging.getLogger = MockedLogger  # type: ignore[attr-defined]

mocks_to_use: MappingProxyType[str, ModuleType] = MappingProxyType({
    "logging": mocked_logging,
})
