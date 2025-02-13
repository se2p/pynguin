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
