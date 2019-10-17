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

from pynguin.generation.export.pytestexporter import PyTestExporter


def test__create_function_node():
    result = PyTestExporter._create_function_node("foo", [])
    assert result.name == "test_foo"


def test__create_functions_empty_sequences():
    exporter = PyTestExporter([], "")
    result = exporter._create_functions([])
    assert len(result) == 0
