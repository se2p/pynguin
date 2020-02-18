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
import importlib

from pynguin.instrumentation.basis import get_tracer
from pynguin.instrumentation.machinery import install_import_hook


def test_hook():
    with install_import_hook(True, "tests.fixtures.instrumentation.mixed"):
        module = importlib.import_module("tests.fixtures.instrumentation.mixed")
        importlib.reload(module)
        assert get_tracer(module)
