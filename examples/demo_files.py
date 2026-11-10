#!/usr/bin/env python3
"""Demo 2 -- hashing files and folders (recursively).

Run:  python examples/demo_files.py [path]

Without an argument a small demo tree is created in a temporary directory,
hashed, and cleaned up again.
"""
import os
import sys

if __package__ in (None, ''):  # plain-script run: make the source tree importable
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile

import pyspamsum


def build_demo_tree(root):
    files = {
        'report.txt': b'Quarterly report: revenue is up 12 percent.\n' * 40,
        'notes.md': b'# Notes\n- call accounting\n- order coffee\n' * 12,
        'data/blob.bin': bytes(range(256)) * 64,
        'data/logs/app.log': b'INFO service started\n' * 500,
        'data/logs/app.log.1': b'INFO service started\n' * 498,   # near-duplicate
    }
    for rel, content in files.items():
        path = os.path.join(root, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(content)


def main():
    tmp = None
    if len(sys.argv) > 1:
        root = sys.argv[1]
    else:
        tmp = tempfile.TemporaryDirectory()
        root = tmp.name
        build_demo_tree(root)
        print(f'(demo tree created in {root})\n')

    target = os.path.join(root, 'report.txt')

    print('-- single file: hash_file ----------------------------------')
    print(target)
    print(pyspamsum.hash_file(target))
    print()

    print('-- whole folder, recursive: hash_folder ---------------------')
    for rel, h in pyspamsum.hash_folder(root).items():
        print(f'{h:<46} {rel}')
    print()

    print('-- top level only (recursive=False) -------------------------')
    for rel, h in pyspamsum.hash_folder(root, recursive=False).items():
        print(f'{h:<46} {rel}')
    print()

    print('-- hash_path dispatches: file -> str, folder -> dict --------')
    one = pyspamsum.hash_path(target)
    print(f'{type(one).__name__:<5} {one}')
    many = pyspamsum.hash_path(root)
    print(f'{type(many).__name__:<5} {len(many)} entries')

    if tmp is not None:
        tmp.cleanup()


if __name__ == '__main__':
    main()
