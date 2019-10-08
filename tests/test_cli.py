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
import argparse
from unittest import mock

from pynguin.cli import main, _create_argument_parser


def test_main_empty_argv():
    with mock.patch("pynguin.cli.TestGenerator") as generator_mock:
        generator_mock.return_value.run.return_value = 0
        assert main() == 0


def test_main_with_argv():
    with mock.patch("pynguin.cli.TestGenerator") as generator_mock:
        generator_mock.return_value.run.return_value = 0
        assert main(["--help"]) == 0


def test__create_argument_parser():
    parser = _create_argument_parser()
    assert isinstance(parser, argparse.ArgumentParser)
