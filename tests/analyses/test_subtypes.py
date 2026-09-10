#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Unit and integration tests for sub-type generation."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pynguin.configuration as config
import pynguin.generator as gen
from pynguin.analyses.generator import RandomGeneratorProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.testcase.testcase import TestCase
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
)
from tests.fixtures.examples.abstract_classes import Animal, Bird, Circle, Shape


def test_abstract_class_has_subclass_generators():
    """Verify that an abstract class receives generators from its concrete subclasses."""
    cluster = generate_test_cluster("tests.fixtures.examples.abstract_classes")
    shape_type = cluster.type_system.convert_type_hint(Shape)

    generators = cluster.get_generators_for(shape_type)
    assert len(generators) == 2

    constructed_types = {
        gen_obj.owner.name for gen_obj in generators if isinstance(gen_obj, GenericConstructor)
    }
    assert constructed_types == {"Circle", "Rectangle"}


def test_abstract_class_has_no_direct_constructor():
    """Verify that an abstract base class does not have its own constructor registered."""
    cluster = generate_test_cluster("tests.fixtures.examples.abstract_classes")
    shape_type = cluster.type_system.convert_type_hint(Shape)

    direct_generators = cluster.generator_provider.get_for_type(shape_type)
    assert len(direct_generators) == 0


def test_multi_level_inheritance_subtypes():
    """Verify that sub-types are resolved across multiple inheritance levels."""
    cluster = generate_test_cluster("tests.fixtures.examples.abstract_classes")
    animal_type = cluster.type_system.convert_type_hint(Animal)
    bird_type = cluster.type_system.convert_type_hint(Bird)

    animal_gens = cluster.get_generators_for(animal_type)
    animal_constructors = {g.owner.name for g in animal_gens if isinstance(g, GenericConstructor)}
    assert "Penguin" in animal_constructors

    bird_gens = cluster.get_generators_for(bird_type)
    bird_constructors = {g.owner.name for g in bird_gens if isinstance(g, GenericConstructor)}
    assert "Penguin" in bird_constructors


def test_select_generator_for_subtypes():
    """Verify that select_generator_for selects a valid concrete subtype generator."""
    cluster = generate_test_cluster("tests.fixtures.examples.abstract_classes")
    shape_type = cluster.type_system.convert_type_hint(Shape)

    selected = cluster.generator_provider.select_generator_for(shape_type)
    assert isinstance(selected, GenericConstructor)
    assert selected.owner.name in {"Circle", "Rectangle"}


def test_testfactory_emits_subclass_for_abstract_parameter():
    """Verify that TestFactory emits a concrete subclass statement for an abstract type."""
    cluster = generate_test_cluster("tests.fixtures.examples.abstract_classes")
    shape_type = cluster.type_system.convert_type_hint(Shape)

    factory = TestFactory(cluster)
    test_case = TestCase()

    var_name, cursor = factory._create_or_reuse_var(test_case, shape_type, Shape, 0, 0)
    assert var_name is not None
    assert cursor > 0
    assert test_case.size() > 0

    code = test_case.to_code()
    assert "Circle(" in code or "Rectangle(" in code


def test_testfactory_reuses_existing_subclass_var():
    """Verify that an existing subclass variable can be reused when base class is requested."""
    cluster = generate_test_cluster("tests.fixtures.examples.abstract_classes")
    shape_type = cluster.type_system.convert_type_hint(Shape)
    circle_type = cluster.type_system.convert_type_hint(Circle)

    factory = TestFactory(cluster)
    test_case = TestCase()

    var_circle, _ = factory._create_or_reuse_var(test_case, circle_type, Circle, 0, 0)
    assert var_circle is not None

    with mock.patch.object(config.configuration.test_creation, "object_reuse_probability", 1.0):
        reused_var, _ = factory._create_or_reuse_var(
            test_case, shape_type, Shape, test_case.size(), 0
        )
        assert reused_var == var_circle


def test_random_generator_provider_subtypes():
    """Verify that RandomGeneratorProvider also resolves subtypes for abstract classes."""
    config.configuration.generator_selection.generator_selection_algorithm = (
        config.Selection.RANDOM_SELECTION
    )
    cluster = generate_test_cluster("tests.fixtures.examples.abstract_classes")
    assert isinstance(cluster.generator_provider, RandomGeneratorProvider)

    shape_type = cluster.type_system.convert_type_hint(Shape)
    gens = cluster.get_generators_for(shape_type)
    constructed_types = {g.owner.name for g in gens if isinstance(g, GenericConstructor)}
    assert constructed_types == {"Circle", "Rectangle"}

    # Reset to default
    config.configuration.generator_selection.generator_selection_algorithm = (
        config.Selection.RANK_SELECTION
    )


def test_integration_abstract_subtypes(tmp_path: Path):
    """Integration test: Pynguin generates and executes tests using concrete subtypes."""
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    project_path = project_path / "tests" / "fixtures" / "examples"

    configuration = config.Configuration(
        seeding=config.SeedingConfiguration(
            seed=42, constant_seeding=False, dynamic_constant_seeding=False
        ),
        algorithm=config.Algorithm.DYNAMOSA,
        stopping=config.StoppingConfiguration(maximum_iterations=5),
        module_name="abstract_classes",
        test_case_output=config.TestCaseOutputConfiguration(
            output_path=str(tmp_path),
        ),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path),
            statistics_backend=config.StatisticsBackend.CSV,
        ),
    )
    gen.set_configuration(configuration)

    result = gen.run_pynguin()
    assert result == gen.ReturnCode.OK
