#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ctypes


def cause_segmentation_fault():
    ctypes.string_at(0)  # Dereferencing NULL will cause SIGSEGV
