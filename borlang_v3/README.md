# ◆ BoRLang v3.0

**A scripting language for ML, vector search, and data exploration.**
Python-like syntax · Lua-like scoping · real implementations backed by NumPy, scikit-learn, SQLite.

> Created by **L.L.B && D.B**

```
python borlang.py                      # REPL
python borlang.py examples/demo_v3.bor # full demo (16 modules)
python test_borlang.py                 # test suite (38 tests)
```

Open `playground.html` in a browser for an interactive code editor with examples and function reference.

---

## What's real (all tested, all working)

| Module | Functions | Backend |
|---|---|---|
| **Parser** | Lexer + recursive descent, if/elif/else/while/for, closures, lists, dicts | Handwritten, 0 deps |
| **ML** | `linear_regression`, `kmeans`, `pca`, `normalize`, `sigmoid`, `relu`, `softmax`, `mean`, `std`, `dot`, `matmul` | NumPy + scikit-learn |
| **Vector Store** | `vector_create`, `vector_add`, `vector_search` | Hash embeddings + NumPy; FAISS if installed; sentence-transformers for semantic search |
| **Memory** | `memory_new`, `memory_save`, `memory_recall`, `memory_forget`, `memory_stats` | SQLite |
| **Quantum-inspired** | `quantum_encode`, `quantum_decode`, `quantum_measure`, `svd_compress` | Classical amplitude encoding (NOT quantum computing) |
| **Compression** | `compress_zh` / `decompress_zh`, `compress_zlib` / `decompress_zlib` | Dictionary coding + zlib; honest metrics |
| **Crypto** | `md5`, `sha1`, `sha256`, `sha512`, `base64_*`, `hex_*`, `uuid`, `token`, `gen_password`, `url_encode/decode` | stdlib hashlib, secrets |
| **Strings** | `upper`, `lower`, `trim`, `split`, `join`, `replace`, `contains`, `startswith`, `endswith`, `match`, `gmatch`, `gsub` | Pure Python |
| **File I/O** | `read`, `write`, `append`, `ls`, `exists`, `mkdir`, `rm` | stdlib pathlib/os |
| **Math** | `abs`, `floor`, `ceil`, `round`, `sqrt`, `pow`, `log`, `sin`, `cos`, `tan`, `min`, `max`, `random`, `range`, `pi`, `e` | stdlib math |
| **Collections** | `table`, `push`, `pop`, `sort`, `reverse`, `keys`, `values` | Pure Python |
| **JSON** | `json_encode`, `json_decode` | stdlib json |
| **System** | `time`, `date`, `datetime`, `sleep`, `env`, `cwd`, `typeof` | stdlib |

**Total: 100+ built-in functions, all real implementations, 38 automated tests.**

---

## Honest notes

**"Quantum" functions** are classical math inspired by quantum concepts. `quantum_encode` normalizes a vector to unit length (amplitude encoding). `quantum_measure` samples an index from |amplitude|² distribution. This is NOT quantum computing. For real QML, use Qiskit or PennyLane.

**"Chinese compression"** uses CJK ideographs as a compact visual alphabet via dictionary coding. It reduces character count but typically **increases** byte count for small inputs (CJK = 3 bytes/char in UTF-8). The function reports both metrics honestly. For real compression, use `compress_zlib`.

**Pentest tools** from v1/v2 have been **removed** because they were all fake stubs returning hardcoded strings. They will return as a separate opt-in module (`borlang_net`) backed by real `subprocess` calls with input sanitization and authorization flags.

---

## Quick example

```lua
# Linear regression on real data
x = [1, 2, 3, 4, 5]
y = [2, 4, 6, 8, 10]
model = linear_regression(x, y)
print("slope = " + str(model.slope))
print("R² = " + str(model.r2))

# Vector search
store = vector_create(128)
vector_add(store, "python is great for ML")
vector_add(store, "i love pizza")
hits = vector_search(store, "machine learning python", 1)
print(hits[0]["text"])

# Closures
def make_counter(start)
    count = start
    def tick()
        count = count + 1
        return count
    end
    return tick
end
c = make_counter(0)
print(c())  # 1
print(c())  # 2
```

---

## Install

```bash
# Minimum (parser + all non-ML features work with just Python 3.10+)
pip install numpy scikit-learn

# Optional: FAISS vector index
pip install faiss-cpu

# Optional: real semantic embeddings
pip install sentence-transformers
```

---

## File structure

```
borlang.py          — interpreter (lexer + parser + evaluator)
borlang_stdlib.py   — standard library (100+ functions)
test_borlang.py     — test suite (38 tests)
playground.html     — web-based code editor + reference
examples/
  demo_v3.bor       — full demo exercising all 16 modules
```

---

## Roadmap

- **v3.1**: `break`/`continue`, string interpolation `f"x={x}"`, better REPL with readline
- **v3.2**: `borlang_net` module — real nmap/dns/whois via subprocess with sandboxing
- **v3.3**: FAISS persistence, semantic embedder auto-download
- **v4.0**: CloudChain integration — BoRLang as smart contract language for the L1 chain

---

## License

MIT — see LICENSE file.

## Credits

Original concept and design: **L.L.B && D.B**
v3.0 redesign principle: *"ship what works, document what doesn't."*
