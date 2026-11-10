# pyspamsum — SpamSum fuzzy hashing with a Cython core

A Python/Cython implementation of the **SpamSum** fuzzy hashing algorithm
(the ancestor of `ssdeep`).  Fuzzy hashes ("context-triggered piecewise
hashes") let you tell whether two inputs are *similar* — something
cryptographic hashes (MD5/SHA) can never do: flip one byte and MD5 changes
completely, while a SpamSum hash stays almost the same.

Design, exactly as intended:

| Part | Language | Why |
| --- | --- | --- |
| Hashing core (rolling hash, block hashes, trigger detection) | **Cython / C** | runs per input byte — the only hot path |
| Scoring & comparison (`compare`, Levenshtein, ...) | **pure Python** | works on 64-char strings, speed irrelevant |
| File & (recursive) folder traversal | **pure Python** | I/O bound; each file hashed by the C core |

The Cython core is a drop-in replacement for the original module:
`hash()`, `hash_from_file()`, `_spamsum()`, `f_table`, `sum_table`,
`byte_table`, `BLOCKSIZE_MIN`, `SPAMSUM_LENGTH` all behave identically
(verified by the test suite against the untouched reference implementation,
which ships as `pyspamsum/_pure.py` and doubles as an automatic fallback
backend when the extension is not built).

## Project layout

```
pyspamsum/
├── pyproject.toml            build-system + project metadata
├── setup.py                  compiles the extension (uses .pyx, or pre-built .c)
├── conftest.py               lets pytest run from a source checkout
├── pyspamsum/
│   ├── __init__.py           public API
│   ├── _imp.py               backend resolution (cython | python fallback)
│   ├── _spamsum.pyx          ★ the Cython hashing core
│   ├── _spamsum.c            pre-generated C (build without Cython)
│   ├── _pure.py              untouched pure-Python reference (test oracle / fallback)
│   ├── scoring.py            compare() and scoring helpers (pure Python)
│   └── folders.py            hash_file / hash_folder / hash_path
├── examples/
│   ├── demo_basic.py         strings, similarity scores, tiny-input caveat
│   ├── demo_files.py         files, folders (recursive), hash_path dispatch
│   ├── demo_similarity.py    near-duplicate detection across folder snapshots
│   └── demo_benchmark.py     Cython core vs pure Python speed
├── tools/
│   └── gen_golden.py         golden-vector generator + reference cross-check
└── tests/
    ├── test_hash.py          golden vectors, format invariants, error handling
    ├── test_consistency.py   Cython == pure-Python reference on 36 sizes + patterns
    ├── test_files.py         file/folder/path hashing incl. permission errors
    └── test_compare.py       compare() goldens, bounds, invalid formats
```

## Installation

Building requires a C compiler; Cython ≥ 3.0 is fetched automatically by
pip as a build requirement (a pre-generated `_spamsum.c` is included, so
`python setup.py build_ext` also works without Cython).

```bash
pip install .            # regular install
pip install -e .         # development install (needed before running pytest)
```

## Quick start

```python
>>> import pyspamsum
>>> pyspamsum.IMPLEMENTATION              # which backend is active
'cython'

>>> h = pyspamsum.hash(b'hello world')    # bytes or str (UTF-8 encoded)
>>> h
'3:iKFSMPn:rJPn'

>>> pyspamsum.hash_file('data/report.txt')            # single file
'48:k////2:k////O'

>>> pyspamsum.hash_folder('docs')                     # recursive by default
{'report.txt': '48:k////2:k////O', 'sub/notes.txt': '12:unwJnwm:unwJnwJm'}

>>> pyspamsum.hash_path('docs/report.txt')  # file -> str
'48:k////2:k////O'
>>> pyspamsum.hash_path('docs')             # folder -> dict
{...}

>>> pyspamsum.compare(h1, h2)             # similarity score 0..100
97
```

## API

| Function | Input → Output | Notes |
| --- | --- | --- |
| `hash(buf)` | `bytes`/`str` → `str` | same signature as the original module |
| `hash_from_file(path)` | `str` path → `str` | streams the file in 64 KiB chunks |
| `hash_file(path)` | `str`/`Path` → `str` | friendly alias of `hash_from_file` |
| `hash_folder(path, *, recursive=True, on_error=None)` | folder → `{relpath: hash}` | see below |
| `hash_path(path, **kwargs)` | file → `str`, folder → `dict` | dispatches on the file type |
| `compare(hash1, hash2)` | two hash strings → `int` 0..100 | pure Python, unchanged |

`hash_folder` maps each **regular file** under `path` (relative POSIX-style
path) to its hash.  There is deliberately no single hash for a whole
folder — fuzzy hashes are only meaningful per byte stream; compare two
folder mappings key by key instead.  Details:

* `recursive=True` (default) descends into subfolders; symlinks are not
  followed into directories (no cycles).
* Non-regular files (devices, sockets, fifos, broken links) are skipped.
* Traversal is sorted → deterministic results.
* `on_error(path, exception)` — when given, unreadable files/folders are
  reported and skipped; when omitted, the first unreadable entry raises
  `IOError`.

## Hash format

```
blocksize:hash1:hash2
   e.g.   96:VVwrp65gS6OdDGoOaNIRyCNvIDNqaf7oDhxz8PN2MXDosex2:jwV65V6OdDBOaNkyo2qafMbURXN
```

`blocksize` is the trigger block size (`3·2^k`), `hash1` is built from
blocks of that size (up to 64 base64 chars), `hash2` from blocks of
`2·blocksize` (up to 32 chars) — the second string makes comparison robust
when files grow and the effective block size changes.  `compare()`
implements the original scoring: block sizes must be equal or differ by a
factor of two, repeated-character runs are stripped, then a
Levenshtein-based score in 0..100 is computed.

## Tests

```bash
pip install -e .
pytest -v
```

111 tests, among them:

* **golden vectors** generated from the untouched reference implementation
  and cross-checked against the Cython core;
* **consistency**: Cython output == pure-Python output for every length in
  a 36-size list (including the 64 KiB streaming-buffer boundaries 65535/
  65536/65537), all 256 single-byte inputs, repetitive patterns, and feeds
  split into tiny 17-byte chunks;
* **files & folders**: recursive/non-recursive walking, permission errors,
  `on_error` callback, `hash_path` dispatch, determinism;
* **compare()**: localized-edit (100), append (97), small-mutation (99),
  unrelated (0), incompatible-block-size (0) goldens, score bounds,
  invalid formats.

`tools/gen_golden.py` regenerates the golden vectors and re-runs the
Cython-vs-reference cross-check (0 failures expected).

## Examples

```bash
python examples/demo_basic.py         # strings + similarity scores
python examples/demo_files.py         # files & recursive folders (+ optional path arg)
python examples/demo_similarity.py    # folder snapshot comparison vs MD5
python examples/demo_benchmark.py     # Cython core vs pure Python speed
```

## Performance

Measured with `examples/demo_benchmark.py` (512 KiB of random data,
CPython 3.12, Cython 3.3, gcc 14, x86-64):

```
pure python :    227.2 ms  (   2.3 MB/s)
cython core :      1.6 ms  ( 338.0 MB/s)
speedup     :    146.5x
```

File hashing keeps the reference behaviour of consuming the stream in
64 KiB chunks, so peak memory stays constant regardless of file size.

## Notes

* If the compiled extension is missing (e.g. the package was copied as
  plain sources), `pyspamsum` falls back to the pure-Python core and
  `pyspamsum.IMPLEMENTATION` reports `'python'`; everything keeps working,
  just slower.  The test `test_cython_backend_is_active` fails in that
  case, so a quiet fallback cannot go unnoticed.
* `hash` shadows the Python built-in *within the package namespace* — the
  original module did the same, and it keeps the API drop-in compatible.
* SpamSum was created by Andrew Tridgell; this project implements the
  algorithm described in his 2002 paper "Fuzzy Hashing" / spamsum notes.
