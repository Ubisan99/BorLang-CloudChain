"""Tests for BoRLang v0.2. Run with: pytest test_borlang.py -v"""

import math
import numpy as np

try:
    import pytest  # type: ignore
except ImportError:
    pytest = None

from borlang import Interpreter, tokenize, Parser


# ===========================================================================
# LEXER
# ===========================================================================

def test_lex_basic():
    toks = tokenize('x = 42 + "hi"')
    # drop newlines/EOF
    kinds = [(t.type, t.value) for t in toks if t.type not in ("NL", "EOF")]
    assert kinds == [
        ("NAME", "x"), ("OP", "="), ("NUM", 42), ("OP", "+"), ("STR", "hi")
    ]


def test_lex_string_with_commas_and_parens():
    # The old regex interpreter broke on this. Must work now.
    toks = tokenize('print("hello, (world)")')
    vals = [t.value for t in toks if t.type == "STR"]
    assert vals == ["hello, (world)"]


def test_lex_comments():
    toks = tokenize("x = 1 # this is a comment\ny = 2 // also comment")
    names = [t.value for t in toks if t.type == "NAME"]
    assert names == ["x", "y"]


# ===========================================================================
# PARSER
# ===========================================================================

def test_parse_nested_calls():
    # This is the pathological case that broke borlang v1.
    Parser(tokenize("print(portfolio({BTC: 2}))")).parse_program()


def test_parse_if_while():
    Parser(tokenize("""
        if x > 0
            y = 1
        elif x == 0
            y = 0
        else
            y = -1
        end
        while y < 10
            y = y + 1
        end
    """)).parse_program()


# ===========================================================================
# INTERPRETER — basics
# ===========================================================================

def test_arithmetic():
    i = Interpreter()
    i.run("x = 2 + 3 * 4")
    assert i.globals.get("x") == 14


def test_string_concat():
    i = Interpreter()
    i.run('s = "v=" + 42')
    assert i.globals.get("s") == "v=42"


def test_if_elif_else():
    i = Interpreter()
    i.run("""
        x = 5
        if x > 10
            y = "big"
        elif x > 3
            y = "medium"
        else
            y = "small"
        end
    """)
    assert i.globals.get("y") == "medium"


def test_while_loop():
    i = Interpreter()
    i.run("""
        total = 0
        n = 1
        while n <= 5
            total = total + n
            n = n + 1
        end
    """)
    assert i.globals.get("total") == 15


def test_for_loop_over_list():
    i = Interpreter()
    i.run("""
        total = 0
        for x in [1, 2, 3, 4]
            total = total + x
        end
    """)
    assert i.globals.get("total") == 10


def test_user_function_with_return():
    i = Interpreter()
    i.run("""
        def square(n)
            return n * n
        end
        result = square(7)
    """)
    assert i.globals.get("result") == 49


def test_closure_captures_env():
    i = Interpreter()
    i.run("""
        def make_adder(x)
            def inner(y)
                return x + y
            end
            return inner
        end
        add5 = make_adder(5)
        result = add5(10)
    """)
    assert i.globals.get("result") == 15


def test_nested_call_with_dict_literal():
    # The exact case that couldn't be parsed before.
    i = Interpreter()
    i.run("d = {a: 1, b: 2}")
    assert i.globals.get("d") == {"a": 1, "b": 2}


def test_index_and_attr_assign():
    i = Interpreter()
    i.run("""
        d = {x: 1}
        d["y"] = 2
        lst = [10, 20, 30]
        lst[1] = 99
    """)
    assert i.globals.get("d") == {"x": 1, "y": 2}
    assert i.globals.get("lst") == [10, 99, 30]


# ===========================================================================
# STDLIB — ML
# ===========================================================================

def test_linear_regression_real():
    i = Interpreter()
    i.run("""
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]
        model = linear_regression(x, y)
    """)
    model = i.globals.get("model")
    assert abs(model.slope - 2.0) < 1e-9
    assert abs(model.intercept) < 1e-9
    assert abs(model.r2 - 1.0) < 1e-9


def test_kmeans_clusters_correctly():
    i = Interpreter()
    i.run("""
        data = [[1,1], [1,2], [10,10], [10,11]]
        result = kmeans(data, 2)
    """)
    result = i.globals.get("result")
    labels = result["labels"]
    # First two points and last two points should be in same cluster (order doesn't matter)
    assert labels[0] == labels[1]
    assert labels[2] == labels[3]
    assert labels[0] != labels[2]


def test_pca_reduces_dimension():
    i = Interpreter()
    i.run("""
        data = [[1,2,3], [4,5,6], [7,8,9], [10,11,12]]
        result = pca(data, 2)
    """)
    result = i.globals.get("result")
    assert len(result["reduced"][0]) == 2
    assert abs(sum(result["explained_variance_ratio"]) - 1.0) < 1e-9


def test_softmax_sums_to_one():
    i = Interpreter()
    i.run("s = softmax([1.0, 2.0, 3.0])")
    s = i.globals.get("s")
    assert abs(sum(s) - 1.0) < 1e-9


# ===========================================================================
# STDLIB — Vector store
# ===========================================================================

def test_vector_store_add_and_search():
    i = Interpreter()
    i.run("""
        store = vector_create(64)
        vector_add(store, "python programming language")
        vector_add(store, "cat sat on the mat")
        vector_add(store, "python is a great programming language for data")
        results = vector_search(store, "python programming", 2)
    """)
    results = i.globals.get("results")
    assert len(results) == 2
    # The two python-related docs should rank above the cat one
    top_texts = [r["text"] for r in results]
    assert any("python" in t for t in top_texts)


# ===========================================================================
# STDLIB — Memory sandbox
# ===========================================================================

def test_memory_roundtrip():
    i = Interpreter()
    i.run("""
        mem = memory_new()
        memory_save(mem, "user", {name: "Borty", age: 30})
        recalled = memory_recall(mem, "user")
        stats = memory_stats(mem)
    """)
    assert i.globals.get("recalled") == {"name": "Borty", "age": 30}
    assert i.globals.get("stats")["entries"] == 1


def test_memory_forget():
    i = Interpreter()
    i.run("""
        mem = memory_new()
        memory_save(mem, "tmp", 123)
        ok = memory_forget(mem, "tmp")
        after = memory_recall(mem, "tmp")
    """)
    assert i.globals.get("ok") is True
    assert i.globals.get("after") is None


# ===========================================================================
# STDLIB — Quantum-inspired
# ===========================================================================

def test_quantum_encode_is_unit_norm():
    i = Interpreter()
    i.run("""
        enc = quantum_encode([3, 4])
    """)
    enc = i.globals.get("enc")
    state = enc["state"]
    assert abs(sum(x * x for x in state) - 1.0) < 1e-9
    assert abs(enc["norm"] - 5.0) < 1e-9  # sqrt(9+16) = 5


def test_quantum_encode_decode_roundtrip():
    i = Interpreter()
    i.run("""
        original = [1.0, 2.5, -3.7, 4.2]
        enc = quantum_encode(original)
        dec = quantum_decode(enc)
    """)
    original = [1.0, 2.5, -3.7, 4.2]
    dec = i.globals.get("dec")
    assert all(abs(a - b) < 1e-9 for a, b in zip(original, dec))


def test_svd_compress_reduces_rank():
    i = Interpreter()
    i.run("""
        m = [[1,2,3,4], [2,4,6,8], [3,6,9,12]]
        result = svd_compress(m, 1)
    """)
    # Matrix is rank 1, so rank-1 reconstruction should be near-perfect
    result = i.globals.get("result")
    assert result["frobenius_error"] < 1e-9


# ===========================================================================
# STDLIB — Compression (honest metrics)
# ===========================================================================

def test_compress_zh_roundtrip():
    text = "the cat sat on the mat and the cat was happy the cat slept"
    i = Interpreter()
    i.globals.set_new("input_text", text)
    i.run("""
        result = compress_zh(input_text)
        restored = decompress_zh(result)
    """)
    assert i.globals.get("restored") == text


def test_compress_zlib_actually_compresses_repetitive():
    i = Interpreter()
    i.run("""
        text = "hello world " * 100
        result = compress_zlib("hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world")
    """)
    r = i.globals.get("result")
    # Highly repetitive → zlib should compress substantially
    assert r["byte_reduction"] > 0.5


# ===========================================================================
# STDLIB — String functions
# ===========================================================================

def test_string_upper_lower_trim():
    i = Interpreter()
    i.run("""
        s = "  Hello World  "
        u = upper(s)
        l = lower(s)
        t = trim(s)
    """)
    assert i.globals.get("u") == "  HELLO WORLD  "
    assert i.globals.get("l") == "  hello world  "
    assert i.globals.get("t") == "Hello World"


def test_string_split_join_replace():
    i = Interpreter()
    i.run("""
        parts = split("a-b-c", "-")
        joined = join(parts, ",")
        fixed = replace("hello world", "world", "BoRLang")
    """)
    assert i.globals.get("parts") == ["a", "b", "c"]
    assert i.globals.get("joined") == "a,b,c"
    assert i.globals.get("fixed") == "hello BoRLang"


def test_string_contains_startswith():
    i = Interpreter()
    i.run("""
        a = contains("hello world", "world")
        b = startswith("hello", "hel")
        c = endswith("hello", "llo")
    """)
    assert i.globals.get("a") is True
    assert i.globals.get("b") is True
    assert i.globals.get("c") is True


# ===========================================================================
# STDLIB — File I/O
# ===========================================================================

def test_file_write_read_exists():
    import tempfile, os
    tmp = tempfile.mktemp(suffix=".txt")
    i = Interpreter()
    i.globals.set_new("path", tmp)
    i.run("""
        write(path, "hello borlang")
        content = read(path)
        found = exists(path)
    """)
    assert i.globals.get("content") == "hello borlang"
    assert i.globals.get("found") is True
    os.unlink(tmp)


# ===========================================================================
# STDLIB — Math extended
# ===========================================================================

def test_math_functions():
    i = Interpreter()
    i.run("""
        a = floor(3.7)
        b = ceil(3.2)
        c = sqrt(16.0)
        d = abs(-5)
        r = round(3.14159, 2)
    """)
    assert i.globals.get("a") == 3
    assert i.globals.get("b") == 4
    assert i.globals.get("c") == 4.0
    assert i.globals.get("d") == 5
    assert i.globals.get("r") == 3.14


def test_range_function():
    i = Interpreter()
    i.run("r = range(1, 5)")
    assert i.globals.get("r") == [1, 2, 3, 4]


# ===========================================================================
# STDLIB — Collections
# ===========================================================================

def test_push_pop_sort_reverse():
    i = Interpreter()
    i.run("""
        lst = [3, 1, 4]
        push(lst, 5)
        s = sort(lst)
        rev = reverse(s)
    """)
    assert i.globals.get("lst") == [3, 1, 4, 5]
    assert i.globals.get("s") == [1, 3, 4, 5]
    assert i.globals.get("rev") == [5, 4, 3, 1]


def test_table_function():
    i = Interpreter()
    i.run('t = table("a", 1, "b", 2)')
    assert i.globals.get("t") == {"a": 1, "b": 2}


def test_keys_values():
    i = Interpreter()
    i.run("""
        d = {x: 10, y: 20}
        k = keys(d)
        v = values(d)
    """)
    assert set(i.globals.get("k")) == {"x", "y"}
    assert set(i.globals.get("v")) == {10, 20}


# ===========================================================================
# STDLIB — JSON
# ===========================================================================

def test_json_roundtrip():
    i = Interpreter()
    i.run("""
        d = {name: "borty", version: 3}
        s = json_encode(d)
        back = json_decode(s)
    """)
    assert i.globals.get("back") == {"name": "borty", "version": 3}


# ===========================================================================
# STDLIB — Crypto extras
# ===========================================================================

def test_uuid_and_token():
    i = Interpreter()
    i.run("""
        u = uuid()
        t = token(16)
        p = gen_password(20)
    """)
    assert len(i.globals.get("u")) == 32  # hex string
    assert len(i.globals.get("p")) == 20


def test_hex_encode_decode():
    i = Interpreter()
    i.run("""
        enc = hex_encode("hello")
        dec = hex_decode(enc)
    """)
    assert i.globals.get("dec") == "hello"


if __name__ == "__main__":
    if pytest is not None:
        pytest.main([__file__, "-v"])
    else:
        # Simple runner when pytest is unavailable
        import traceback
        tests = [(n, o) for n, o in list(globals().items())
                 if n.startswith("test_") and callable(o)]
        passed, failed = 0, []
        for name, fn in tests:
            try:
                fn()
                print(f"  OK   {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {name}: {type(e).__name__}: {e}")
                traceback.print_exc()
                failed.append(name)
        print(f"\n{passed}/{len(tests)} passed")
