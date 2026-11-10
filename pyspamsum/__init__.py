"""pyspamsum -- SpamSum fuzzy hashing with a Cython core.

The hashing core (rolling hash, block hashing, block-boundary trigger
detection) lives in the compiled extension ``pyspamsum._spamsum``.
Similarity scoring and hash comparison are pure Python
(``pyspamsum.scoring``).  If the extension has not been built, the package
transparently falls back to a pure-Python port of the original algorithm
(``pyspamsum._pure``); ``pyspamsum.IMPLEMENTATION`` reports which backend
is active.

Public API
----------
hash(buf)                  str / bytes          -> "blocksize:hash1:hash2"
hash_from_file(path)       file path (str)      -> hash string
hash_file(path)            file path (str/Path) -> hash string
hash_folder(path, ...)     folder (str/Path)    -> {relpath: hash, ...}
hash_path(path, ...)       file -> str, folder -> dict
compare(hash1, hash2)      similarity score 0..100
"""

from ._imp import (
    BLOCKSIZE_MIN,
    IMPLEMENTATION,
    SPAMSUM_LENGTH,
    _spamsum,
    hash,
    hash_from_file,
)
from .folders import hash_file, hash_folder, hash_path
from .scoring import compare

__version__ = '1.0.0'

__all__ = [
    'hash', 'hash_from_file', 'hash_file', 'hash_folder', 'hash_path',
    'compare', 'BLOCKSIZE_MIN', 'SPAMSUM_LENGTH', 'IMPLEMENTATION',
    '__version__',
]
