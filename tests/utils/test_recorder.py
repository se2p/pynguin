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
from typing import Type
from unittest.mock import MagicMock

from coverage import Coverage, CoverageException

from pynguin.utils.recorder import CoverageRecorder, Record


def _provide_module_mock() -> Type:
    t = MagicMock(Type)
    t.__name__ = "Foo"
    return t


def test_add_module():
    recorder = CoverageRecorder([_provide_module_mock()])
    t = MagicMock(Type)
    t.__name__ = "Bar"
    recorder.add_module(t)
    assert len(recorder._modules) == 2
    assert "Foo" in recorder._records
    assert "Bar" in recorder._records


def test_save(tmp_path):
    recorder = CoverageRecorder(
        [_provide_module_mock()], file_name="test.csv", folder=tmp_path
    )
    recorder.save(tmp_path)
    file_name = os.path.join(tmp_path, "test.csv")
    assert os.path.exists(file_name)
    assert os.path.isfile(file_name)


def test_save_with_data(tmp_path):
    recorder = CoverageRecorder(
        [_provide_module_mock()], file_name="test.csv", folder=tmp_path
    )
    coverage = MagicMock(Coverage)
    coverage.report.return_value = "Dummy Coverage 42%"
    recorder.record_data(coverage)
    recorder.save()
    file_name = os.path.join(tmp_path, "test.csv")
    assert os.path.exists(file_name)
    assert os.path.isfile(file_name)


def test_record_none_data():
    recorder = CoverageRecorder([_provide_module_mock()])
    recorder.record_data(None)


def test_record_data():
    recorder = CoverageRecorder([_provide_module_mock()], file_name="test.csv")
    coverage = MagicMock(Coverage)
    coverage.report.return_value = "Dummy Coverage 42%"
    recorder.record_data(coverage)
    record = recorder._records["Foo"][0]
    assert isinstance(record, Record)
    assert record.module == "Foo"
    assert record.coverage == "Dummy Coverage 42%"


def test_record_data_raises_exception():
    recorder = CoverageRecorder([_provide_module_mock()], file_name="test.csv")
    coverage = MagicMock(Coverage)
    coverage.report.side_effect = CoverageException()
    recorder.record_data(coverage)
