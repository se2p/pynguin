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
import pytest

from pynguin.utils.type_utils import is_primitive_type


@pytest.mark.parametrize(
    "type_, result",
    [
        pytest.param(int, True),
        pytest.param(float, True),
        pytest.param(str, True),
        pytest.param(bool, True),
        pytest.param(complex, True),
        pytest.param(type, False),
        pytest.param(None, False),
    ],
)
def test_is_primitive_type(type_, result):
    assert is_primitive_type(type_) == result
