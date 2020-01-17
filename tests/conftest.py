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
from collections import defaultdict
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereferenceimpl as vri


# -- FIXTURES --------------------------------------------------------------------------
from pynguin import Configuration


@pytest.fixture(scope="function")
def test_case_mock():
    return MagicMock(tc.TestCase)


@pytest.fixture(scope="function")
def variable_reference_mock():
    return MagicMock(vri.VariableReferenceImpl)


@pytest.fixture(scope="function")
def configuration_mock():
    return MagicMock(Configuration)


# -- CONFIGURATIONS AND EXTENSIONS FOR PYTEST ------------------------------------------


def pytest_addoption(parser):
    group = parser.getgroup("pynguin")
    group.addoption(
        "--integration", action="store_true", help="Run integration tests.",
    )
    group.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="Include slow tests in test run",
    )
    group.addoption(
        "--owl",
        action="store",
        type=str,
        default=None,
        metavar="fixture",
        help="Run tests using a specific fixture",
    )


def pytest_runtest_setup(item):
    if "integration" in item.keywords and not item.config.getvalue("integration"):
        pytest.skip("need --integration option to run")


def pytest_collection_modifyitems(items, config):
    """Deselect tests marked as slow if --slow is set."""
    if config.option.slow:
        return

    selected_items = []
    deselected_items = []

    for item in items:
        if item.get_closest_marker("slow"):
            deselected_items.append(item)
        else:
            selected_items.append(item)

    config.hook.pytest_deselected(items=deselected_items)
    items[:] = selected_items


class Turtle:
    """Plugin for adding markers to slow running tests."""

    def __init__(self, config):
        self._config = config
        self._durations = defaultdict(dict)
        self._durations.update(
            self._config.cache.get("cache/turtle", defaultdict(dict))
        )
        self._slow = 5.0

    def pytest_runtest_logreport(self, report):
        self._durations[report.nodeid][report.when] = report.duration

    @pytest.mark.tryfirst
    def pytest_collection_modifyitems(self, session, config, items):
        for item in items:
            duration = sum(self._durations[item.nodeid].values())
            if duration > self._slow:
                item.add_marker(pytest.mark.turtle)

    def pytest_sessionfinish(self, session):
        cached_durations = self._config.cache.get("cache/turtle", defaultdict(dict))
        cached_durations.update(self._durations)
        self._config.cache.set("cache/turtle", cached_durations)

    def pytest_configure(self, config):
        config.addinivalue_line("markers", "turtle: marker for slow running tests")


class Owl:
    """Plugin for running tests using a specific fixture."""

    def __init__(self, config):
        self._config = config

    def pytest_collection_modifyitems(self, items, config):
        if not config.option.owl:
            return

        selected_items = []
        deselected_items = []

        for item in items:
            if config.option.owl in getattr(item, "fixturenames", ()):
                selected_items.append(item)
            else:
                deselected_items.append(item)

        config.hook.pytest_deselected(items=deselected_items)
        items[:] = selected_items


def pytest_configure(config):
    config.pluginmanager.register(Turtle(config), "turtle")
    config.pluginmanager.register(Owl(config), "owl")
