#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from pynguin.generation.export.noneexporter import NoneExporter


def test_export_sequence(exportable_test_case, tmp_path):
    path = tmp_path / "generated.py"
    exporter = NoneExporter()
    exporter.export_sequences(str(path), [exportable_test_case, exportable_test_case])
    assert not path.exists()
