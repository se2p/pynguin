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
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.testcase as tc


# -- FIXTURES --------------------------------------------------------------------------


@pytest.fixture(scope="function")
def test_case_mock():
    return MagicMock(tc.TestCase)


# -- CONFIGURATIONS FOR PYTEST ---------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--integration", action="store_true", help="Run integration tests.",
    )


def pytest_runtest_setup(item):
    if "integration" in item.keywords and not item.config.getvalue("integration"):
        pytest.skip("need --integration option to run")
