#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pynguin.configuration as config


def test_serialization_round_trip(tmp_path):
    """Make sure we can serialize/deserialize our configuration"""
    path = tmp_path / "serialized.json"

    with path.open("w") as write:
        config.configuration.dump_json(write, indent=4)

    loaded = config.Configuration.load_json(path)

    assert config.configuration == loaded
