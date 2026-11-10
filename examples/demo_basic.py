#!/usr/bin/env python3
"""Demo 1 -- hashing strings and scoring their similarity.

Run:  python examples/demo_basic.py
"""
import os
import sys

if __package__ in (None, ''):  # plain-script run: make the source tree importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random

import pyspamsum


def main():
    print('pyspamsum backend :', pyspamsum.IMPLEMENTATION)
    print()

    samples = [
        'The quick brown fox jumps over the lazy dog',
        'The quick brown fox jumps over the lazy dog!',      # one byte appended
        'The quick brown fox leaps over the lazy dog',       # one word changed
        'Totally different content for a change of pace!!',
    ]
    hashes = [pyspamsum.hash(s) for s in samples]

    print('-- fuzzy hashes -------------------------------------------')
    for text, h in zip(samples, hashes):
        print(f'{h:<42} {text[:40]!r}')
    print()

    print('-- pairwise similarity scores (0..100) --------------------')
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            score = pyspamsum.compare(hashes[i], hashes[j])
            print(f'score({i}, {j}) = {score:>3}   {samples[i][:28]!r} vs {samples[j][:28]!r}')
    print()
    print('Note: SpamSum similarity is designed for inputs of at least a few')
    print('kilobytes -- for tiny inputs the score is capped proportionally to')
    print('the block size, as seen above.')
    print()

    # a realistic pair: ~6 KB document with ONE localized edit
    doc = b''.join(
        b'The quick brown fox jumps over the lazy dog. '
        b'Entry %04d of the running log.\n' % i
        for i in range(96)
    )
    edited = doc.replace(b'Entry 0050', b'Entry 0050!!', 1)
    unrelated = bytes(random.Random(1).getrandbits(8) for _ in range(len(doc)))

    print('-- larger documents (~6 KB) --------------------------------')
    print('hash(doc)      =', pyspamsum.hash(doc))
    print('hash(edited)   =', pyspamsum.hash(edited))
    print('hash(unrelated)=', pyspamsum.hash(unrelated))
    print()
    print('score(doc, doc)          =', pyspamsum.compare(pyspamsum.hash(doc), pyspamsum.hash(doc)))
    print('score(doc, edited)       =', pyspamsum.compare(pyspamsum.hash(doc), pyspamsum.hash(edited)))
    print('score(doc, unrelated)    =', pyspamsum.compare(pyspamsum.hash(doc), pyspamsum.hash(unrelated)))


if __name__ == '__main__':
    main()
