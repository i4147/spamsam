"""Build script for pyspamsum (compiles the Cython hashing core).

Normal install (Cython is declared as a build requirement in
pyproject.toml, so plain pip handles everything)::

    pip install .

Fallbacks, in order:

* Cython available          -> compile ``pyspamsum/_spamsum.pyx``
* Cython missing, but the
  pre-generated ``pyspamsum/_spamsum.c`` is present -> compile the C file
"""

import os

from setuptools import Extension, setup

PYX = os.path.join('pyspamsum', '_spamsum.pyx')
PREGEN_C = os.path.join('pyspamsum', '_spamsum.c')

try:
    from Cython.Build import cythonize
except ImportError:
    cythonize = None

if cythonize is not None and os.path.exists(PYX):
    ext_modules = cythonize(
        [Extension('pyspamsum._spamsum', [PYX])],
        language_level='3',
    )
elif os.path.exists(PREGEN_C):
    ext_modules = [Extension('pyspamsum._spamsum', [PREGEN_C])]
else:  # pragma: no cover
    raise RuntimeError('Cython is required to build pyspamsum: pip install cython')

setup(ext_modules=ext_modules)
