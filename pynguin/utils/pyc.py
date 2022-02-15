#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
# Parsing of the .pyc header is inspired by
# https://nedbatchelder.com/blog/200804/the_structure_of_pyc_files.html
"""Provides a utility class to handle pyc files."""

import marshal
import struct
import time
from types import CodeType
from typing import Tuple

from pynguin.instrumentation.instrumentation import InstrumentationTransformer


class Pyc:
    """
    Class representing a compiled Python file in .pyc format
    """

    def __init__(self, file: str):
        """
         Unpack a pyc file from version 3.6
         Format pyc file:
             - 4 bytes magic number
             - 4 bytes flags
             - 4 bytes compilation timestamp
             - 4 bytes size (of sourcecode)
             - rest: module code object
        Args:
            file: The file name to unpack
        """
        self._file: str = file

        with open(self._file, "rb") as file_stream:
            self._magic: bytes = file_stream.read(4)
            self._flags: bytes = file_stream.read(4)
            self._timestamp: bytes = file_stream.read(4)
            self._size: bytes = file_stream.read(4)

            self._code: CodeType = marshal.load(file_stream)

    def get_path(self) -> str:
        """Returns the path towards the pyc file.

        Returns:
            The path to the pyc file as string.
        """
        return self._file

    def get_header_data(self) -> Tuple[bytes, bytes, bytes, bytes]:
        """
            Get the header data of a pyc file.
        Returns:
            A tuple containing the magic bits, flags, timestamp and size of
            the pyc file.
        """
        return self._magic, self._flags, self._timestamp, self._size

    def print_header(self) -> None:
        """
        Prints the header data of a pyc file.
        The printed data contains the magic bits, flags, timestamp and size of
        the pyc file.
        """
        unix_time: int = struct.unpack("I", self._timestamp)[0]
        formatted_time: str = time.asctime(time.localtime(unix_time))
        formatted_size: int = struct.unpack("I", self._size)[0]
        print(f"\tFilename:     {self._file}")
        print(f"\tMagic number: {str(self._magic)}")
        print(f"\tTimestamp:    {unix_time} ({formatted_time})")
        print(f"\tSource size:  {formatted_size} bytes")

    def get_code_object(self) -> CodeType:
        """The executable code object of a pyc file.

        Returns:
            The code of the pyc file as CodeType.
        """
        return self._code

    def set_code_object(self, code: CodeType) -> None:
        """Set the executable code to a copy of a given code object.

        Args:
            code: The new code object of the pyc file.
        """
        self._code = CodeType(
            code.co_argcount,
            code.co_posonlyargcount,
            code.co_kwonlyargcount,
            code.co_nlocals,
            code.co_stacksize,
            code.co_flags,
            code.co_code,
            code.co_consts,
            code.co_names,
            code.co_varnames,
            code.co_filename,
            code.co_name,
            code.co_firstlineno,
            code.co_lnotab,
            code.co_freevars,
            code.co_cellvars,
        )

    def instrument(self, transformer: InstrumentationTransformer) -> None:
        """Instrument the pyc file with the given InstrumentationTransformer.

        Args:
            transformer: The transformer instrumenting the pyc file's code.
        """
        instrumented_code = transformer.instrument_module(self._code)
        self.set_code_object(instrumented_code)

    def write(self, file: str) -> str:
        """
        Write the header and code of the pyc file into a file at the given path.
        Args:
            file: The path and file name where to write the file to.

        Returns:
            The path of the written file as a string.
        """
        # Write the to a compiled Python file
        with open(file, "wb") as file_stream:
            file_stream.write(self._magic)
            file_stream.write(self._flags)
            file_stream.write(self._timestamp)
            file_stream.write(self._size)
        with open(file, "ab+") as file_stream:
            marshal.dump(self._code, file_stream)

        return file

    def overwrite(self) -> str:
        """
        Overwrite the header and code of the pyc file.

        Returns:
            The path of the overwritten file as a string.
        """
        # Write to a compiled Python file
        with open(self._file, "wb") as file_stream:
            file_stream.write(self._magic)
            file_stream.write(self._flags)
            file_stream.write(self._timestamp)
            file_stream.write(self._size)
        with open(self._file, "ab+") as file_stream:
            marshal.dump(self._code, file_stream)

        return self._file
