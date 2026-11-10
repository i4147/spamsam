"""Pytest configuration.

Keeping a conftest.py at the project root makes the project directory
importable, so the tests run both against an installed package and after
an in-place build::

    python setup.py build_ext --inplace
    pytest
"""
