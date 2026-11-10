#!/usr/bin/env python3
"""Demo 3 -- near-duplicate detection across files and folders.

Two folder "snapshots" are hashed recursively and compared file by file:
one file got a small localized edit, one log was truncated, one file is
untouched.  Fuzzy hashes keep scoring those pairs high, while a
cryptographic hash (MD5) would change completely.

Run:  python examples/demo_similarity.py
"""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ''):  # plain-script run: make the source tree importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyspamsum

REPORT = b'Incident report: the backup job finished with warnings.\n' * 60
# Unique log lines (real logs vary per request; a repeated single line
# would make the fuzzy hash degenerate).
LOG = b''.join(b'INFO request %05d handled in %02d ms\n' % (i, (i * 7) % 97)
               for i in range(400))
LOG_TRUNC = b''.join(b'INFO request %05d handled in %02d ms\n' % (i, (i * 7) % 97)
                     for i in range(395))
TODO = b'- water plants\n' * 50


def write(root, rel, content):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        a = os.path.join(tmp, 'snapshot_a')
        b = os.path.join(tmp, 'snapshot_b')

        # snapshot A
        write(a, 'docs/report.txt', REPORT)
        write(a, 'logs/app.log', LOG)
        write(a, 'docs/todo.txt', TODO)

        # snapshot B: report edited in one place, log truncated, todo same
        write(b, 'docs/report.txt', REPORT.replace(b'warnings', b'errors', 1))
        write(b, 'logs/app.log', LOG_TRUNC)
        write(b, 'docs/todo.txt', TODO)

        ha = pyspamsum.hash_folder(a)
        hb = pyspamsum.hash_folder(b)

        print('file                 fuzzy score   md5 changed?')
        print('-------------------  -----------   ------------')
        for key in sorted(set(ha) | set(hb)):
            if key in ha and key in hb:
                score = pyspamsum.compare(ha[key], hb[key])
                md5_a = hashlib.md5((Path(a) / key).read_bytes()).hexdigest()
                md5_b = hashlib.md5((Path(b) / key).read_bytes()).hexdigest()
                changed = 'yes' if md5_a != md5_b else 'no'
                print(f'{key:<20}  {score:>6}       {changed}')
            else:
                print(f'{key:<20}  {"-":>6}       missing in one snapshot')

    print()
    print('Fuzzy hashes stay similar when only part of a file changes,')
    print('while MD5/SHA change completely -- that is the point of SpamSum.')


if __name__ == '__main__':
    main()
