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
import os

import pytest

import pynguin.configuration as config
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.typeinference.nonstrategy import NoTypeInferenceStrategy
from pynguin.typeinference.stubstrategy import StubInferenceStrategy
from pynguin.typeinference.typehintsstrategy import TypeHintsInferenceStrategy
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor


def test_accessible():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.no_dependencies"
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 4


def test_generators():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.no_dependencies"
    ).generate_cluster()
    from tests.fixtures.cluster.no_dependencies import Test

    assert len(cluster.get_generators_for(Test)) == 1
    assert len(cluster.get_generators_for(int)) == 0
    assert len(cluster.get_generators_for(float)) == 0


def test_simple_dependencies():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.simple_dependencies"
    ).generate_cluster()
    from tests.fixtures.cluster.dependency import SomeArgumentType

    assert len(cluster.get_generators_for(SomeArgumentType)) == 1


def test_complex_dependencies():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.complex_dependencies"
    ).generate_cluster()
    assert cluster.num_accessible_objects_under_test() == 1


def test_max_recursion():
    config.INSTANCE.max_cluster_recursion = 1
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.complex_dependencies"
    ).generate_cluster()
    assert len(cluster.generators) == 2


def test_modifier():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.complex_dependencies"
    ).generate_cluster()
    assert len(cluster.modifiers) == 2


def test_simple_dependencies_only_own_classes():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.simple_dependencies"
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 1


def test_resolve_only_union():
    cluster = TestClusterGenerator(
        "tests.fixtures.cluster.typing_parameters"
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 2
    assert len(cluster.generators) == 1


def test_private_method_not_added():
    cluster = TestClusterGenerator(
        "tests.fixtures.examples.private_methods"
    ).generate_cluster()
    assert len(cluster.accessible_objects_under_test) == 1
    assert isinstance(
        next(iter(cluster.accessible_objects_under_test)), GenericConstructor
    )


@pytest.mark.parametrize(
    "inference_strategy, obj",
    [
        pytest.param(config.TypeInferenceStrategy.NONE, NoTypeInferenceStrategy),
        pytest.param(config.TypeInferenceStrategy.STUB_FILES, StubInferenceStrategy),
        pytest.param(
            config.TypeInferenceStrategy.TYPE_HINTS, TypeHintsInferenceStrategy
        ),
    ],
)
def test_initialise_type_inference_strategies(inference_strategy, obj):
    config.INSTANCE.type_inference_strategy = inference_strategy
    config.INSTANCE.stub_dir = os.devnull
    generator = TestClusterGenerator("")
    assert isinstance(generator._inference._strategies[0], obj)


def test_initialise_stub_inference_strategy_exception():
    config.INSTANCE.type_inference_strategy = config.TypeInferenceStrategy.STUB_FILES
    with pytest.raises(ConfigurationException):
        TestClusterGenerator("")


def test_initialise_unknown_type_inference_strategies():
    config.INSTANCE.type_inference_strategy = "foo"
    with pytest.raises(ConfigurationException):
        TestClusterGenerator("")
