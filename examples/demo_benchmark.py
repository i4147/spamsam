#!/usr/bin/env python3
"""Demo 4 -- why the hashing core lives in Cython.

Times the compiled Cython core against the pure-Python reference
implementation (``pyspamsum._pure``) on the same input.

Run:  python examples/demo_benchmark.py
"""
import os
import sys

if __package__ in (None, ''):  # plain-script run: make the source tree importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import time

import pyspamsum
from pyspamsum._pure import hash as pure_hash


def main():
    rng = random.Random(7)
    size = 512 * 1024
    data = bytes(rng.getrandbits(8) for _ in range(size))

    print(f'hashing {size:,} bytes of random data')
    print(f'package backend: {pyspamsum.IMPLEMENTATION}')
    print()

    t0 = time.perf_counter()
    h1 = pure_hash(data)
    t_pure = time.perf_counter() - t0

    t0 = time.perf_counter()
    h2 = pyspamsum.hash(data)
    t_cy = time.perf_counter() - t0

    assert h1 == h2, 'implementations disagree?!'
    print(f'pure python : {t_pure * 1000:8.1f} ms  ({size / t_pure / 1e6:6.1f} MB/s)')
    print(f'cython core : {t_cy * 1000:8.1f} ms  ({size / t_cy / 1e6:6.1f} MB/s)')
    print(f'speedup     : {t_pure / t_cy:8.1f}x')


if __name__ == '__main__':
    main()
