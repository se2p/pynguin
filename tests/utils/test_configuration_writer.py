from pathlib import Path

import pytest

import pynguin.configuration as config
from pynguin.configuration import StatisticsBackend
from pynguin.utils.configuration_writer import write_configuration, \
    convert_config_to_dict


def test_write_configuration(tmp_path):
    config.configuration.statistics_output.statistics_backend = StatisticsBackend.CSV
    config.configuration.statistics_output.report_dir = str(tmp_path)

    write_configuration()

    toml_path = Path(
        config.configuration.statistics_output.report_dir) / "pynguin-config.toml"
    assert toml_path.exists()

    txt_path = Path(
        config.configuration.statistics_output.report_dir) / "pynguin-config.txt"
    assert txt_path.exists()


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        ({"key": "value"}, {"key": "value"}),
        (["item1", "item2"], ["item1", "item2"]),
        (Path("/some/path"), "/some/path"),
        (StatisticsBackend.CSV, "CSV"),
        (123, 123),
        ("string", "string"),
        (None, None),
        ({"_value_": "special_value"}, "special_value"),

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
