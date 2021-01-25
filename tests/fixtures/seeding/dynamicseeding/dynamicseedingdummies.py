#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Dummy method for testing adding a value
def compare_op_dummy(x, y):
    if x == y:
        return 0
    else:
        return 1


# Dummy method for testing the str.startswith method
def startswith_dummy(s1, s2):
    if s1.startswith(s2):
        return 0
    else:
        return 1


# Dummy method for testing the str.endswith method
def endswith_dummy(s1, s2):
    if s1.endswith(s2):
        return 0
    else:
        return 1


# Dummy method for testing the str.isalnum() method
def isalnum_dummy(s1):
    if s1.isalnum():
        return 0
    else:
        return 1


# Dummy method for testing the str.islower() method
def islower_dummy(s1):
    if s1.islower():
        return 0
    else:
        return 1


# Dummy method for testing the str.isupper() method
def isupper_dummy(s1):
    if s1.isupper():
        return 0
    else:
        return 1


# Dummy method for testing the str.isdecimal() method
def isdecimal_dummy(s1):
    if s1.isdecimal():
        return 0
    else:
        return 1


# Dummy method for testing the str.isalpha() method
def isalpha_dummy(s1):
    if s1.isalpha():
        return 0
    else:
        return 1


# Dummy method for testing the str.isdigit() method
def isdigit_dummy(s1):
    if s1.isdigit():
        return 0
    else:
        return 1


# Dummy method for testing the str.isidentifier() method
def isidentifier_dummy(s1):
    if s1.isidentifier():
        return 0
    else:
        return 1


# Dummy method for testing the str.isnumeric() method
def isnumeric_dummy(s1):
    if s1.isnumeric():
        return 0
    else:
        return 1


# Dummy method for testing the str.isprintable() method
def isprintable_dummy(s1):
    if s1.isprintable():
        return 0
    else:
        return 1


# Dummy method for testing the str.isspace() method
def isspace_dummy(s1):
    if s1.isspace():
        return 0
    else:
        return 1


# Dummy method for testing the str.istitle() method
def istitle_dummy(s1):
    if s1.istitle():
        return 0
    else:
        return 1
