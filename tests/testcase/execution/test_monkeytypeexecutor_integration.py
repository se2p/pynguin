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
import pynguin.configuration as config
from pynguin.testcase.execution.monkeytypeexecutor import MonkeyTypeExecutor


def test_no_exceptions(short_test_case):
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    executor = MonkeyTypeExecutor()
    result = executor.execute(short_test_case)
    assert len(result) == 1
    assert (
        result[0].funcname == "tests.fixtures.accessibles.accessible.SomeType.__init__"
    )
    assert result[0].arg_types["y"] == int
