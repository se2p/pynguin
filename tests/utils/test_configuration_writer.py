#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import logging

from pathlib import Path
from unittest.mock import patch

import pytest

import pynguin.configuration as config

from pynguin.configuration import StatisticsBackend
from pynguin.utils.configuration_writer import PYNGUIN_CONFIG_TOML
from pynguin.utils.configuration_writer import PYNGUIN_CONFIG_TXT
from pynguin.utils.configuration_writer import convert_config_to_dict
from pynguin.utils.configuration_writer import extract_parameter_list_from_config
from pynguin.utils.configuration_writer import write_configuration


@pytest.fixture
def expected_toml(tmp_path):
    expected_toml = Path(tmp_path) / f"expected-{PYNGUIN_CONFIG_TOML}"
    expected = """project_path = ""
module_name = ""
algorithm = "RANDOM"
ignore_modules = []
ignore_methods = []
subprocess = false
subprocess_if_recommended = true

[test_case_output]
output_path = ""
crash_path = ""
export_strategy = "PY_TEST"
max_length_test_case = 2500
assertion_generation = "MUTATION_ANALYSIS"
allow_stale_assertions = false
mutation_strategy = "FIRST_ORDER_MUTANTS"
mutation_order = 1
post_process = true
float_precision = 0.01
format_with_black = true

[statistics_output]
report_dir = "{REPORT_DIR}"
statistics_backend = "CSV"
timeline_interval = 1000000000
timeline_interpolation = true
coverage_metrics = [ "BRANCH",]
output_variables = [ "TargetModule", "Coverage",]
configuration_id = ""
run_id = ""
project_name = ""
create_coverage_report = false
type_guess_top_n = 10

[stopping]
maximum_search_time = -1
maximum_test_executions = -1
maximum_statement_executions = -1
maximum_slicing_time = 600
maximum_iterations = -1
maximum_test_execution_timeout = 5
maximum_coverage = 100
maximum_coverage_plateau = -1
minimum_coverage = 100
minimum_plateau_iterations = -1
maximum_memory = 3000
test_execution_time_per_statement = 1

[large_language_model]
api_key = ""
model_name = "gpt-4o-mini"
temperature = 0.8
hybrid_initial_population = false
llm_test_case_percentage = 0.5
enable_response_caching = false
call_llm_for_uncovered_targets = false
coverage_threshold = 1
call_llm_on_stall_detection = false
max_plateau_len = 25
max_llm_interventions = 1

[seeding]
seed = {SEED}
constant_seeding = true
initial_population_seeding = false
initial_population_data = ""
seeded_testcases_reuse_probability = 0.9
initial_population_mutations = 0
dynamic_constant_seeding = true
seeded_primitives_reuse_probability = 0.2
seeded_dynamic_values_reuse_probability = 0.6
seed_from_archive = false
seed_from_archive_probability = 0.2
seed_from_archive_mutations = 3
max_dynamic_length = 1000
max_dynamic_pool_size = 50

[type_inference]
type_inference_strategy = "TYPE_HINTS"
type_tracing = 0.0

[pynguinml]
ml_testing_enabled = false
constraints_path = ""
dtype_mapping_path = ""
constructor_function = ""
constructor_function_parameter = ""
max_ndim = 4
max_shape_dim = 4
ignore_constraints_probability = 0.25

[test_creation]
max_recursion = 10
max_delta = 20
max_int = 2048
string_length = 20
bytes_length = 20
collection_size = 5
primitive_reuse_probability = 0.5
object_reuse_probability = 0.9
none_weight = 0
any_weight = 0
original_type_weight = 5
type_tracing_weight = 10
type4py_weight = 10
type_tracing_kept_guesses = 2
wrap_var_param_type_probability = 0.7
negate_type = 0.1
skip_optional_parameter_probability = 0.7
max_attempts = 1000
insertion_uut = 0.5
max_size = 100
use_random_object_for_call = 0.0

[search_algorithm]
min_initial_tests = 1
max_initial_tests = 10
population = 50
chromosome_length = 40
chop_max_length = true
elite = 1
crossover_rate = 0.75
test_insertion_probability = 0.1
test_delete_probability = 0.3333333333333333
test_change_probability = 0.3333333333333333
test_insert_probability = 0.3333333333333333
statement_insertion_probability = 0.5
random_perturbation = 0.2
change_parameter_probability = 0.1
tournament_size = 5
rank_bias = 1.7
selection = "TOURNAMENT_SELECTION"
use_archive = false
filter_covered_targets_from_test_cluster = false
number_of_mutations = 1

[mio]
exploitation_starts_at_percent = 0.5

[random]
max_sequence_length = 10
max_sequences_combined = 10

[test_case_output.minimization]
test_case_minimization_strategy = "CASE"
test_case_minimization_direction = "BACKWARD"

[mio.initial_config]
number_of_tests_per_target = 10
random_test_or_from_archive_probability = 0.5
number_of_mutations = 1

[mio.focused_config]
number_of_tests_per_target = 1
random_test_or_from_archive_probability = 0.0
number_of_mutations = 10
"""
    expected = expected.replace("{REPORT_DIR}", str(tmp_path))
    expected = expected.replace("{SEED}", str(config.configuration.seeding.seed))
    expected_toml.write_text(expected)
    return expected_toml


@pytest.fixture
def expected_txt(tmp_path):
    expected_txt = Path(tmp_path) / f"expected-{PYNGUIN_CONFIG_TXT}"
    expected = """("Configuration(project_path='', module_name='', "
 "test_case_output=TestCaseOutputConfiguration(output_path='', crash_path='', "
 "export_strategy=<ExportStrategy.PY_TEST: 'PY_TEST'>, "
 'max_length_test_case=2500, '
 'assertion_generation=<AssertionGenerator.MUTATION_ANALYSIS: '
 "'MUTATION_ANALYSIS'>, allow_stale_assertions=False, "
 'mutation_strategy=<MutationStrategy.FIRST_ORDER_MUTANTS: '
 "'FIRST_ORDER_MUTANTS'>, mutation_order=1, post_process=True, "
 'minimization=Minimization(test_case_minimization_strategy=<MinimizationStrategy.CASE: '
 "'CASE'>, test_case_minimization_direction=<MinimizationDirection.BACKWARD: "
 "'BACKWARD'>), float_precision=0.01, format_with_black=True), "
 "algorithm=<Algorithm.RANDOM: 'RANDOM'>, "
 "statistics_output=StatisticsOutputConfiguration(report_dir='{REPORT_DIR}', "
 "statistics_backend=<StatisticsBackend.CSV: 'CSV'>, "
 'timeline_interval=1000000000, timeline_interpolation=True, '
 "coverage_metrics=[<CoverageMetric.BRANCH: 'BRANCH'>], "
 "output_variables=[TargetModule, Coverage], configuration_id='', run_id='', "
 "project_name='', create_coverage_report=False, type_guess_top_n=10), "
 'stopping=StoppingConfiguration(maximum_search_time=-1, '
 'maximum_test_executions=-1, maximum_statement_executions=-1, '
 'maximum_slicing_time=600, maximum_iterations=-1, '
 'maximum_test_execution_timeout=5, maximum_coverage=100, '
 'maximum_coverage_plateau=-1, minimum_coverage=100, '
 'minimum_plateau_iterations=-1, maximum_memory=3000, '
 'test_execution_time_per_statement=1), '
 "large_language_model=LLMConfiguration(api_key='', model_name='gpt-4o-mini', "
 'temperature=0.8, hybrid_initial_population=False, '
 'llm_test_case_percentage=0.5, enable_response_caching=False, '
 'call_llm_for_uncovered_targets=False, coverage_threshold=1, '
 'call_llm_on_stall_detection=False, max_plateau_len=25, '
 'max_llm_interventions=1), '
 'seeding=SeedingConfiguration(seed={SEED}, '
 'constant_seeding=True, initial_population_seeding=False, '
 "initial_population_data='', seeded_testcases_reuse_probability=0.9, "
 'initial_population_mutations=0, dynamic_constant_seeding=True, '
 'seeded_primitives_reuse_probability=0.2, '
 'seeded_dynamic_values_reuse_probability=0.6, seed_from_archive=False, '
 'seed_from_archive_probability=0.2, seed_from_archive_mutations=3, '
 'max_dynamic_length=1000, max_dynamic_pool_size=50), '
 'type_inference=TypeInferenceConfiguration(type_inference_strategy=<TypeInferenceStrategy.TYPE_HINTS: '
 "'TYPE_HINTS'>, type_tracing=0.0), "
 'pynguinml=PynguinMLConfiguration(ml_testing_enabled=False, '
 "constraints_path='', dtype_mapping_path='', constructor_function='', "
 "constructor_function_parameter='', max_ndim=4, max_shape_dim=4, "
 'ignore_constraints_probability=0.25), '
 'test_creation=TestCreationConfiguration(max_recursion=10, max_delta=20, '
 'max_int=2048, string_length=20, bytes_length=20, collection_size=5, '
 'primitive_reuse_probability=0.5, object_reuse_probability=0.9, '
 'none_weight=0, any_weight=0, original_type_weight=5, type_tracing_weight=10, '
 'type4py_weight=10, type_tracing_kept_guesses=2, '
 'wrap_var_param_type_probability=0.7, negate_type=0.1, '
 'skip_optional_parameter_probability=0.7, max_attempts=1000, '
 'insertion_uut=0.5, max_size=100, use_random_object_for_call=0.0), '
 'search_algorithm=SearchAlgorithmConfiguration(min_initial_tests=1, '
 'max_initial_tests=10, population=50, chromosome_length=40, '
 'chop_max_length=True, elite=1, crossover_rate=0.75, '
 'test_insertion_probability=0.1, test_delete_probability=0.3333333333333333, '
 'test_change_probability=0.3333333333333333, '
 'test_insert_probability=0.3333333333333333, '
 'statement_insertion_probability=0.5, random_perturbation=0.2, '
 'change_parameter_probability=0.1, tournament_size=5, rank_bias=1.7, '
 "selection=<Selection.TOURNAMENT_SELECTION: 'TOURNAMENT_SELECTION'>, "
 'use_archive=False, filter_covered_targets_from_test_cluster=False, '
 'number_of_mutations=1), '
 'mio=MIOConfiguration(initial_config=MIOPhaseConfiguration(number_of_tests_per_target=10, '
 'random_test_or_from_archive_probability=0.5, number_of_mutations=1), '
 'focused_config=MIOPhaseConfiguration(number_of_tests_per_target=1, '
 'random_test_or_from_archive_probability=0.0, number_of_mutations=10), '
 'exploitation_starts_at_percent=0.5), '
 'random=RandomConfiguration(max_sequence_length=10, '
 'max_sequences_combined=10), ignore_modules=[], ignore_methods=[], '
 'subprocess=False, subprocess_if_recommended=True)')"""  # noqa:E501
    expected = expected.replace("{REPORT_DIR}", str(tmp_path))
    expected = expected.replace("{SEED}", str(config.configuration.seeding.seed))
    expected_txt.write_text(expected)
    return expected_txt


@pytest.fixture
def expected_parameter_list() -> list[str]:
    parameter_list: list[str] = [
        "--project_path /tmp",
        "--module_name dummy",
        "--export_strategy PY_TEST",
        "--max_length_test_case 2500",
        "--assertion_generation MUTATION_ANALYSIS",
        "--allow_stale_assertions False",
        "--mutation_strategy FIRST_ORDER_MUTANTS",
        "--mutation_order 1",
        "--post_process True",
        "--minimization.test_case_minimization_direction BACKWARD",
        "--minimization.test_case_minimization_strategy CASE",
        "--float_precision 0.01",
        "--format_with_black True",
        "--algorithm RANDOM",  # as defined in tests/conftest.py
        "--report_dir pynguin-report",
        "--statistics_backend CSV",
        "--timeline_interval 1000000000",
        "--timeline_interpolation True",
        "--coverage_metrics BRANCH",
        "--output_variables TargetModule\nCoverage",
        "--create_coverage_report False",
        "--type_guess_top_n 10",
        "--maximum_search_time -1",
        "--maximum_test_executions -1",
        "--maximum_statement_executions -1",
        "--maximum_slicing_time 600",
        "--maximum_iterations -1",
        "--maximum_memory 3000",
        "--maximum_test_execution_timeout 5",
        "--maximum_coverage 100",
        "--maximum_coverage_plateau -1",
        "--minimum_coverage 100",
        "--minimum_plateau_iterations -1",
        "--ml_testing_enabled False",
        "--test_execution_time_per_statement 1",
        "--seed 12345",
        "--constant_seeding True",
        "--initial_population_seeding False",
        "--seeded_testcases_reuse_probability 0.9",
        "--initial_population_mutations 0",
        "--dynamic_constant_seeding True",
        "--seeded_primitives_reuse_probability 0.2",
        "--seeded_dynamic_values_reuse_probability 0.6",
        "--seed_from_archive False",
        "--seed_from_archive_probability 0.2",
        "--seed_from_archive_mutations 3",
        "--max_dynamic_length 1000",
        "--max_dynamic_pool_size 50",
        "--type_inference_strategy TYPE_HINTS",
        "--type_tracing 0.0",
        "--max_recursion 10",
        "--max_delta 20",
        "--max_int 2048",
        "--string_length 20",
        "--subprocess False",
        "--subprocess_if_recommended True",
        "--bytes_length 20",
        "--collection_size 5",
        "--primitive_reuse_probability 0.5",
        "--object_reuse_probability 0.9",
        "--none_weight 0",
        "--any_weight 0",
        "--original_type_weight 5",
        "--type_tracing_weight 10",
        "--type4py_weight 10",
        "--type_tracing_kept_guesses 2",
        "--wrap_var_param_type_probability 0.7",
        "--negate_type 0.1",
        "--skip_optional_parameter_probability 0.7",
        "--max_attempts 1000",
        "--insertion_uut 0.5",
        "--max_size 100",
        "--use_random_object_for_call 0.0",
        "--min_initial_tests 1",
        "--max_initial_tests 10",
        "--population 50",
        "--chromosome_length 40",
        "--chop_max_length True",
        "--elite 1",
        "--crossover_rate 0.75",
        "--test_insertion_probability 0.1",
        "--test_delete_probability 0.3333333333333333",
        "--test_change_probability 0.3333333333333333",
        "--test_insert_probability 0.3333333333333333",
        "--statement_insertion_probability 0.5",
        "--random_perturbation 0.2",
        "--change_parameter_probability 0.1",
        "--tournament_size 5",
        "--rank_bias 1.7",
        "--selection TOURNAMENT_SELECTION",
        "--use_archive False",
        "--filter_covered_targets_from_test_cluster False",
        "--number_of_mutations 1",
        "--exploitation_starts_at_percent 0.5",
        "--initial_config.number_of_tests_per_target 10",
        "--initial_config.random_test_or_from_archive_probability 0.5",
        "--initial_config.number_of_mutations 1",
        "--focused_config.number_of_tests_per_target 1",
        "--focused_config.random_test_or_from_archive_probability 0.0",
        "--focused_config.number_of_mutations 10",
        "--max_sequence_length 10",
        "--max_sequences_combined 10",
        "--model_name gpt-4o-mini",
        "--temperature 0.8",
        "--hybrid_initial_population False",
        "--llm_test_case_percentage 0.5",
        "--enable_response_caching False",
        "--call_llm_for_uncovered_targets False",
        "--coverage_threshold 1",
        "--call_llm_on_stall_detection False",
        "--max_plateau_len 25",
        "--max_llm_interventions 1",
        "--max_ndim 4",
        "--max_shape_dim 4",
        "--ignore_constraints_probability 0.25",
    ]
    return sorted(parameter_list)


def test_write_configuration(expected_toml, expected_txt, tmp_path):
    config.configuration.statistics_output.statistics_backend = StatisticsBackend.CSV
    config.configuration.statistics_output.report_dir = str(tmp_path)

    write_configuration()

    toml_path = Path(config.configuration.statistics_output.report_dir) / PYNGUIN_CONFIG_TOML
    assert toml_path.exists()
    assert toml_path.read_text() == expected_toml.read_text()

    txt_path = Path(config.configuration.statistics_output.report_dir) / PYNGUIN_CONFIG_TXT
    assert txt_path.exists()
    assert txt_path.read_text() == expected_txt.read_text()


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        ({"key": "value"}, {"key": "value"}),
        (["item1", "item2"], ["item1", "item2"]),
        (StatisticsBackend.CSV, "CSV"),
        (123, 123),
        ("string", "string"),
        (None, None),
    ],
)
def test_convert_config_to_dict(input_value, expected_output):
    assert convert_config_to_dict(input_value) == expected_output


def test_convert_object_with_dict():
    class CustomConfig:
        def __init__(self):
            self.option = "value"

    obj = CustomConfig()
    expected_output = {"option": "value"}

    assert convert_config_to_dict(obj) == expected_output


def test_ignore_callable_and_dunder_methods():
    class Sample:
        def __init__(self):
            self.visible = "yes"
            self._hidden = "no"
            self.__private = "secret"

        def method(self):
            return "should be ignored"

    sample_obj = Sample()
    converted = convert_config_to_dict(sample_obj)

    assert "visible" in converted
    assert "_hidden" in converted
    assert "__private" not in converted
    assert "method" not in converted


def test_extract_parameter_list_from_config(expected_parameter_list):
    config.configuration.module_name = "dummy"
    config.configuration.project_path = "/tmp"  # noqa: S108
    config.configuration.seeding.seed = 12345

    parameter_list = extract_parameter_list_from_config(verbosity=False)

    assert parameter_list == [elem.replace(" ", "\n") for elem in expected_parameter_list]


def test_extract_parameter_list_from_config_preserve_verbosity():
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        mock_logger.getEffectiveLevel.return_value = logging.DEBUG  # Simulate verbose logging
        parameter_list = extract_parameter_list_from_config()
        assert "-v" not in parameter_list


@pytest.mark.parametrize(
    "log_level, expected_v_flag",
    [
        (logging.INFO, "-v"),
        (logging.DEBUG, "-vv"),
    ],
)
def test_extract_parameter_list_from_config_preserve_verbosity_2(log_level, expected_v_flag):
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        mock_logger.getEffectiveLevel.return_value = log_level

        parameter_list = extract_parameter_list_from_config()

        assert expected_v_flag in parameter_list
