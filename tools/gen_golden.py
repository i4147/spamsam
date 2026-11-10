"""Generate golden test vectors for the pyspamsum test suite.

Cross-checks the compiled Cython core against the untouched pure-Python
reference implementation (``pyspamsum._pure``) and prints ready-to-paste
golden values.

Run from anywhere after an in-place build (``python setup.py build_ext
--inplace``) or an editable install::

    python tools/gen_golden.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyspamsum
from pyspamsum._pure import hash as ref_hash

assert pyspamsum.IMPLEMENTATION == 'cython', 'build the extension first'


def seeded(seed, size):
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


DOC = b'Incident report: the backup job finished with warnings.\n' * 60
DOC_EDIT = DOC.replace(b'warnings', b'errors')

# --- realistic near-duplicate scenarios: LOCALIZED edits only -----------

# A) document with unique lines; one word changed in one line
lines = [(b'The quick brown fox jumps over the lazy dog. '
          b'Entry %04d of the running log.\n' % i) for i in range(96)]
DOC2 = b''.join(lines)
DOC2_EDIT = DOC2.replace(b'Entry 0050', b'Entry 0050!!', 1)

# B) same bytes with a chunk appended at the end (classic download scenario)
R64K = seeded(77, 65536)
APPENDED = R64K + seeded(78, 3000)

# C) random blob with 10 bytes changed in one small region
BASE8K = seeded(91, 8192)
m = bytearray(BASE8K)
rng_c = random.Random(92)
for _ in range(10):
    m[rng_c.randrange(4000, 4100)] = rng_c.getrandbits(8)
MUT10 = bytes(m)

vectors = [
    ('empty', b''),
    ('one-byte', b'A'),
    ('abc', b'abc'),
    ('hello-world', b'hello world'),
    ('pangram', b'The quick brown fox jumps over the lazy dog'),
    ('zeros-1000', b'\x00' * 1000),
    ('a-10000', b'a' * 10000),
    ('pattern-10240', bytes(range(256)) * 40),
    ('random-4096', seeded(42, 4096)),
    ('random-200000', seeded(43, 200000)),
    ('doc2', DOC2),
    ('doc2-edit', DOC2_EDIT),
    ('appended', APPENDED),
    ('mut10', MUT10),
]

failures = 0
for name, data in vectors:
    a, b = pyspamsum.hash(data), ref_hash(data)
    status = 'OK  ' if a == b else 'MISMATCH'
    if a != b:
        failures += 1
    print(f'{status} {name:<16} {a}')
    if a != b:
        print(f'     ref: {b}')

print()
print('--- compare() goldens -------------------------------------------------')
score_doc = pyspamsum.compare(pyspamsum.hash(DOC), pyspamsum.hash(DOC_EDIT))
print('DOC vs DOC_EDIT (edit every line)        :', score_doc)
score_doc2 = pyspamsum.compare(pyspamsum.hash(DOC2), pyspamsum.hash(DOC2_EDIT))
print('DOC2 vs DOC2_EDIT (one localized edit)   :', score_doc2)
score_app = pyspamsum.compare(pyspamsum.hash(R64K), pyspamsum.hash(APPENDED))
print('R64K vs APPENDED (3 KiB appended)        :', score_app)
score_mut = pyspamsum.compare(pyspamsum.hash(BASE8K), pyspamsum.hash(MUT10))
print('BASE8K vs MUT10 (10 bytes changed)       :', score_mut)

rng = random.Random(6)
base = seeded(5, 5000)
mutated = bytearray(base)
for _ in range(100):
    mutated[rng.randrange(len(mutated))] = rng.getrandbits(8)
mutated = bytes(mutated)
score_mut = pyspamsum.compare(pyspamsum.hash(base), pyspamsum.hash(mutated))
print('mutated-random compare  :', score_mut)

a1, b1 = pyspamsum.hash(seeded(1, 4096)), pyspamsum.hash(seeded(2, 4096))
score_unrel = pyspamsum.compare(a1, b1)
print('unrelated compare       :', score_unrel)

tiny = pyspamsum.hash(b'tiny')
large = pyspamsum.hash(b'x' * 100000)
print('tiny hash / large hash  :', tiny, '/', large)
print('block sizes tiny/large  :', tiny.split(':')[0], large.split(':')[0],
      '| compare =', pyspamsum.compare(tiny, large))

print()
print('failures:', failures)
sys.exit(1 if failures else 0)
