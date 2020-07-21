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


def test_serialization_round_trip(tmp_path):
    """Make sure we can serialize/deserialize our configuration"""
    path = tmp_path / "serialized.json"

    with path.open("w") as write:
        config.INSTANCE.dump_json(write, indent=4)

    loaded = config.Configuration.load_json(path)

    assert config.INSTANCE == loaded
