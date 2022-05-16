.. _install:

Installation of Pynguin
=======================

This part of the documentation covers the installation of Pynguin, since
proper installation of a software package is the first step to use it.

Using PIP
---------
.. warning::
  We highly recommend that you *do not* install Pynguin in your system's or user's
  Python package store; instead we recommend to use a `virtual environment <https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#installing-virtualenv>`_.

  This prevents issues between your system's package store and Pynguin's dependencies -
  which can easily cause version conflicts with other Python packages.

The easiest way to obtain Pynguin is by running this command in your terminal of
choice::

   $ pip install pynguin

Get the Source Code
-------------------

Released versions are also available through our `GitHub repository <https://github
.com/se2p/pynguin>`_.

You can either clone the public repository::

   $ git clone git://github.com/se2p/pynguin.git

Or download the `tarball <https://github.com/se2p/pynguin/tarball/master>`_::

   $ curl -OL https://github.com/se2p/pynguin/tarball/master
   # optionally, zipball is also available (for Windows users).
