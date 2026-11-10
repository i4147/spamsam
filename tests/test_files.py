"""Tests for file and folder hashing (hash_from_file / hash_file /
hash_folder / hash_path).
"""
import os

import pytest

import pyspamsum

requires_non_root = pytest.mark.skipif(
    hasattr(os, 'geteuid') and os.geteuid() == 0,
    reason='file permissions are not enforced for root',
)


def seeded_bytes(seed, size):
    import random
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


def make_tree(base):
    """Create a small directory tree with files on three levels."""
    (base / 'a.txt').write_bytes(b'alpha')
    (base / 'b.txt').write_bytes(b'bravo' * 100)
    sub = base / 'sub'
    sub.mkdir()
    (sub / 'c.bin').write_bytes(bytes(range(256)) * 8)
    deep = sub / 'deep'
    deep.mkdir()
    (deep / 'd.txt').write_bytes(b'delta content\n' * 10)
    (base / 'empty_dir').mkdir()          # no files -> contributes nothing


# --------------------------------------------------------------- hash_from_file

def test_hash_from_file_matches_hash_of_bytes(tmp_path):
    data = seeded_bytes(21, 5000)
    p = tmp_path / 'sample.bin'
    p.write_bytes(data)
    assert pyspamsum.hash_from_file(str(p)) == pyspamsum.hash(data)


def test_hash_from_file_empty(tmp_path):
    p = tmp_path / 'empty.bin'
    p.write_bytes(b'')
    assert pyspamsum.hash_from_file(str(p)) == '3::'


def test_hash_from_file_missing(tmp_path):
    with pytest.raises(IOError):
        pyspamsum.hash_from_file(str(tmp_path / 'nope.bin'))


def test_hash_from_file_rejects_directory(tmp_path):
    with pytest.raises(IOError):
        pyspamsum.hash_from_file(str(tmp_path))


def test_hash_from_file_rejects_non_string():
    with pytest.raises(TypeError):
        pyspamsum.hash_from_file(123)


@requires_non_root
def test_hash_from_file_unreadable(tmp_path):
    p = tmp_path / 'secret.bin'
    p.write_bytes(b'x')
    os.chmod(p, 0)
    try:
        with pytest.raises(IOError):
            pyspamsum.hash_from_file(str(p))
    finally:
        os.chmod(p, 0o644)


# ------------------------------------------------------------------- hash_file

def test_hash_file_accepts_pathlib_and_str(tmp_path):
    data = seeded_bytes(22, 1234)
    p = tmp_path / 'x.bin'
    p.write_bytes(data)
    assert pyspamsum.hash_file(p) == pyspamsum.hash(data)
    assert pyspamsum.hash_file(str(p)) == pyspamsum.hash(data)


# ----------------------------------------------------------------- hash_folder

def test_hash_folder_recursive(tmp_path):
    make_tree(tmp_path)
    result = pyspamsum.hash_folder(tmp_path)
    assert set(result) == {'a.txt', 'b.txt', 'sub/c.bin', 'sub/deep/d.txt'}
    assert result['a.txt'] == pyspamsum.hash(b'alpha')
    assert result['b.txt'] == pyspamsum.hash(b'bravo' * 100)
    assert result['sub/c.bin'] == pyspamsum.hash(bytes(range(256)) * 8)
    assert result['sub/deep/d.txt'] == pyspamsum.hash(b'delta content\n' * 10)


def test_hash_folder_non_recursive(tmp_path):
    make_tree(tmp_path)
    result = pyspamsum.hash_folder(tmp_path, recursive=False)
    assert set(result) == {'a.txt', 'b.txt'}


def test_hash_folder_empty_dir(tmp_path):
    assert pyspamsum.hash_folder(tmp_path) == {}


def test_hash_folder_deterministic(tmp_path):
    make_tree(tmp_path)
    assert pyspamsum.hash_folder(tmp_path) == pyspamsum.hash_folder(tmp_path)


def test_hash_folder_missing(tmp_path):
    with pytest.raises(IOError):
        pyspamsum.hash_folder(tmp_path / 'missing')


def test_hash_folder_rejects_non_string():
    with pytest.raises(TypeError):
        pyspamsum.hash_folder(42)


@requires_non_root
def test_hash_folder_on_error_callback(tmp_path):
    (tmp_path / 'good.txt').write_bytes(b'good data here')
    bad = tmp_path / 'bad.txt'
    bad.write_bytes(b'cannot read this one')
    os.chmod(bad, 0)
    try:
        errors = []
        result = pyspamsum.hash_folder(
            tmp_path, on_error=lambda path, exc: errors.append((path, exc)))
        assert set(result) == {'good.txt'}
        assert len(errors) == 1
        assert errors[0][0].endswith('bad.txt')
        # without a callback the error is raised instead
        with pytest.raises(IOError):
            pyspamsum.hash_folder(tmp_path)
    finally:
        os.chmod(bad, 0o644)


# ------------------------------------------------------------------- hash_path

def test_hash_path_dispatches_file_to_string(tmp_path):
    p = tmp_path / 'file.bin'
    p.write_bytes(b'some file payload')
    result = pyspamsum.hash_path(p)
    assert isinstance(result, str)
    assert result == pyspamsum.hash(b'some file payload')


def test_hash_path_dispatches_folder_to_dict(tmp_path):
    make_tree(tmp_path)
    result = pyspamsum.hash_path(tmp_path)
    assert isinstance(result, dict)
    assert set(result) == {'a.txt', 'b.txt', 'sub/c.bin', 'sub/deep/d.txt'}


def test_hash_path_forwards_kwargs_to_hash_folder(tmp_path):
    make_tree(tmp_path)
    result = pyspamsum.hash_path(tmp_path, recursive=False)
    assert set(result) == {'a.txt', 'b.txt'}


def test_hash_path_missing(tmp_path):
    with pytest.raises(IOError):
        pyspamsum.hash_path(tmp_path / 'nope')
