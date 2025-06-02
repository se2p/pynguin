#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import datetime
import importlib
import sys
import threading

from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import pynguin.__version__ as ver  # noqa: PLC2701
import pynguin.configuration as config

from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTrace
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.report import CoverageEntry
from pynguin.utils.report import CoverageReport
from pynguin.utils.report import LineAnnotation
from pynguin.utils.report import get_coverage_report
from pynguin.utils.report import render_coverage_report
from pynguin.utils.report import render_xml_coverage_report


def test_coverage_entry_add():
    assert CoverageEntry(2, 1) + CoverageEntry(3, 7) == CoverageEntry(5, 8)


def test_coverage_entry_add_inplace():
    foo = CoverageEntry(2, 1)
    foo += CoverageEntry(3, 7)
    assert foo == CoverageEntry(5, 8)


@pytest.mark.parametrize(
    "line,msg",
    [
        (
            LineAnnotation(
                1,
                MagicMock(CoverageEntry),
                CoverageEntry(1, 2),
                CoverageEntry(0, 0),
                CoverageEntry(),
            ),
            "1/2 branches covered",
        ),
        (
            LineAnnotation(
                1,
                MagicMock(CoverageEntry),
                CoverageEntry(0, 0),
                CoverageEntry(1, 2),
                CoverageEntry(),
            ),
            "1/2 branchless code objects covered",
        ),
        (
            LineAnnotation(
                1,
                MagicMock(CoverageEntry),
                CoverageEntry(1, 2),
                CoverageEntry(3, 4),
                CoverageEntry(),
            ),
            "1/2 branches covered; 3/4 branchless code objects covered",
        ),
        (
            LineAnnotation(
                1,
                MagicMock(CoverageEntry),
                CoverageEntry(1, 2),
                CoverageEntry(3, 4),
                CoverageEntry(1, 1),
            ),
            "1/2 branches covered; 3/4 branchless code objects covered; Line 1 covered",
        ),
    ],
)
def test_line_annotation_message(line, msg):
    assert line.message() == msg


@pytest.fixture
def demo_module() -> str:
    return """def foo():
    pass


def baz():
    assert 3 == 5 and 3 == -3


def bar(x: int):
    if x:
        return 5
    else:
        return 6
"""


@pytest.fixture
def sample_report() -> CoverageReport:
    return CoverageReport(
        module="cov_demo",
        source=[
            "def foo():\n",
            "    pass\n",
            "\n",
            "\n",
            "def baz():\n",
            "    assert 3 == 5 and 3 == -3\n",
            "\n",
            "\n",
            "def bar(x: int):\n",
            "    if x:\n",
            "        return 5\n",
            "    else:\n",
            "        return 6\n",
        ],
        branches=CoverageEntry(covered=2, existing=6),
        branchless_code_objects=CoverageEntry(covered=1, existing=2),
        lines=CoverageEntry(covered=2, existing=8),
        line_annotations=[
            LineAnnotation(
                line_no=1,
                total=CoverageEntry(covered=2, existing=3),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=1, existing=2),
                lines=CoverageEntry(covered=1, existing=1),
            ),
            LineAnnotation(
                line_no=2,
                total=CoverageEntry(covered=0, existing=1),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=1),
            ),
            LineAnnotation(
                line_no=3,
                total=CoverageEntry(covered=0, existing=0),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=0),
            ),
            LineAnnotation(
                line_no=4,
                total=CoverageEntry(covered=0, existing=0),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=0),
            ),
            LineAnnotation(
                line_no=5,
                total=CoverageEntry(covered=1, existing=1),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=1, existing=1),
            ),
            LineAnnotation(
                line_no=6,
                total=CoverageEntry(covered=2, existing=5),
                branches=CoverageEntry(covered=2, existing=4),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=1),
            ),
            LineAnnotation(
                line_no=7,
                total=CoverageEntry(covered=0, existing=0),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=0),
            ),
            LineAnnotation(
                line_no=8,
                total=CoverageEntry(covered=0, existing=0),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=0),
            ),
            LineAnnotation(
                line_no=9,
                total=CoverageEntry(covered=0, existing=1),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=1),
            ),
            LineAnnotation(
                line_no=10,
                total=CoverageEntry(covered=0, existing=3),
                branches=CoverageEntry(covered=0, existing=2),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=1),
            ),
            LineAnnotation(
                line_no=11,
                total=CoverageEntry(covered=0, existing=1),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=1),
            ),
            LineAnnotation(
                line_no=12,
                total=CoverageEntry(covered=0, existing=0),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=0),
            ),
            LineAnnotation(
                line_no=13,
                total=CoverageEntry(covered=0, existing=1),
                branches=CoverageEntry(covered=0, existing=0),
                branchless_code_objects=CoverageEntry(covered=0, existing=0),
                lines=CoverageEntry(covered=0, existing=1),
            ),
        ],
        branch_coverage=0.375,
        line_coverage=0.25,
    )


def test_get_coverage_report(sample_report, tmp_path: Path, demo_module):
    target = tmp_path / "foo"
    target.mkdir()
    test_module = "cov_demo"
    with (target / (test_module + ".py")).open(mode="w", encoding="utf-8") as out_file:
        out_file.write(demo_module)
    sys.path.insert(0, str(target.absolute()))

    test_case = MagicMock()
    last_result = MagicMock(
        execution_trace=ExecutionTrace(
            executed_code_objects=OrderedSet([0]),
            executed_predicates={},
            true_distances={0: 0.0, 1: 1.0},
            false_distances={0: 1.0, 1: 0.0},
            covered_line_ids=OrderedSet([0, 1]),
        )
    )
    test_case.get_last_execution_result.return_value = last_result
    test_suite = MagicMock(test_case_chromosomes=[test_case])
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.LINE,
        config.CoverageMetric.BRANCH,
    ]
    with install_import_hook(test_module, tracer):
        importlib.import_module(test_module)
    executor = MagicMock(tracer=tracer)
    config.configuration.module_name = test_module
    assert (
        get_coverage_report(
            test_suite,
            executor,
            {config.CoverageMetric.LINE, config.CoverageMetric.BRANCH},
        )
        == sample_report
    )


def test_render_coverage_report(sample_report, tmp_path: Path):
    report_path = tmp_path / "report.html"
    render_coverage_report(
        sample_report,
        report_path,
        datetime.datetime(1970, 1, 1),  # noqa: DTZ001
    )
    with report_path.open(encoding="utf-8", mode="r") as file:
        content = file.readlines()
        assert content == [
            "<!DOCTYPE html>\n",
            '<html lang="en">\n',
            "<head>\n",
            '  <meta charset="UTF-8">\n',
            "  <title>Pynguin coverage report</title>\n",
            "  <style>\n",
            "\n",
            "pre { line-height: 125%; }\n",
            "td.linenos .normal { color: #586e75; background-color: #073642; "
            "padding-left: 5px; padding-right: 5px; }\n",
            "span.linenos { color: #586e75; background-color: #073642; padding-left: "
            "5px; padding-right: 5px; }\n",
            "td.linenos .special { color: #000000; background-color: #ffffc0; "
            "padding-left: 5px; padding-right: 5px; }\n",
            "span.linenos.special { color: #000000; background-color: #ffffc0; "
            "padding-left: 5px; padding-right: 5px; }\n",
            ".highlight .hll { background-color: #073642 }\n",
            ".highlight { background: #002b36; color: #839496 }\n",
            ".highlight .c { color: #586E75; font-style: italic } /* Comment */\n",
            ".highlight .err { color: #839496; background-color: #DC322F } /* Error */\n",
            ".highlight .esc { color: #839496 } /* Escape */\n",
            ".highlight .g { color: #839496 } /* Generic */\n",
            ".highlight .k { color: #859900 } /* Keyword */\n",
            ".highlight .l { color: #839496 } /* Literal */\n",
            ".highlight .n { color: #839496 } /* Name */\n",
            ".highlight .o { color: #586E75 } /* Operator */\n",
            ".highlight .x { color: #839496 } /* Other */\n",
            ".highlight .p { color: #839496 } /* Punctuation */\n",
            ".highlight .ch { color: #586E75; font-style: italic } /* Comment.Hashbang */\n",
            ".highlight .cm { color: #586E75; font-style: italic } /* Comment.Multiline */\n",
            ".highlight .cp { color: #D33682 } /* Comment.Preproc */\n",
            ".highlight .cpf { color: #586E75 } /* Comment.PreprocFile */\n",
            ".highlight .c1 { color: #586E75; font-style: italic } /* Comment.Single */\n",
            ".highlight .cs { color: #586E75; font-style: italic } /* Comment.Special */\n",
            ".highlight .gd { color: #DC322F } /* Generic.Deleted */\n",
            ".highlight .ge { color: #839496; font-style: italic } /* Generic.Emph */\n",
            ".highlight .ges { color: #839496; font-weight: bold; font-style: italic } "
            "/* Generic.EmphStrong */\n",
            ".highlight .gr { color: #DC322F } /* Generic.Error */\n",
            ".highlight .gh { color: #839496; font-weight: bold } /* Generic.Heading */\n",
            ".highlight .gi { color: #859900 } /* Generic.Inserted */\n",
            ".highlight .go { color: #839496 } /* Generic.Output */\n",
            ".highlight .gp { color: #268BD2; font-weight: bold } /* Generic.Prompt */\n",
            ".highlight .gs { color: #839496; font-weight: bold } /* Generic.Strong */\n",
            ".highlight .gu { color: #839496; text-decoration: underline } /* "
            "Generic.Subheading */\n",
            ".highlight .gt { color: #268BD2 } /* Generic.Traceback */\n",
            ".highlight .kc { color: #2AA198 } /* Keyword.Constant */\n",
            ".highlight .kd { color: #2AA198 } /* Keyword.Declaration */\n",
            ".highlight .kn { color: #CB4B16 } /* Keyword.Namespace */\n",
            ".highlight .kp { color: #859900 } /* Keyword.Pseudo */\n",
            ".highlight .kr { color: #859900 } /* Keyword.Reserved */\n",
            ".highlight .kt { color: #B58900 } /* Keyword.Type */\n",
            ".highlight .ld { color: #839496 } /* Literal.Date */\n",
            ".highlight .m { color: #2AA198 } /* Literal.Number */\n",
            ".highlight .s { color: #2AA198 } /* Literal.String */\n",
            ".highlight .na { color: #839496 } /* Name.Attribute */\n",
            ".highlight .nb { color: #268BD2 } /* Name.Builtin */\n",
            ".highlight .nc { color: #268BD2 } /* Name.Class */\n",
            ".highlight .no { color: #268BD2 } /* Name.Constant */\n",
            ".highlight .nd { color: #268BD2 } /* Name.Decorator */\n",
            ".highlight .ni { color: #268BD2 } /* Name.Entity */\n",
            ".highlight .ne { color: #268BD2 } /* Name.Exception */\n",
            ".highlight .nf { color: #268BD2 } /* Name.Function */\n",
            ".highlight .nl { color: #268BD2 } /* Name.Label */\n",
            ".highlight .nn { color: #268BD2 } /* Name.Namespace */\n",
            ".highlight .nx { color: #839496 } /* Name.Other */\n",
            ".highlight .py { color: #839496 } /* Name.Property */\n",
            ".highlight .nt { color: #268BD2 } /* Name.Tag */\n",
            ".highlight .nv { color: #268BD2 } /* Name.Variable */\n",
            ".highlight .ow { color: #859900 } /* Operator.Word */\n",
            ".highlight .pm { color: #839496 } /* Punctuation.Marker */\n",
            ".highlight .w { color: #839496 } /* Text.Whitespace */\n",
            ".highlight .mb { color: #2AA198 } /* Literal.Number.Bin */\n",
            ".highlight .mf { color: #2AA198 } /* Literal.Number.Float */\n",
            ".highlight .mh { color: #2AA198 } /* Literal.Number.Hex */\n",
            ".highlight .mi { color: #2AA198 } /* Literal.Number.Integer */\n",
            ".highlight .mo { color: #2AA198 } /* Literal.Number.Oct */\n",
            ".highlight .sa { color: #2AA198 } /* Literal.String.Affix */\n",
            ".highlight .sb { color: #2AA198 } /* Literal.String.Backtick */\n",
            ".highlight .sc { color: #2AA198 } /* Literal.String.Char */\n",
            ".highlight .dl { color: #2AA198 } /* Literal.String.Delimiter */\n",
            ".highlight .sd { color: #586E75 } /* Literal.String.Doc */\n",
            ".highlight .s2 { color: #2AA198 } /* Literal.String.Double */\n",
            ".highlight .se { color: #2AA198 } /* Literal.String.Escape */\n",
            ".highlight .sh { color: #2AA198 } /* Literal.String.Heredoc */\n",
            ".highlight .si { color: #2AA198 } /* Literal.String.Interpol */\n",
            ".highlight .sx { color: #2AA198 } /* Literal.String.Other */\n",
            ".highlight .sr { color: #CB4B16 } /* Literal.String.Regex */\n",
            ".highlight .s1 { color: #2AA198 } /* Literal.String.Single */\n",
            ".highlight .ss { color: #2AA198 } /* Literal.String.Symbol */\n",
            ".highlight .bp { color: #268BD2 } /* Name.Builtin.Pseudo */\n",
            ".highlight .fm { color: #268BD2 } /* Name.Function.Magic */\n",
            ".highlight .vc { color: #268BD2 } /* Name.Variable.Class */\n",
            ".highlight .vg { color: #268BD2 } /* Name.Variable.Global */\n",
            ".highlight .vi { color: #268BD2 } /* Name.Variable.Instance */\n",
            ".highlight .vm { color: #268BD2 } /* Name.Variable.Magic */\n",
            ".highlight .il { color: #2AA198 } /* Literal.Number.Integer.Long */\n",
            "\n",
            "body{\n",
            "    color: #c9d1d9;\n",
            "    background: #0d1117;\n",
            "    font-family: monospace;\n",
            "    font-size: 16px;\n",
            "}\n",
            "\n",
            "td.lines span{\n",
            "    display: block;\n",
            "    padding-right: 8px;\n",
            "    line-height: 125%;\n",
            "}\n",
            "\n",
            ".notCovered{\n",
            "    border-right: 5px solid darkred;\n",
            "}\n",
            ".partiallyCovered{\n",
            "    border-right: 5px solid orangered;\n",
            "}\n",
            ".fullyCovered{\n",
            "    border-right: 5px solid darkgreen;\n",
            "}\n",
            ".notRelevant{\n",
            "    border-right: 5px solid transparent;\n",
            "}\n",
            "\n",
            "</style>\n",
            "</head>\n",
            "<body>\n",
            "<h1>Pynguin coverage report for module 'cov_demo'</h1>\n",
            "<p>Achieved 37.50% branch coverage:\n",
            "1/2 branchless code objects covered.\n",
            "2/6 branches covered.</p>\n",
            "<p>Achieved 25.00% line coverage:\n",
            "2/8 lines covered. </p>\n",
            "<table>\n",
            "    <tbody>\n",
            "        <tr>\n",
            '            <td style="width: 40px; text-align: right;" class="lines">\n',
            '                <span class="partiallyCovered" title="1/2 branchless code '
            'objects covered; Line 1 covered">1</span>\n',
            '                  <span class="notCovered" title="Line 2 not covered">2</span>\n',
            '                  <span class="notRelevant">3</span>\n',
            '                  <span class="notRelevant">4</span>\n',
            '                  <span class="fullyCovered" title="Line 5 covered">5</span>\n',
            '                  <span class="partiallyCovered" title="2/4 branches '
            'covered; Line 6 not covered">6</span>\n',
            '                  <span class="notRelevant">7</span>\n',
            '                  <span class="notRelevant">8</span>\n',
            '                  <span class="notCovered" title="Line 9 not covered">9</span>\n',
            '                  <span class="notCovered" title="0/2 branches covered;'
            ' Line 10 not covered">10</span>\n',
            '                  <span class="notCovered" title="Line 11 not covered">11</span>\n',
            '                  <span class="notRelevant">12</span>\n',
            '                  <span class="notCovered" title="Line 13 not covered">13</span>\n',
            "                  </td>\n",
            '            <td style="width: 100%;"><div '
            'class="highlight"><pre><span></span><span class="k">def</span><span '
            'class="w"> </span><span class="nf">foo</span><span class="p">():</span>\n',
            '    <span class="k">pass</span>\n',
            "\n",
            "\n",
            '<span class="k">def</span><span class="w"> </span><span '
            'class="nf">baz</span><span class="p">():</span>\n',
            '    <span class="k">assert</span> <span class="mi">3</span> <span '
            'class="o">==</span> <span class="mi">5</span> <span class="ow">and</span> '
            '<span class="mi">3</span> <span class="o">==</span> <span '
            'class="o">-</span><span class="mi">3</span>\n',
            "\n",
            "\n",
            '<span class="k">def</span><span class="w"> </span><span '
            'class="nf">bar</span><span class="p">(</span><span class="n">x</span><span '
            'class="p">:</span> <span class="nb">int</span><span class="p">):</span>\n',
            '    <span class="k">if</span> <span class="n">x</span><span class="p">:</span>\n',
            '        <span class="k">return</span> <span class="mi">5</span>\n',
            '    <span class="k">else</span><span class="p">:</span>\n',
            '        <span class="k">return</span> <span class="mi">6</span>\n',
            "</pre></div>\n",
            "</td>\n",
            "        </tr>\n",
            "    </tbody>\n",
            "</table>\n",
            "<footer>\n",
            "  <p>Created at 1970-01-01 00:00:00</p>\n",
            "</footer>\n",
            "</body>\n",
            "</html>",
        ]


def test_get_coverage_report_with_inspect_valueerror():
    """Test that get_coverage_report handles ValueError from inspect.getsourcelines.

    This test directly mocks inspect.getsourcelines to raise a ValueError,
    simulating the error that occurs with modules that have circular references
    in their decorators (like TensorFlow).
    """
    test_case = MagicMock()
    last_result = MagicMock(execution_trace=MagicMock())
    test_case.get_last_execution_result.return_value = last_result
    test_suite = MagicMock(test_case_chromosomes=[test_case])

    tracer = MagicMock()
    executor = MagicMock(tracer=tracer)
    module_name = "test_module"
    config.configuration.module_name = module_name
    mock_module = MagicMock()
    mock_trace = MagicMock()

    # Create a ValueError that simulates the error
    error_msg = "wrapper loop when unwrapping <module 'tensorflow.python.util.tf_decorator'>"
    value_error = ValueError(error_msg)

    # Use patches to mock all the functions called in get_coverage_report
    with (
        patch("pynguin.ga.computations.analyze_results", return_value=mock_trace),
        patch.object(executor.tracer, "get_subject_properties", return_value=MagicMock()),
        patch.object(executor.tracer, "lineids_to_linenos", return_value=OrderedSet()),
        patch.dict(sys.modules, {module_name: mock_module}),
        patch("inspect.getsourcelines", side_effect=value_error),
        pytest.raises(RuntimeError),  # Expect a RuntimeError to be raised
    ):
        get_coverage_report(
            test_suite,
            executor,
            {config.CoverageMetric.LINE, config.CoverageMetric.BRANCH},
        )


def test_render_xml_coverage_report(sample_report, tmp_path: Path):
    report_path = tmp_path / "report.xml"
    render_xml_coverage_report(
        sample_report,
        report_path,
        datetime.datetime(year=1970, month=1, day=1),  # noqa: DTZ001
    )
    expected = [
        '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE coverage SYSTEM '
        '"http://cobertura.sourceforge.net/xml/coverage-04.dtd"><coverage '
        'line-rate="0.25" branch-rate="0.375" lines-covered="2" lines-valid="8" '
        'branches-covered="3" branches-valid="8" complexity="0.0" '
        f'version="pynguin-{ver.__version__}" timestamp="0">\n',
        "  <sources>\n",
        "    <source>cov_demo</source>\n",
        "  </sources>\n",
        "  <packages>\n",
        '    <package name="" line-rate="0.25" branch-rate="0.375" complexity="0.0">\n',
        "      <classes>\n",
        '        <class name="" filename="cov_demo" line-rate="0.25" '
        'branch-rate="0.375" complexity="0.0">\n',
        "          <methods />\n",
        "          <lines>\n",
        '            <line number="1" hits="1" branch="true" condition-coverage="50% (1/2)" />\n',
        '            <line number="2" hits="0" branch="false" />\n',
        '            <line number="5" hits="1" branch="false" />\n',
        '            <line number="6" hits="1" branch="true" condition-coverage="50% (2/4)" />\n',
        '            <line number="9" hits="0" branch="false" />\n',
        '            <line number="10" hits="0" branch="true" condition-coverage="0% (0/2)" />\n',
        '            <line number="11" hits="0" branch="false" />\n',
        '            <line number="13" hits="0" branch="false" />\n',
        "          </lines>\n",
        "        </class>\n",
        "      </classes>\n",
        "    </package>\n",
        "  </packages>\n",
        "</coverage>",
    ]
    with report_path.open(encoding="utf-8", mode="r") as file:
        content = file.readlines()
        assert content == expected
