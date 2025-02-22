#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import graphviz


def show_dot_graph(dot_str: str):
    """Show a graph using Graphviz."""
    graph = graphviz.Source(dot_str)
    graph.view()


def print_dunder(obj):
    """Prints all dunder (__) attributes of an object row by row.

    DISCLAIMER: This function is only used for debugging purposes. Do not use it in
    production code as it uses the print function.

    Usage: Set a breakpoint somewhere in the code, execute the debugger and once it
    stops at the breakpoint, switch over to the console and type print_dunder(my_obj).

    :param obj: The object to inspect.
    """
    for attr in dir(obj):
        if attr.startswith("__"):
            print(f"{attr}: {getattr(obj, attr)}")  # noqa: T201
