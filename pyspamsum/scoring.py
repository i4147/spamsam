"""Scoring and comparison of SpamSum fuzzy hashes -- pure Python.

This part of the algorithm is not performance critical (it works on the
short base64 hash strings, never on raw data), so it stays in plain
Python exactly as in the original implementation.  Only the hashing core
itself lives in the Cython extension.

The score returned by :func:`compare` roughly means::

    100  identical (after removing repeated sequences)
     ~90+  near-duplicates (small edits, appended data ...)
      1+  weak similarity
      0  unrelated inputs (or incompatible block sizes)
"""

SPAMSUM_LENGTH = 64
BLOCKSIZE_MIN = 3
ROLL_WINDOW = 7


def _levenshtein(s, t):
    """Classic edit distance between two strings (row-pair DP)."""
    if s == t: return 0
    elif len(s) == 0: return len(t)
    elif len(t) == 0: return len(s)
    v0 = [None] * (len(t) + 1)
    v1 = [None] * (len(t) + 1)
    for i in range(len(v0)):
        v0[i] = i
    for i in range(len(s)):
        v1[0] = i + 1
        for j in range(len(t)):
            cost = 0 if s[i] == t[j] else 1
            v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
        for j in range(len(v0)):
            v0[j] = v1[j]
    return v1[len(t)]


def _common_substring(s1, s2):
    """True when the two strings share a common substring of length >= 7."""
    ROLL_WINDOW = 7
    m = len(s1)
    n = len(s2)
    res = 0
    for i in range(m):
        for j in range(n):
            cur = 0
            while (i + cur) < m and (j + cur) < n and s1[i + cur] == s2[j + cur]:
                cur += 1
            res = max(res, cur)
    return True if res >= ROLL_WINDOW else False


def _score_strings(s1, s2, block_size):
    if _common_substring(s1, s2) == False:
        return 0
    score = _levenshtein(s1, s2)
    score = (score * SPAMSUM_LENGTH) // (len(s1) + len(s2))
    score = (100 * score) // SPAMSUM_LENGTH
    score = 100 - score
    if score > (block_size // BLOCKSIZE_MIN * min([len(s1), len(s2)])):
        score = block_size // BLOCKSIZE_MIN * min([len(s1), len(s2)])
    return score


def _strip_sequences(s):
    """Remove runs of 3+ identical characters (spamsum's repeat removal)."""
    r = s[:3]
    for i in range(3, len(s)):
        if (s[i] != s[i-1] or s[i] != s[i-2] or s[i] != s[i-3]):
            r += s[i]
    return r


def compare(hash1, hash2):
    """compare(hash1, hash2) -> int

    Compare two SpamSum hash strings and return a similarity score in the
    range 0..100 (100 == identical).
    """
    if not (isinstance(hash1, str) and isinstance(hash2, str)):
        raise TypeError('Arguments must be of string type')
    try:
        hash1_bs, hash1_s1, hash1_s2 = hash1.split(':')
        hash2_bs, hash2_s1, hash2_s2 = hash2.split(':')
        hash1_bs = int(hash1_bs)
        hash2_bs = int(hash2_bs)
    except ValueError:
        raise ValueError('Invalid hash format') from None
    if hash1_bs != hash2_bs and hash1_bs != (hash2_bs * 2) and hash2_bs != (hash1_bs * 2):
        return 0
    hash1_s1 = _strip_sequences(hash1_s1)
    hash1_s2 = _strip_sequences(hash1_s2)
    hash2_s1 = _strip_sequences(hash2_s1)
    hash2_s2 = _strip_sequences(hash2_s2)
    if hash1_bs == hash2_bs and hash1_s1 == hash2_s1:
        return 100
    if hash1_bs == hash2_bs:
        score1 = _score_strings(hash1_s1, hash2_s1, hash1_bs)
        score2 = _score_strings(hash1_s2, hash2_s2, hash2_bs*2)
        score = int(max([score1, score2]))
        return score
    elif hash1_bs == (hash2_bs * 2):
        score = int(_score_strings(hash1_s1, hash2_s2, hash1_bs))
        return score
    else:
        score = int(_score_strings(hash1_s2, hash2_s1, hash2_bs))
        return score
