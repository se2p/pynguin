#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest


@pytest.fixture
def file_to_open(tmp_path):
    file = tmp_path / "test_file.txt"
    file.write_text("test")
    return file
