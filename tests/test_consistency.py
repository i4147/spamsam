"""Cross-implementation consistency tests.

The compiled Cython core must produce byte-for-byte identical hashes to
the pure-Python reference implementation (``pyspamsum/_pure.py``) for
every input -- sizes around the 64 KiB streaming buffer, single bytes,
repetitive patterns and feeds split across many small chunks.
"""
import random
from io import BytesIO

import pytest

import pyspamsum
from pyspamsum._pure import hash as reference_hash


def seeded_bytes(seed, size):
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


# Sizes include the streaming-buffer boundaries (65535/65536/65537, 131072)
# and block-size boundaries (191/192/193, 255/256, 511/512 ...).
SIZES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 31, 32, 63, 64, 65,
         127, 128, 191, 192, 193, 255, 256, 511, 512, 1023, 1024,
         4095, 4096, 10000, 65535, 65536, 65537, 131072, 200000]


@pytest.mark.parametrize('size', SIZES)
def test_matches_reference(size):
    data = seeded_bytes(2024 + size, size)
    assert pyspamsum.hash(data) == reference_hash(data)


def test_all_single_byte_inputs():
    for b in range(256):
        data = bytes([b])
        assert pyspamsum.hash(data) == reference_hash(data)


@pytest.mark.parametrize('data', [
    b'\x00' * 999,
    b'\x00' * 65536,
    b'a' * 4096,
    b'ab' * 2048,
    b'xyz' * 1000,
    b'\xff' * 65537,
    bytes(range(256)) * 64,
    b'abcdefgh' * 13 + b'X' + b'abcdefgh' * 13,
])
def test_repetitive_patterns(data):
    assert pyspamsum.hash(data) == reference_hash(data)


def test_lowlevel_stream_api_matches_hash():
    data = seeded_bytes(11, 5000)
    stream_hash = pyspamsum._imp._spamsum(BytesIO(data), len(data))
    assert stream_hash == pyspamsum.hash(data)


def test_streaming_in_small_chunks_matches_hash():
    class TinyStream:
        """Minimal stream handing out only 17 bytes per readinto call."""

        def __init__(self, payload):
            self._bio = BytesIO(payload)

        def seek(self, pos):
            return self._bio.seek(pos)

        def readinto(self, buf):
            chunk = self._bio.read(min(17, len(buf)))
            buf[:len(chunk)] = chunk
            return len(chunk)

    data = seeded_bytes(12, 5000)
    assert pyspamsum._imp._spamsum(TinyStream(data), len(data)) \
        == pyspamsum.hash(data)


def test_cython_backend_is_active():
    assert pyspamsum.IMPLEMENTATION == 'cython'


@pytest.mark.skipif(pyspamsum.IMPLEMENTATION != 'cython',
                    reason='Cython core not built')
def test_cython_tables_match_reference():
    import importlib
    # pyspamsum._spamsum (the function) shadows the submodule attribute in
    # the package namespace, so fetch the module via sys.modules instead.
    from pyspamsum import _pure as ref
    core = importlib.import_module('pyspamsum._spamsum')
    assert tuple(core.f_table) == tuple(ref.f_table)
    assert core.sum_table == ref.sum_table
    assert core.byte_table == ref.byte_table
    assert core.BLOCKSIZE_MIN == ref.BLOCKSIZE_MIN == 3
    assert core.SPAMSUM_LENGTH == ref.SPAMSUM_LENGTH == 64
