"""Filesystem helpers built on top of the hashing core.

* ``hash_file``   -- hash a single file (accepts str / os.PathLike)
* ``hash_folder`` -- hash every regular file in a folder, recursively
* ``hash_path``   -- dispatch: file -> hash string, folder -> {path: hash}

Directory walking is I/O bound, so folder traversal is plain Python;
each individual file is hashed by the compiled Cython core.
"""

import os

from ._imp import hash_from_file

__all__ = ['hash_file', 'hash_folder', 'hash_path']


def _as_path(path):
    if isinstance(path, os.PathLike):
        path = os.fspath(path)
    if not isinstance(path, str):
        raise TypeError('Argument must be of string type, not %r' % type(path))
    return path


def hash_file(path):
    """Return the SpamSum hash of the file at *path*.

    Convenience wrapper around :func:`pyspamsum.hash_from_file` that also
    accepts :class:`pathlib.Path` objects.
    """
    return hash_from_file(_as_path(path))


def _hash_one(path, on_error):
    try:
        return hash_from_file(path)
    except OSError as exc:
        if on_error is None:
            raise
        on_error(path, exc)
        return None


def hash_folder(path, *, recursive=True, on_error=None):
    """Hash every regular file under the folder *path*.

    Returns a dict mapping each file's path (relative to *path*, always
    with ``/`` separators) to its SpamSum hash string::

        {'docs/report.txt': '96:mHmHmHmH:mHmHmHmHmHmH'}

    There is deliberately no single hash for a whole folder: fuzzy hashes
    are only meaningful per byte stream, so a folder is hashed file by
    file and the mapping can be compared folder-against-folder.

    Parameters
    ----------
    path : str or os.PathLike
        Folder to scan.
    recursive : bool
        Also descend into subfolders (default ``True``).
    on_error : callable(path, exception), optional
        Called for every file that cannot be read and every folder that
        cannot be listed; the offending entry is skipped.  When omitted
        (default) the first unreadable entry raises :class:`IOError`.

    Notes
    -----
    * Symbolic links are not followed into directories (no cycles); links
      pointing at regular files are hashed through their target.
    * Non-regular files (devices, sockets, fifos, broken links) are skipped.
    * Traversal is sorted, so results are deterministic.
    """
    path = _as_path(path)
    if not os.path.isdir(path):
        raise IOError('Folder not found')
    if not os.access(path, os.R_OK | os.X_OK):
        raise IOError('Folder is not readable')

    def walk_error(err):
        if on_error is None:
            raise err
        on_error(err.filename or path, err)

    results = {}
    if recursive:
        for dirpath, dirnames, filenames in os.walk(path, followlinks=False,
                                                    onerror=walk_error):
            dirnames.sort()                      # deterministic traversal order
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                if not os.path.isfile(full):     # skip sockets, fifos, broken links
                    continue
                digest = _hash_one(full, on_error)
                if digest is not None:
                    rel = os.path.relpath(full, path).replace(os.sep, '/')
                    results[rel] = digest
    else:
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isfile(full):
                digest = _hash_one(full, on_error)
                if digest is not None:
                    results[name] = digest
    return results


def hash_path(path, **kwargs):
    """Hash *path*: file -> single hash string, folder -> dict of hashes.

    Extra keyword arguments are forwarded to :func:`hash_folder` when
    *path* is a folder (e.g. ``recursive=False``, ``on_error=...``).
    """
    path = _as_path(path)
    if os.path.isfile(path):
        return hash_from_file(path)
    if os.path.isdir(path):
        return hash_folder(path, **kwargs)
    raise IOError('Path not found')
