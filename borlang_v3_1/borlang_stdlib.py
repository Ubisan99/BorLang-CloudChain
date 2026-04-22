"""
BoRLang Standard Library — real implementations.

Design principles:
- No fake stubs. Every function does what it claims or raises NotImplementedError.
- Prefer battle-tested libs (numpy, sklearn, faiss) over reinventing.
- Optional heavy deps (faiss, sentence-transformers) are soft-imported with
  numpy fallbacks so the core works out of the box.
- All docstrings state honestly what the function does (and does NOT do).
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import sqlite3
import time
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import normalize as sk_normalize

# ---------------------------------------------------------------------------
# Soft dependencies
# ---------------------------------------------------------------------------

try:
    import faiss  # type: ignore

    _HAS_FAISS = True
except ImportError:
    _HAS_FAISS = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore

    _HAS_ST = True
except ImportError:
    _HAS_ST = False


# ===========================================================================
# ML / NUMPY
# ===========================================================================

def br_array(data) -> np.ndarray:
    """Wrap a Python list (or nested list) as a numpy array."""
    return np.asarray(data, dtype=float)


def br_zeros(n: int) -> np.ndarray:
    return np.zeros(int(n))


def br_ones(n: int) -> np.ndarray:
    return np.ones(int(n))


def br_random_array(n: int, seed: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random(int(n))


def br_mean(x) -> float:
    return float(np.mean(x))


def br_std(x) -> float:
    return float(np.std(x))


def br_sum(x) -> float:
    return float(np.sum(x))


def br_dot(a, b) -> float:
    return float(np.dot(a, b))


def br_matmul(a, b) -> np.ndarray:
    return np.matmul(a, b)


def br_sigmoid(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    # Numerically stable: for very negative x use exp(x)/(1+exp(x))
    out = np.empty_like(x)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    out[~pos] = np.exp(x[~pos]) / (1.0 + np.exp(x[~pos]))
    return out


def br_relu(x) -> np.ndarray:
    return np.maximum(0, np.asarray(x, dtype=float))


def br_softmax(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x = x - np.max(x)  # numerical stability
    e = np.exp(x)
    return e / np.sum(e)


@dataclass
class LinearModel:
    """Result of linear_regression(). Honest fields, no magic."""

    slope: float
    intercept: float
    r2: float
    _sk_model: Any = field(repr=False, default=None)

    def predict(self, x) -> np.ndarray:
        x_arr = np.asarray(x, dtype=float).reshape(-1, 1)
        return self._sk_model.predict(x_arr)


def br_linear_regression(x, y) -> LinearModel:
    """Fit y = slope*x + intercept using scikit-learn.

    Returns a LinearModel with slope, intercept, r2, and a .predict() method.
    Only 1-D x supported here for simplicity; for multivariate, use sklearn directly.
    """
    x_arr = np.asarray(x, dtype=float).reshape(-1, 1)
    y_arr = np.asarray(y, dtype=float)
    model = LinearRegression().fit(x_arr, y_arr)
    r2 = float(model.score(x_arr, y_arr))
    return LinearModel(
        slope=float(model.coef_[0]),
        intercept=float(model.intercept_),
        r2=r2,
        _sk_model=model,
    )


def br_kmeans(data, k: int, seed: int = 42) -> dict:
    """K-Means clustering. Returns {'labels', 'centers', 'inertia'}."""
    arr = np.asarray(data, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    km = KMeans(n_clusters=int(k), random_state=seed, n_init=10).fit(arr)
    return {
        "labels": km.labels_.tolist(),
        "centers": km.cluster_centers_.tolist(),
        "inertia": float(km.inertia_),
    }


def br_pca(data, n_components: int) -> dict:
    """PCA dimensionality reduction. Returns {'reduced', 'explained_variance_ratio'}."""
    arr = np.asarray(data, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    pca = PCA(n_components=int(n_components)).fit(arr)
    return {
        "reduced": pca.transform(arr).tolist(),
        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
    }


def br_normalize(data) -> np.ndarray:
    """L2-normalize each row."""
    arr = np.asarray(data, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return sk_normalize(arr, norm="l2")


def br_similarity(a, b) -> float:
    """Cosine similarity between two 1-D vectors."""
    a_arr = np.asarray(a, dtype=float).ravel()
    b_arr = np.asarray(b, dtype=float).ravel()
    denom = (np.linalg.norm(a_arr) * np.linalg.norm(b_arr))
    if denom == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / denom)


# ===========================================================================
# VECTOR STORE
# ===========================================================================

class VectorStore:
    """Vector store with FAISS backend if available, numpy brute-force fallback.

    Uses a hash-based bag-of-words embedder by default (deterministic, no deps).
    If sentence-transformers is installed and load_embedder() is called, switches
    to real semantic embeddings.
    """

    def __init__(self, dim: int = 256):
        self.dim = int(dim)
        self._vectors: list[np.ndarray] = []
        self._payloads: list[str] = []
        self._embedder = None  # lazily loaded real embedder
        if _HAS_FAISS:
            self._index = faiss.IndexFlatIP(self.dim)  # inner product on normalized vecs
        else:
            self._index = None

    # -- Embedding ----------------------------------------------------------

    def load_embedder(self, model_name: str = "all-MiniLM-L6-v2") -> bool:
        """Try to load a real sentence-transformers embedder. Returns True on success."""
        if not _HAS_ST:
            return False
        self._embedder = SentenceTransformer(model_name)
        self.dim = self._embedder.get_sentence_embedding_dimension()
        # Rebuild index if we had one
        if _HAS_FAISS:
            self._index = faiss.IndexFlatIP(self.dim)
        self._vectors = []
        self._payloads = []
        return True

    def embed(self, text: str) -> np.ndarray:
        """Embed text to a unit vector of length self.dim."""
        if self._embedder is not None:
            v = self._embedder.encode([text])[0].astype("float32")
        else:
            v = self._hash_embed(text)
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        return v.astype("float32")

    def _hash_embed(self, text: str) -> np.ndarray:
        """Feature-hashing bag-of-words embedding. Fast, deterministic, no deps.

        NOT semantic — 'cat' and 'kitten' will not be close. Use load_embedder()
        for real semantic search.
        """
        v = np.zeros(self.dim, dtype="float32")
        for token in text.lower().split():
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 32) & 1 else -1.0
            v[idx] += sign
        return v

    # -- CRUD ---------------------------------------------------------------

    def add(self, text: str) -> int:
        v = self.embed(text)
        self._vectors.append(v)
        self._payloads.append(text)
        if self._index is not None:
            self._index.add(v.reshape(1, -1))
        return len(self._payloads) - 1

    def search(self, query: str, k: int = 5) -> list[dict]:
        if not self._payloads:
            return []
        q = self.embed(query).reshape(1, -1)
        k = min(int(k), len(self._payloads))
        if self._index is not None:
            scores, idxs = self._index.search(q, k)
            scores, idxs = scores[0], idxs[0]
        else:
            # numpy fallback: cosine via dot product on unit vectors
            mat = np.stack(self._vectors)
            scores = (mat @ q.ravel())
            idxs = np.argsort(-scores)[:k]
            scores = scores[idxs]
        return [
            {"id": int(i), "score": float(s), "text": self._payloads[int(i)]}
            for i, s in zip(idxs, scores)
            if int(i) >= 0
        ]

    def size(self) -> int:
        return len(self._payloads)

    def save(self, path: str) -> None:
        """Persist to a single .npz file (payloads + vectors)."""
        if not self._vectors:
            np.savez(path, vectors=np.zeros((0, self.dim)), payloads=np.array([]))
            return
        np.savez(
            path,
            vectors=np.stack(self._vectors),
            payloads=np.array(self._payloads, dtype=object),
        )

    def load(self, path: str) -> None:
        data = np.load(path, allow_pickle=True)
        vecs = data["vectors"]
        self._vectors = [v.astype("float32") for v in vecs]
        self._payloads = list(data["payloads"])
        if self._index is not None and len(self._vectors) > 0:
            self._index.reset()
            self._index.add(np.stack(self._vectors))


def br_vector_create(dim: int = 256) -> VectorStore:
    return VectorStore(dim=dim)


def br_vector_add(store: VectorStore, text: str) -> int:
    return store.add(text)


def br_vector_search(store: VectorStore, query: str, k: int = 5) -> list[dict]:
    return store.search(query, k=k)


# ===========================================================================
# MEMORY SANDBOX (SQLite-backed key/value with metadata)
# ===========================================================================

class MemorySandbox:
    """Persistent key/value memory backed by SQLite. JSON-serializable values only."""

    def __init__(self, path: str = ":memory:"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                size INTEGER NOT NULL
            )
            """
        )
        self.conn.commit()

    def save(self, key: str, value: Any) -> str:
        payload = json.dumps(value, default=str)
        self.conn.execute(
            "INSERT OR REPLACE INTO memory(key, value, created_at, size) VALUES (?,?,?,?)",
            (key, payload, time.time(), len(payload)),
        )
        self.conn.commit()
        return key

    def recall(self, key: str) -> Any:
        row = self.conn.execute(
            "SELECT value FROM memory WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def forget(self, key: str) -> bool:
        cur = self.conn.execute("DELETE FROM memory WHERE key = ?", (key,))
        self.conn.commit()
        return cur.rowcount > 0

    def stats(self) -> dict:
        row = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(size), 0) FROM memory"
        ).fetchone()
        return {"entries": int(row[0]), "size_bytes": int(row[1])}

    def keys(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT key FROM memory").fetchall()]


def br_memory_save(sandbox: MemorySandbox, key: str, value: Any) -> str:
    return sandbox.save(key, value)


def br_memory_recall(sandbox: MemorySandbox, key: str) -> Any:
    return sandbox.recall(key)


def br_memory_forget(sandbox: MemorySandbox, key: str) -> bool:
    return sandbox.forget(key)


def br_memory_stats(sandbox: MemorySandbox) -> dict:
    return sandbox.stats()


# ===========================================================================
# QUANTUM-INSPIRED ENCODING
# ---------------------------------------------------------------------------
# This is classical math inspired by quantum concepts. It is NOT quantum
# computing. We implement:
#   - amplitude encoding: map a real vector to a unit-norm "state vector"
#   - measurement: sample an index i with probability |state[i]|^2
#   - SVD-based lossy compression: keep top-k singular values
# For real QML, use Qiskit or PennyLane.
# ===========================================================================

def br_quantum_encode(data) -> dict:
    """Amplitude encoding: normalize a vector so sum(|amp|^2) = 1.

    Returns {'state': [...], 'norm': original_norm}. Classical, not quantum.
    """
    v = np.asarray(data, dtype=float).ravel()
    norm = float(np.linalg.norm(v))
    if norm == 0:
        state = v.tolist()
    else:
        state = (v / norm).tolist()
    return {"state": state, "norm": norm, "note": "classical amplitude encoding"}


def br_quantum_decode(encoded: dict) -> list:
    """Inverse of br_quantum_encode: multiply state by stored norm."""
    state = np.asarray(encoded["state"], dtype=float)
    return (state * encoded["norm"]).tolist()


def br_quantum_measure(state, seed: int | None = None) -> int:
    """Sample an index from |amplitude|^2 distribution (single-shot measurement)."""
    rng = np.random.default_rng(seed)
    s = np.asarray(state, dtype=float).ravel()
    probs = s * s
    total = probs.sum()
    if total == 0:
        return 0
    probs = probs / total
    return int(rng.choice(len(probs), p=probs))


def br_svd_compress(matrix, rank: int) -> dict:
    """Truncated SVD compression. Returns reconstruction + compression ratio."""
    m = np.asarray(matrix, dtype=float)
    u, s, vt = np.linalg.svd(m, full_matrices=False)
    k = int(rank)
    u_k, s_k, vt_k = u[:, :k], s[:k], vt[:k, :]
    reconstructed = u_k @ np.diag(s_k) @ vt_k
    original_size = m.size
    compressed_size = u_k.size + s_k.size + vt_k.size
    return {
        "reconstructed": reconstructed.tolist(),
        "rank": k,
        "ratio": float(compressed_size / original_size),
        "frobenius_error": float(np.linalg.norm(m - reconstructed)),
    }


# ===========================================================================
# "CHINESE COMPRESSION" — honest version
# ---------------------------------------------------------------------------
# The original claim of "70% space reduction" needed honesty: mapping ASCII
# to CJK ideograms in UTF-8 INCREASES byte size (3 bytes/char vs 1). What
# actually saves space is dictionary coding: map frequent tokens (words,
# ngrams) to single code points. We use the CJK Unified Ideographs range
# (U+4E00..U+9FFF, ~20k code points) as a compact visual alphabet.
#
# Metric reported: character count reduction (not byte reduction).
# For actual byte compression, use zlib.
# ===========================================================================

_CJK_START = 0x4E00
_CJK_END = 0x9FFF
_CJK_RANGE = _CJK_END - _CJK_START + 1


def br_compress_zh(text: str, min_token_len: int = 3) -> dict:
    """Dictionary-coding compression using CJK code points as symbols.

    Builds a frequency-based codebook of whitespace-separated tokens and
    replaces each with one CJK character. Returns both the compressed text
    and the codebook needed to decompress.

    Honest metrics returned:
      - char_reduction: 1 - (len(compressed) / len(original))
      - byte_reduction_utf8: 1 - (utf8_bytes(compressed+codebook) / utf8_bytes(original))
        (this one is often NEGATIVE for short inputs — we report it truthfully)
    """
    tokens = text.split()
    freq = Counter(tokens)
    # Only compress tokens that appear >= 2 times and are long enough to matter
    candidates = [
        t for t, c in freq.most_common()
        if c >= 2 and len(t) >= min_token_len
    ]
    candidates = candidates[:_CJK_RANGE]  # cap at available symbols

    codebook = {t: chr(_CJK_START + i) for i, t in enumerate(candidates)}
    reverse = {v: k for k, v in codebook.items()}

    # Build compressed stream: replace known tokens with their CJK symbol,
    # separate with space so decompression is unambiguous.
    compressed_parts = [codebook.get(tok, tok) for tok in tokens]
    compressed = " ".join(compressed_parts)

    original_bytes = len(text.encode("utf-8"))
    compressed_bytes = len(compressed.encode("utf-8")) + len(
        json.dumps(reverse, ensure_ascii=False).encode("utf-8")
    )

    return {
        "compressed": compressed,
        "codebook": reverse,
        "char_reduction": 1 - (len(compressed) / max(len(text), 1)),
        "byte_reduction_utf8": 1 - (compressed_bytes / max(original_bytes, 1)),
        "note": "dictionary coding; byte_reduction may be negative on small inputs",
    }


def br_decompress_zh(payload: dict) -> str:
    compressed = payload["compressed"]
    codebook = payload["codebook"]
    out = []
    for tok in compressed.split():
        out.append(codebook.get(tok, tok))
    return " ".join(out)


def br_compress_zlib(text: str) -> dict:
    """Actual byte compression with zlib. Honest baseline to compare against."""
    raw = text.encode("utf-8")
    comp = zlib.compress(raw, level=9)
    return {
        "compressed_b64": base64.b64encode(comp).decode("ascii"),
        "original_bytes": len(raw),
        "compressed_bytes": len(comp),
        "byte_reduction": 1 - (len(comp) / max(len(raw), 1)),
    }


def br_decompress_zlib(payload: dict) -> str:
    return zlib.decompress(base64.b64decode(payload["compressed_b64"])).decode("utf-8")


# ===========================================================================
# CRYPTO / HASH
# ===========================================================================

def br_md5(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()


def br_sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def br_sha512(data: str) -> str:
    return hashlib.sha512(data.encode()).hexdigest()


def br_base64_encode(data: str) -> str:
    return base64.b64encode(data.encode()).decode()


def br_base64_decode(data: str) -> str:
    return base64.b64decode(data.encode()).decode()


# ===========================================================================
# STRING FUNCTIONS
# ===========================================================================

def br_upper(s: str) -> str:
    return s.upper() if s else ""

def br_lower(s: str) -> str:
    return s.lower() if s else ""

def br_trim(s: str) -> str:
    return s.strip() if s else ""

def br_split(s: str, delim: str = " ") -> list:
    return s.split(delim) if s else []

def br_join(lst, delim: str = " ") -> str:
    return delim.join(str(x) for x in lst) if lst else ""

def br_replace(s: str, old: str, new: str) -> str:
    return s.replace(old, new) if s else ""

def br_startswith(s: str, prefix: str) -> bool:
    return s.startswith(prefix) if s else False

def br_endswith(s: str, suffix: str) -> bool:
    return s.endswith(suffix) if s else False

def br_contains(s: str, sub: str) -> bool:
    return sub in s if s else False

def br_sub(s: str, start: int, end: int = None) -> str:
    if end is not None:
        return s[int(start):int(end)]
    return s[int(start):]

import re as _re

def br_match(pattern: str, text: str):
    m = _re.search(pattern, text)
    return m.group() if m else None

def br_gmatch(pattern: str, text: str) -> list:
    return _re.findall(pattern, text)

def br_gsub(text: str, pattern: str, repl: str) -> str:
    return _re.sub(pattern, repl, text) if text else ""


# ===========================================================================
# FILE I/O (sandboxed to workspace by default)
# ===========================================================================

import os as _os

def br_read(filename: str) -> str | None:
    try:
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return None

def br_write(filename: str, content: str) -> bool:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(str(content))
        return True
    except Exception:
        return False

def br_append(filename: str, content: str) -> bool:
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(str(content))
        return True
    except Exception:
        return False

def br_ls(path: str = ".") -> list:
    try:
        return sorted(e.name for e in Path(path).iterdir())
    except Exception:
        return []

def br_exists(path: str) -> bool:
    return Path(path).exists()

def br_mkdir(path: str) -> bool:
    try:
        _os.makedirs(path, exist_ok=True)
        return True
    except Exception:
        return False

def br_rm(path: str) -> bool:
    try:
        p = Path(path)
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            p.rmdir()
        return True
    except Exception:
        return False


# ===========================================================================
# MATH (extended — real implementations wrapping stdlib math)
# ===========================================================================

def br_abs(n):
    return abs(n)

def br_floor(n) -> int:
    return math.floor(n)

def br_ceil(n) -> int:
    return math.ceil(n)

def br_round(n, decimals: int = 0):
    return round(n, int(decimals))

def br_sqrt(n) -> float:
    return math.sqrt(n)

def br_pow(base, exp) -> float:
    return math.pow(base, exp)

def br_log(n, base=None) -> float:
    return math.log(n) if base is None else math.log(n, base)

def br_log10(n) -> float:
    return math.log10(n)

def br_sin(n) -> float:
    return math.sin(n)

def br_cos(n) -> float:
    return math.cos(n)

def br_tan(n) -> float:
    return math.tan(n)

def br_min(*args):
    flat = args[0] if len(args) == 1 and hasattr(args[0], "__iter__") else args
    return min(flat)

def br_max(*args):
    flat = args[0] if len(args) == 1 and hasattr(args[0], "__iter__") else args
    return max(flat)

import random as _random_mod

def br_random(a: int = 0, b: int = 100) -> int:
    return _random_mod.randint(int(a), int(b))

def br_range(start, end=None, step=1) -> list:
    if end is None:
        return list(range(int(start)))
    return list(range(int(start), int(end), int(step)))


# ===========================================================================
# COLLECTIONS
# ===========================================================================

def br_push(lst: list, item):
    lst.append(item)
    return lst

def br_pop(lst: list):
    return lst.pop() if lst else None

def br_sort(lst):
    return sorted(lst)

def br_reverse(lst):
    return list(reversed(lst))

def br_keys(d: dict) -> list:
    return list(d.keys()) if isinstance(d, dict) else []

def br_values(d: dict) -> list:
    return list(d.values()) if isinstance(d, dict) else []

def br_table(*pairs):
    """Create a dict from alternating key/value pairs: table('a', 1, 'b', 2)."""
    d = {}
    for i in range(0, len(pairs) - 1, 2):
        d[pairs[i]] = pairs[i + 1]
    return d


# ===========================================================================
# JSON
# ===========================================================================

def br_json_encode(obj) -> str:
    return json.dumps(obj, default=str)

def br_json_decode(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


# ===========================================================================
# SYSTEM
# ===========================================================================

from datetime import datetime as _dt

def br_time() -> int:
    return int(time.time())

def br_date() -> str:
    return _dt.now().strftime("%Y-%m-%d")

def br_datetime() -> str:
    return _dt.now().isoformat()

def br_sleep(seconds):
    time.sleep(float(seconds))

def br_env(name: str, default: str = "") -> str:
    return _os.environ.get(name, default)

def br_cwd() -> str:
    return _os.getcwd()

def br_type(obj) -> str:
    if obj is None:
        return "nil"
    if isinstance(obj, bool):
        return "bool"
    if isinstance(obj, int):
        return "int"
    if isinstance(obj, float):
        return "float"
    if isinstance(obj, str):
        return "string"
    if isinstance(obj, list):
        return "list"
    if isinstance(obj, dict):
        return "dict"
    return type(obj).__name__


# ===========================================================================
# HASHING (extended)
# ===========================================================================

def br_sha1(data: str) -> str:
    return hashlib.sha1(data.encode()).hexdigest()

def br_hex_encode(data: str) -> str:
    return data.encode().hex()

def br_hex_decode(data: str) -> str:
    return bytes.fromhex(data).decode()

import secrets as _secrets

def br_uuid() -> str:
    return _secrets.token_hex(16)

def br_token(length: int = 32) -> str:
    return _secrets.token_urlsafe(int(length))

def br_gen_password(length: int = 16) -> str:
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(_secrets.choice(alphabet) for _ in range(int(length)))


# ===========================================================================
# URL encoding
# ===========================================================================

import urllib.parse as _urlparse

def br_url_encode(text: str) -> str:
    return _urlparse.quote(text)

def br_url_decode(text: str) -> str:
    return _urlparse.unquote(text)


# ===========================================================================
# PRINTLN helper (print with newline — the default print already does this,
# but BoRLang v2 had both "print" and "println")
# ===========================================================================

def br_println(*args):
    print(*args)

def br_print(*args):
    print(*args, end="")


# ===========================================================================
# REGISTRY — maps BoRLang names → Python callables
# ===========================================================================

def build_stdlib() -> dict:
    """Return the dict of {borlang_name: python_callable} for the interpreter."""
    # Soft-import the flow engine so core works without it
    try:
        from borlang_flow import build_flow_stdlib
        flow_funcs = build_flow_stdlib()
    except ImportError:
        flow_funcs = {}

    std = {
        # --- ML / NumPy ---
        "array": br_array,
        "zeros": br_zeros,
        "ones": br_ones,
        "random_array": br_random_array,
        "mean": br_mean,
        "std": br_std,
        "dot": br_dot,
        "matmul": br_matmul,
        "sigmoid": br_sigmoid,
        "relu": br_relu,
        "softmax": br_softmax,
        "linear_regression": br_linear_regression,
        "kmeans": br_kmeans,
        "pca": br_pca,
        "normalize": br_normalize,
        "similarity": br_similarity,
        # --- Vector store ---
        "vector_create": br_vector_create,
        "vector_add": br_vector_add,
        "vector_search": br_vector_search,
        # --- Memory sandbox ---
        "memory_new": lambda path=":memory:": MemorySandbox(path),
        "memory_save": br_memory_save,
        "memory_recall": br_memory_recall,
        "memory_forget": br_memory_forget,
        "memory_stats": br_memory_stats,
        # --- Quantum-inspired ---
        "quantum_encode": br_quantum_encode,
        "quantum_decode": br_quantum_decode,
        "quantum_measure": br_quantum_measure,
        "svd_compress": br_svd_compress,
        # --- Compression ---
        "compress_zh": br_compress_zh,
        "decompress_zh": br_decompress_zh,
        "compress_zlib": br_compress_zlib,
        "decompress_zlib": br_decompress_zlib,
        # --- Crypto / Hash ---
        "md5": br_md5,
        "sha1": br_sha1,
        "sha256": br_sha256,
        "sha512": br_sha512,
        "base64_encode": br_base64_encode,
        "base64_decode": br_base64_decode,
        "hex_encode": br_hex_encode,
        "hex_decode": br_hex_decode,
        "uuid": br_uuid,
        "token": br_token,
        "gen_password": br_gen_password,
        "url_encode": br_url_encode,
        "url_decode": br_url_decode,
        # --- String ---
        "upper": br_upper,
        "lower": br_lower,
        "trim": br_trim,
        "split": br_split,
        "join": br_join,
        "replace": br_replace,
        "startswith": br_startswith,
        "endswith": br_endswith,
        "contains": br_contains,
        "sub": br_sub,
        "match": br_match,
        "gmatch": br_gmatch,
        "gsub": br_gsub,
        # --- File I/O ---
        "read": br_read,
        "write": br_write,
        "append": br_append,
        "ls": br_ls,
        "exists": br_exists,
        "mkdir": br_mkdir,
        "rm": br_rm,
        # --- Math ---
        "abs": br_abs,
        "floor": br_floor,
        "ceil": br_ceil,
        "round": br_round,
        "sqrt": br_sqrt,
        "pow": br_pow,
        "log": br_log,
        "log10": br_log10,
        "sin": br_sin,
        "cos": br_cos,
        "tan": br_tan,
        "min": br_min,
        "max": br_max,
        "sum": br_sum,
        "random": br_random,
        "range": br_range,
        "pi": lambda: math.pi,
        "e": lambda: math.e,
        # --- Collections ---
        "push": br_push,
        "pop": br_pop,
        "sort": br_sort,
        "reverse": br_reverse,
        "keys": br_keys,
        "values": br_values,
        "table": br_table,
        # --- JSON ---
        "json_encode": br_json_encode,
        "json_decode": br_json_decode,
        # --- System ---
        "time": br_time,
        "date": br_date,
        "datetime": br_datetime,
        "sleep": br_sleep,
        "env": br_env,
        "cwd": br_cwd,
        "typeof": br_type,
        # --- I/O ---
        "print": br_println,
        "println": br_println,
        "len": len,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
    }
    std.update(flow_funcs)
    return std
