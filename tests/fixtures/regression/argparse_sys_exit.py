#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import argparse


def foo():
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input')
    args = parser.parse_args()
