"""Pure-Python reference implementation of SpamSum.

This file is the original, untouched implementation.  It serves two
purposes:

* test oracle -- the pytest suite asserts that the compiled Cython core
  produces byte-for-byte identical hashes;
* automatic fallback backend -- if the Cython extension has not been built
  for the running interpreter, ``pyspamsum`` transparently uses this module
  (see ``pyspamsum/_imp.py``).
"""

import os
from itertools import cycle
from io import BytesIO

BLOCKSIZE_MIN = 3
SPAMSUM_LENGTH = 64
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


def _spamsum(stream, slen):
	STREAM_BUFF_SIZE = 65536
	HASH_INIT = 0x27
	ROLL_WINDOW = 7
	B64 = tuple('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/')
	bs = BLOCKSIZE_MIN
	while (bs * SPAMSUM_LENGTH) < slen:
		bs = bs * 2
	block_size = bs
	rh = 0
	while True:
		if block_size < BLOCKSIZE_MIN:
			raise RuntimeError('Calculated block size is too small')
		roll_win = [0] * ROLL_WINDOW
		roll_h1 = roll_h2 = roll_h3 = int()
		roll_n = int()
		roll_c = cycle(range(ROLL_WINDOW))
		block_hash1 = block_hash2 = int(HASH_INIT)
		hash_string1 = hash_string2 = str()
		last_char1 = last_char2 = str()
		stream.seek(0)
		buf = stream.read(STREAM_BUFF_SIZE)
		while buf:
			for b in buf:
				block_hash1 = byte_table[b][block_hash1]
				block_hash2 = byte_table[b][block_hash2]
				roll_n = next(roll_c)
				roll_h2 = roll_h2 - roll_h1 + (ROLL_WINDOW * b)
				roll_h1 = roll_h1 + b - roll_win[roll_n]
				roll_win[roll_n] = b
				roll_h3 = (roll_h3 << 5) & 0xFFFFFFFF
				roll_h3 ^= b
				rh = (roll_h1 + roll_h2 + roll_h3) & 0xFFFFFFFF
				if (rh % block_size) == (block_size - 1):
					last_char1 = B64[block_hash1]
					if len(hash_string1) < (SPAMSUM_LENGTH - 1):
						hash_string1 += B64[block_hash1]
						block_hash1 = HASH_INIT
						last_char1 = str()
					if (rh % (block_size * 2)) == ((block_size * 2) - 1):
						last_char2 = B64[block_hash2]
						if len(hash_string2) < ((SPAMSUM_LENGTH // 2) - 1):
							hash_string2 += B64[block_hash2]
							block_hash2 = HASH_INIT
							last_char2 = str()
			buf = stream.read(STREAM_BUFF_SIZE)
		if block_size > BLOCKSIZE_MIN and len(hash_string1) < (SPAMSUM_LENGTH // 2):
			block_size = (block_size // 2)
		else:
			if rh != 0:
				hash_string1 += B64[block_hash1]
				hash_string2 += B64[block_hash2]
			else:
				hash_string1 += last_char1
				hash_string2 += last_char2
			break
	return '{0}:{1}:{2}'.format(block_size, hash_string1, hash_string2)


def hash(buf):
	if isinstance(buf, bytes):
		pass
	elif isinstance(buf, str):
		buf = buf.encode()
	else:
		raise TypeError('Argument must be of bytes or string type, not %r' % type(buf))
	return _spamsum(BytesIO(buf), len(buf))


def hash_from_file(filename):
	if not isinstance(filename, str):
		raise TypeError('Argument must be of string type, not %r' % type(filename))
	if not os.path.isfile(filename):
		raise IOError('File not found')
	if not os.access(filename, os.R_OK):
		raise IOError('File is not readable')
	fsize = os.stat(filename).st_size
	return _spamsum(open(filename, 'rb'), fsize)


if __name__ == '__main__':
	import sys
	if len(sys.argv) > 1:
		print(hash_from_file(sys.argv[1]))
	else:
		with open(0, 'rb') as f:
			print(hash(f.read()))
