"""Backend resolution for the hashing core.

Prefers the compiled Cython extension (``pyspamsum._spamsum``); falls back
to the pure-Python reference port (``pyspamsum._pure``) when the extension
has not been built for the running interpreter.  ``IMPLEMENTATION`` records
which backend is active so tests and tools can tell the difference.
"""

try:
    from ._spamsum import (BLOCKSIZE_MIN, SPAMSUM_LENGTH, _spamsum, hash,
                           hash_from_file)
    IMPLEMENTATION = 'cython'
except ImportError:  # extension missing / built for another interpreter
    from ._pure import (BLOCKSIZE_MIN, SPAMSUM_LENGTH, _spamsum, hash,
                        hash_from_file)
    IMPLEMENTATION = 'python'

__all__ = ['hash', 'hash_from_file', '_spamsum', 'BLOCKSIZE_MIN',
           'SPAMSUM_LENGTH', 'IMPLEMENTATION']
