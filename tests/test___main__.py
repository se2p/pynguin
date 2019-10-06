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
import runpy
from unittest import mock

import pytest


@mock.patch("pynguin.cli.main")
def test___main__(main):
    main.return_value = 42
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        runpy.run_module("pynguin", run_name="__main__")
        main.assert_called_once()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 42
