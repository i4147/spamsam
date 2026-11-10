# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
# cython: embedsignature=True
"""Cython implementation of the SpamSum fuzzy-hashing core.

Only the byte-twiddling hot path lives here (block hashing, rolling hash
and block-boundary trigger detection).  Scoring and comparison of finished
hashes stay in pure Python -- see ``pyspamsum.scoring``.

The public functions are drop-in compatible with the original pure-Python
module:

    hash(buf)                 bytes or str -> "blocksize:s1:s2"
    hash_from_file(filename)  file path    -> "blocksize:s1:s2"
    _spamsum(stream, slen)    seekable binary stream (internal API)

The input is still consumed in 64 KiB chunks, so file hashing keeps the
streaming behaviour of the reference implementation.
"""

import os

from cpython.bytes cimport PyBytes_FromStringAndSize

cdef extern from "stdint.h":
    ctypedef unsigned char uint8_t
    ctypedef unsigned int uint32_t
    ctypedef unsigned long long uint64_t
    ctypedef long long int64_t


# ---------------------------------------------------------------------------
# Constants (same values and names as the reference implementation)
# ---------------------------------------------------------------------------
BLOCKSIZE_MIN = 3
SPAMSUM_LENGTH = 64

cdef enum:
    C_BLOCKSIZE_MIN = 3
    C_SPAMSUM_LENGTH = 64
    C_HASH_INIT = 0x27
    C_ROLL_WINDOW = 7
    C_STREAM_BUFF_SIZE = 65536

# Base64 alphabet used for the hash strings
B64_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

# ---------------------------------------------------------------------------
# Lookup tables
#
# They are kept as Python objects for API parity with the reference module
# and mirrored into C arrays for the hot loop.
# ---------------------------------------------------------------------------
f_table = (
    0x00, 0x13, 0x26, 0x39, 0x0c, 0x1f, 0x32, 0x05,
    0x18, 0x2b, 0x3e, 0x11, 0x24, 0x37, 0x0a, 0x1d,
    0x30, 0x03, 0x16, 0x29, 0x3c, 0x0f, 0x22, 0x35,
    0x08, 0x1b, 0x2e, 0x01, 0x14, 0x27, 0x3a, 0x0d,
    0x20, 0x33, 0x06, 0x19, 0x2c, 0x3f, 0x12, 0x25,
    0x38, 0x0b, 0x1e, 0x31, 0x04, 0x17, 0x2a, 0x3d,
    0x10, 0x23, 0x36, 0x09, 0x1c, 0x2f, 0x02, 0x15,
    0x28, 0x3b, 0x0e, 0x21, 0x34, 0x07, 0x1a, 0x2d
)

sum_table = [
    [f_table[a] ^ b for b in range(0, 64)] for a in range(0, 64)
]

byte_table = [
    [sum_table[h][b & 0x3F] for h in range(0, 64)] for b in range(0, 256)
]


cdef uint8_t _F_TABLE[64]
cdef uint8_t _BYTE_TABLE[256][64]
cdef uint8_t _B64[64]

# C-level 32-bit mask (0xFFFFFFFF is a Python object literal, which cannot
# be used inside a nogil function)
cdef uint64_t _MASK32 = 0xFFFFFFFF


cdef void _build_tables():
    cdef int a, b, h
    cdef bytes b64b = B64_ALPHABET.encode('ascii')
    for a in range(64):
        _F_TABLE[a] = <uint8_t>f_table[a]
    for h in range(64):
        _B64[h] = <uint8_t>b64b[h]
    for b in range(256):
        for h in range(64):
            # byte_table[b][h] == sum_table[h][b & 0x3F] == f_table[h] ^ (b & 0x3F)
            _BYTE_TABLE[b][h] = <uint8_t>(f_table[h] ^ (b & 0x3F))


# ---------------------------------------------------------------------------
# Incremental hashing state
# ---------------------------------------------------------------------------
cdef struct hash_state_t:
    uint64_t block_size
    uint32_t block_hash1
    uint32_t block_hash2
    int64_t roll_h1            # exact (unmasked) rolling sums, as in the reference
    int64_t roll_h2
    uint64_t roll_h3
    uint32_t rh
    int roll_n
    uint8_t roll_win[C_ROLL_WINDOW]
    uint8_t hs1[66]            # hash_string1 buffer (max 63 chars + 1 final)
    Py_ssize_t hs1_len
    uint8_t hs2[66]            # hash_string2 buffer (max 31 chars + 1 final)
    Py_ssize_t hs2_len
    uint8_t last1
    int has_last1
    uint8_t last2
    int has_last2


cdef void _reset_pass(hash_state_t* st, uint64_t block_size) noexcept nogil:
    cdef int i
    st.block_size = block_size
    st.block_hash1 = C_HASH_INIT
    st.block_hash2 = C_HASH_INIT
    st.roll_h1 = 0
    st.roll_h2 = 0
    st.roll_h3 = 0
    st.roll_n = 0
    for i in range(C_ROLL_WINDOW):
        st.roll_win[i] = 0
    st.hs1_len = 0
    st.hs2_len = 0
    st.has_last1 = 0
    st.has_last2 = 0
    # NOTE: st.rh is intentionally *not* reset here -- the reference
    # implementation initialises it once outside of the retry loop.


cdef void _feed(hash_state_t* st, const unsigned char* data, Py_ssize_t n) noexcept nogil:
    cdef Py_ssize_t i
    cdef unsigned int b
    cdef uint32_t bh1 = st.block_hash1
    cdef uint32_t bh2 = st.block_hash2
    cdef int64_t h1 = st.roll_h1
    cdef int64_t h2 = st.roll_h2
    cdef uint64_t h3 = st.roll_h3
    cdef uint32_t rh = st.rh
    cdef int rn = st.roll_n
    cdef uint64_t bs = st.block_size
    cdef uint64_t bs2 = st.block_size * 2
    cdef Py_ssize_t len1 = st.hs1_len
    cdef Py_ssize_t len2 = st.hs2_len

    for i in range(n):
        b = data[i]

        # block hashes (6-bit table walk)
        bh1 = _BYTE_TABLE[b][bh1]
        bh2 = _BYTE_TABLE[b][bh2]

        # rolling hash
        h2 = h2 - h1 + (7 * b)
        h1 = h1 + b - st.roll_win[rn]
        st.roll_win[rn] = <uint8_t>b
        rn += 1
        if rn == C_ROLL_WINDOW:
            rn = 0
        h3 = ((h3 << 5) & _MASK32) ^ b
        rh = <uint32_t>((<uint64_t>(h1 + h2) + h3) & _MASK32)

        # trigger: end of a block
        if (rh % bs) == (bs - 1):
            st.last1 = _B64[bh1]
            st.has_last1 = 1
            if len1 < (C_SPAMSUM_LENGTH - 1):
                st.hs1[len1] = _B64[bh1]
                len1 += 1
                bh1 = C_HASH_INIT
                st.has_last1 = 0
            # trigger: end of a double-size block
            if (rh % bs2) == (bs2 - 1):
                st.last2 = _B64[bh2]
                st.has_last2 = 1
                if len2 < ((C_SPAMSUM_LENGTH // 2) - 1):
                    st.hs2[len2] = _B64[bh2]
                    len2 += 1
                    bh2 = C_HASH_INIT
                    st.has_last2 = 0

    st.block_hash1 = bh1
    st.block_hash2 = bh2
    st.roll_h1 = h1
    st.roll_h2 = h2
    st.roll_h3 = h3
    st.rh = rh
    st.roll_n = rn
    st.hs1_len = len1
    st.hs2_len = len2


cdef str _finish(hash_state_t* st):
    cdef bytes s1 = PyBytes_FromStringAndSize(<char*>st.hs1, st.hs1_len)
    cdef bytes s2 = PyBytes_FromStringAndSize(<char*>st.hs2, st.hs2_len)
    cdef bytes t1
    cdef bytes t2
    if st.rh != 0:
        t1 = PyBytes_FromStringAndSize(<char*>&_B64[st.block_hash1], 1)
        t2 = PyBytes_FromStringAndSize(<char*>&_B64[st.block_hash2], 1)
    else:
        if st.has_last1:
            t1 = PyBytes_FromStringAndSize(<char*>&st.last1, 1)
        else:
            t1 = b''
        if st.has_last2:
            t2 = PyBytes_FromStringAndSize(<char*>&st.last2, 1)
        else:
            t2 = b''
    return '%d:%s:%s' % (st.block_size,
                         (s1 + t1).decode('ascii'),
                         (s2 + t2).decode('ascii'))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def hash(buf):
    """hash(buf) -> str

    Return the SpamSum fuzzy hash of *buf*.

    *buf* may be ``bytes`` or ``str`` (a str is UTF-8 encoded first).
    The result has the form ``"blocksize:hash1:hash2"``.
    """
    cdef bytes data
    if isinstance(buf, bytes):
        data = <bytes>buf
    elif isinstance(buf, str):
        data = (<str>buf).encode('utf-8')
    else:
        raise TypeError('Argument must be of bytes or string type, not %r' % type(buf))
    return _spamsum_bytes(data)


def hash_from_file(filename):
    """hash_from_file(filename) -> str

    Return the SpamSum fuzzy hash of the file at *filename* (a str path).
    The file is read in 64 KiB chunks; no more than one pass plus possible
    block-size retries, so very large files are handled in constant memory.
    """
    cdef object f
    cdef Py_ssize_t fsize
    if not isinstance(filename, str):
        raise TypeError('Argument must be of string type, not %r' % type(filename))
    if not os.path.isfile(filename):
        raise IOError('File not found')
    if not os.access(filename, os.R_OK):
        raise IOError('File is not readable')
    fsize = os.stat(filename).st_size
    f = open(filename, 'rb')
    try:
        return _spamsum(f, fsize)
    finally:
        f.close()


def _spamsum(stream, slen):
    """_spamsum(stream, slen) -> str

    Internal, reference-compatible API: hash a seekable binary stream of
    *slen* bytes.  Kept public so tests and tools can hash any seekable
    stream object.
    """
    cdef hash_state_t st
    cdef Py_ssize_t slen_ = slen
    cdef uint64_t bs = C_BLOCKSIZE_MIN
    cdef bytearray buffer
    cdef const unsigned char[::1] bmv
    cdef const unsigned char* ptr
    cdef object readinto
    cdef Py_ssize_t n
    cdef object chunk

    if slen_ < 0:
        slen_ = 0
    while (bs * C_SPAMSUM_LENGTH) < slen_:
        bs = bs * 2

    st.rh = 0
    readinto = getattr(stream, 'readinto', None)
    buffer = bytearray(C_STREAM_BUFF_SIZE)
    bmv = buffer
    while True:
        if bs < C_BLOCKSIZE_MIN:
            raise RuntimeError('Calculated block size is too small')
        _reset_pass(&st, bs)
        stream.seek(0)
        if readinto is not None:
            while True:
                n = readinto(buffer)
                if not n:
                    break
                ptr = &bmv[0]
                with nogil:
                    _feed(&st, ptr, n)
        else:
            while True:
                chunk = stream.read(C_STREAM_BUFF_SIZE)
                if not chunk:
                    break
                _feed_object(&st, chunk)
        if bs > C_BLOCKSIZE_MIN and st.hs1_len < (C_SPAMSUM_LENGTH // 2):
            bs = bs // 2
        else:
            break
    return _finish(&st)


cdef str _spamsum_bytes(bytes data):
    cdef hash_state_t st
    cdef Py_ssize_t n = len(data)
    cdef uint64_t bs = C_BLOCKSIZE_MIN
    cdef const unsigned char[::1] mv
    cdef const unsigned char* ptr

    while (bs * C_SPAMSUM_LENGTH) < n:
        bs = bs * 2

    st.rh = 0
    mv = data
    while True:
        if bs < C_BLOCKSIZE_MIN:
            raise RuntimeError('Calculated block size is too small')
        _reset_pass(&st, bs)
        if n > 0:
            ptr = &mv[0]
            with nogil:
                _feed(&st, ptr, n)
        if bs > C_BLOCKSIZE_MIN and st.hs1_len < (C_SPAMSUM_LENGTH // 2):
            bs = bs // 2
        else:
            break
    return _finish(&st)


cdef void _feed_object(hash_state_t* st, object chunk):
    cdef const unsigned char[::1] cmv = chunk
    cdef Py_ssize_t n = len(chunk)
    if n > 0:
        _feed(st, &cmv[0], n)


_build_tables()
