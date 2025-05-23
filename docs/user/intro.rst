.. _introduction:

Introduction
============

Philosophy
----------

Pynguin was developed with a few :pep:`20` idioms in mind.

#. Beautiful is better than ugly.
#. Explicit is better than implicit.
#. Simple is better than complex.
#. Complex is better than complicated.
#. Readability counts.

We furthermore like the thoughts and ideas from Robert C. Martin's *Clean Code*.
All contributions to Pynguin should keep these important rules in mind.

.. _`publications`:

Publications on Pynguin
-----------------------

* S. Lukasczyk, F. Kroiß, and G. Fraser.
  **An Empirical Study of Automated Unit Test Generation for Python**.
  Empirical Software Engineering **28**, 36 (2023).
  DOI `10.1007/s10664-022-10248-w <https://doi.org/10.1007/s10664-022-10248-w>`_.
  `arXiv:2111.05003 <https://arxiv.org/abs/2111.05003>`_

  BibTeX entry:

  .. code-block:: bibtex

      @Article{journals/ese/LukasczykKF23,
        author    = {Stephan Lukasczyk and Florian Kroi{\ss} and Gordon Fraser},
        title     = {An empirical study of automated unit test generation for python},
        journal   = {Empirical Software Engineering},
        volume    = {28},
        number    = {2},
        year      = {2023},
        doi       = {10.1007/s10664-022-10248-w},
      }

* S. Lukasczyk and G. Fraser.
  **Pynguin: Automated Unit Test Generation for Python**.
  In *Proceedings of the 44th International Conference on Software Engineering
  Companion.*
  ACM, 2022.
  DOI: `10.1145/3510454.3516829 <https://doi.org/10.1145/3510454.3516829>`_.
  `arXiv:2202.05218 <https://arxiv.org/abs/2202.05218>`_

  BibTeX entry:

  .. code-block:: bibtex

      @inproceedings{DBLP:conf/icse/LukasczykF22,
        author    = {Stephan Lukasczyk and Gordon Fraser},
        title     = {Pynguin: Automated Unit Test Generation for Python},
        booktitle = {44th {IEEE/ACM} International Conference on Software Engineering:
                     Companion Proceedings, {ICSE} Companion 2022, Pittsburgh, PA, USA,
                     May 22-24, 2022},
        pages     = {168--172},
        publisher = {{ACM/IEEE}},
        year      = {2022},
        doi       = {10.1145/3510454.3516829},
      }

* S. Lukasczyk, F. Kroiß, and G. Fraser. **Automated Unit Test Generation for Python.**
  In *Proceedings of the 12th Symposium on Search-based Software Engineering.*
  Lecture Notes in Computer Science, vol. 12420, pp. 9–24.
  Springer, 2020.
  DOI: `10.1007/978-3-030-59762-7_2 <https://doi.org/10.1007/978-3-030-59762-7_2>`_.
  `arXiv:2007.14049 <https://arxiv.org/abs/2007.14049>`_

  BibTeX entry:

  .. code-block:: bibtex

      @InProceedings{conf/ssbse/LukasczykKF20,
        author    = {Stephan Lukasczyk and Florian Kroi{\ss} and Gordon Fraser},
        title     = {Automated Unit Test Generation for Python},
        booktitle = {Proceedings of the 12th Symposium on Search-based Software Engineering (SSBSE 2020, Bari, Italy, October 7–8)},
        year      = {2020},
        publisher = {Springer},
        series    = {Lecture Notes in Computer Science},
        volume    = {12420},
        pages     = {9--24},
        doi       = {10.1007/978-3-030-59762-7\_2},
      }

Theses on Pynguin
-----------------

This is an (incomplete) list of theses done on Pynguin.

* A. Hajdari: **Enhancing Automated Unit Testing for Machine Learning Libraries
  Based on API Constraints**. Master's Thesis. University of Passau, 2025.

  Added API-Documentation parsing and test generation for libraries which require
  tensor inputs based on the parsed constraints.

* A. Abdelillah: **Exploring LLM Integration into Automated Unit Test Generation**.
  Master's Thesis.  University of Passau, 2025.

  Integrated LLM querying, including prompting, parsing and the LLMOSAAlgorithm.
* G. Oberreuter Álvarez: **Effects of the Implementation of a Graph-Based Object Synthesis
  Heuristic on Pynguin**. Master's Thesis.  University of Passau, 2024.

  Adds a object-synthesis heuristic for the test generation based on generation graphs.
* L. Berg: **Improving automated unit test generation for machine learning libraries using
  structured input data**.  Master's Thesis.  University of Namur, 2024.

  Provides an approach to generate more structured input data and to run Pynguin more reliably on
  native-code libraries.
* F. Kroiß: **Type Tracing: Using Runtime Information to Improve Automated Unit-test Generation
  for Python**. Master's Thesis.  University of Passau, 2023.

  Provides an approach to infer and refine missing and existing type information based on the
  execution of the generated test cases.
* S. Labrenz: **Using Checked Coverage as Fitness Function for Test Generation in
  Python**.  Master's Thesis.  University of Passau, 2022.

  Provides checked coverage both as a fitness function for test generation as well as an
  optimisation criterion for assertion minimisation.
* M. Königseder: **DeepTyper für Python und der Einfluss von Typvorhersagen auf die
  automatische Testgenerierung**. Bachelor's Thesis.  University of Passau, 2022.

* M. Reichenberger: **Measuring Oracle Quality in Python**.  Master's Thesis.  University
  of Passau, 2022.

  Although this work did not directly contribute to Pynguin, its implementation of
  Checked Coverage was the basis for the thesis of S. Labrenz.
* F. Straubinger: **Mutation Analysis to Improve the Generation of Assertions for
  Automatically Generated Python Unit-tests**.  Bachelor's Thesis.  University of Passau,
  2021.

  Provided the mutation-based assertion generation for improved regression tests.
* L. Steffens: **Seeding Strategies in Search-Based Unit Test Generation for Python**.
  Bachelor's Thesis.  University of Passau, 2021.

  Provided the dynamic seeding as well as the seeding from existing test cases to
  Pynguin.
* F. Kroiß: **Automatic Generation of Whole Test Suites in Python**.  Bachelor's Thesis.
  University of Passau, 2020.

  Provided the whole-suite test generation algorithm as well as large parts of the core
  parts of Pynguin, e.g., instrumentation, test-case representation, and execution.
* C. Frädrich: **Combining Test Generation and Type Inference for Testing Dynamically
  Typed Programming Language**.  Master's Thesis.  University of Passau, 2019.

  Implemented a proof-of-concept using a Randoop-like test-generation algorithm and
  incorporated several ideas for type inference.  Although this work was done before
  Pynguin was actually startet, it is the foundation and proof-of-concept that test
  generation for Python was actually a feasible goal.  Thus, we consider it as the
  seminal starting point of this endeavour.

.. _`mit`:

MIT License
-----------

Pynguin is released under the terms of the `MIT License`_.

Copyright (c) 2019–2023 Pynguin Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

.. _`MIT License`: https://opensource.org/licenses/MIT
