"""Tests for pyspamsum.compare and the scoring helpers.

All expected scores are deterministic golden values generated with the
reference implementation.
"""
import random

import pytest

import pyspamsum
from pyspamsum import compare
from pyspamsum._pure import hash as reference_hash
from pyspamsum.scoring import _strip_sequences


def seeded_bytes(seed, size):
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


# A document with unique lines, and a near-duplicate differing in ONE line.
DOC2 = b''.join(
    b'The quick brown fox jumps over the lazy dog. Entry %04d of the running log.\n' % i
    for i in range(96)
)
DOC2_EDIT = DOC2.replace(b'Entry 0050', b'Entry 0050!!', 1)

# Same bytes with a chunk appended at the end (download / log-growth case).
R64K = seeded_bytes(77, 65536)
APPENDED = R64K + seeded_bytes(78, 3000)

# Random blob with 10 bytes changed within one small region.
BASE8K = seeded_bytes(91, 8192)
_m = bytearray(BASE8K)
_rng = random.Random(92)
for _ in range(10):
    _m[_rng.randrange(4000, 4100)] = _rng.getrandbits(8)
MUT10 = bytes(_m)

# The same short phrase repeated: one edit per repetition *scrambles every
# block*, which drops the score to 0 -- a known property of block-based
# fuzzy hashing (edits must be localized relative to the block size).
REPEATED = b'Incident report: the backup job finished with warnings.\n' * 60
REPEATED_EDIT = REPEATED.replace(b'warnings', b'errors')


def h(data):
    return pyspamsum.hash(data)


def test_identical_input_scores_100():
    data = seeded_bytes(5, 5000)
    assert compare(h(data), h(data)) == 100


def test_localized_edit_scores_100():
    assert compare(h(DOC2), h(DOC2_EDIT)) == 100
    # the pure-Python oracle agrees
    assert compare(reference_hash(DOC2), reference_hash(DOC2_EDIT)) == 100


def test_appended_data_scores_97():
    assert compare(h(R64K), h(APPENDED)) == 97


def test_small_region_mutation_scores_99():
    assert compare(h(BASE8K), h(MUT10)) == 99


def test_distributed_edits_score_zero():
    assert compare(h(REPEATED), h(REPEATED_EDIT)) == 0


def test_unrelated_inputs_score_zero():
    assert compare(h(seeded_bytes(1, 4096)), h(seeded_bytes(2, 4096))) == 0


def test_incompatible_block_sizes_score_zero():
    small = h(seeded_bytes(3, 4096))       # block size 96
    large = h(seeded_bytes(4, 200000))     # block size 6144
    bs_small = int(small.split(':')[0])
    bs_large = int(large.split(':')[0])
    assert bs_small != bs_large
    assert bs_small * 2 != bs_large and bs_large * 2 != bs_small
    assert compare(small, large) == 0


def test_score_bounds_over_many_mutations():
    rng = random.Random(5)
    base = seeded_bytes(6, 5000)
    base_h = h(base)
    for _ in range(25):
        mutated = bytearray(base)
        for _ in range(rng.randrange(0, 20)):
            mutated[rng.randrange(len(mutated))] = rng.getrandbits(8)
        score = compare(base_h, h(bytes(mutated)))
        assert 0 <= score <= 100


def test_invalid_format_raises_value_error():
    valid = '3:uG:uG'
    for bad in ['', 'nonsense', 'a:b:c', '1:2', '1:2:3:4', 'x:y:z', ':']:
        with pytest.raises(ValueError):
            compare(bad, valid)
        with pytest.raises(ValueError):
            compare(valid, bad)


def test_compare_rejects_non_string():
    with pytest.raises(TypeError):
        compare(1, '3:uG:uG')
    with pytest.raises(TypeError):
        compare('3:uG:uG', None)
    with pytest.raises(TypeError):
        compare(h(b'abc'), None)


def test_identical_short_hash_strings_score_100():
    assert compare('3:abcdef:gh', '3:abcdef:gh') == 100


def test_strip_sequences():
    assert _strip_sequences('') == ''
    assert _strip_sequences('ab') == 'ab'
    # The first three characters are always kept; afterwards a character is
    # dropped only when it extends an already-identical run of three.
    assert _strip_sequences('aaabbbcaa') == 'aaabbbcaa'   # runs of 3 survive
    assert _strip_sequences('aaaab') == 'aaab'            # 4th 'a' is dropped
    assert _strip_sequences('xaaay') == 'xaaay'   # differs from 'x' 3 back
    assert _strip_sequences('xaaaay') == 'xaaay'  # 5th 'a' matches 3 back
