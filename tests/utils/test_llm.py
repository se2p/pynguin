#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pynguin.utils.llm import extract_code


def test_extract_code():
    string = """
Lorem ipsum
```python
print('foo```bar```foo')
print('foo```bar```foo')
```
Lorem ipsum
```python
print('foo```bar```foo')
print('foo```bar```foo')
```
Lorem ipsum
```
print('foo```bar```foo')
print('foo```bar```foo')
```
"""
    expected = """print('foo```bar```foo')
print('foo```bar```foo')

print('foo```bar```foo')
print('foo```bar```foo')

print('foo```bar```foo')
print('foo```bar```foo')
"""
    actual = extract_code(string)
    assert actual == expected
