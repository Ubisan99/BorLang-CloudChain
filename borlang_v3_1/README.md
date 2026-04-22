# ◆ BoRLang v3.1

**A scripting language for ML, vector search, and agentic workflows.**
Python-like syntax · Lua-like scoping · n8n/RAGFlow-style block programming.
Real implementations backed by NumPy, scikit-learn, SQLite.

> Created by **L.L.B && D.B**

```bash
python borlang.py                        # REPL
python borlang.py examples/demo_v3.bor   # ML/Vector/Memory demo (16 modules)
python borlang.py examples/agent_rag.bor # Agentic flow demo (RAG pipeline)
python test_borlang.py                   # Core test suite (38 tests)
python test_flow.py                      # Flow engine tests (15 tests)
```

Open `playground.html` for the code editor, or `flow_designer.html` for the visual flow designer.

---

## New in v3.1: BoRFlow — Agentic Workflow Engine

Build agentic pipelines like n8n or RAGFlow, but programmed directly in BoRLang.
Every flow is a DAG of **blocks** (http, llm, transform, condition, loop, python).
State flows through a shared context. Runs sequentially; conditions branch; loops iterate.

```lua
# Build a RAG-like agent in 10 lines
agent = flow_new("my_agent")

flow_add(agent, "fetch",    "http",      {url: "https://api.example.com/docs"})
flow_add(agent, "extract",  "transform", {field: "body.items"})
flow_add(agent, "check",    "condition", {left: "{{len_items}}", op: ">", right: 0})
flow_add(agent, "summarize","llm",       {model: "qwen2.5:14b", prompt: "Summarize: {{item}}"})
flow_add(agent, "fallback", "print",     {message: "no items found"})

flow_connect(agent, "fetch", "extract")
flow_connect(agent, "extract", "check")
flow_branch(agent, "check", "summarize", "fallback")

result = flow_run(agent)
```

### Block types

| Type | What it does | Config |
|---|---|---|
| `print` | Print message (template with `{{key}}`) | `message` |
| `http` | Real HTTP GET/POST via urllib | `url, method, headers, body` |
| `llm` | Call Ollama API (real inference) | `model, prompt, host, system` |
| `transform` | Extract field or apply op | `field` or `input` + `operation` |
| `condition` | Branch `on_true`/`on_false` | `left, op, right` |
| `loop` | Iterate over a collection | `over, body, item_key` |
| `python` | Drop to Python callable | `fn` |
| `action` | Custom handler by name | `name` + args |

### Flow primitives

```lua
flow_new(name)                          # create empty flow
flow_add(f, id, type, config)           # add a block
flow_connect(f, from_id, to_id)         # connect default edge
flow_branch(f, cond_id, true_id, false_id)  # connect condition branches
flow_run(f, initial_context)            # execute the flow
flow_trace(f)                           # get execution log
flow_to_json(f)                         # serialize for UI rendering
```

### Visual designer

`flow_designer.html` is a browser-based n8n-like canvas:
- Parse BoRLang flow code into visual nodes
- Drag nodes to rearrange the DAG
- See animated execution with per-node status
- Click a node to inspect its config
- View the live context in the inspector

---

## What's real (all tested, all working)

| Module | Functions | Backend |
|---|---|---|
| **Parser** | Lexer + recursive descent, if/elif/else/while/for, closures, lists, dicts | Handwritten, 0 deps |
| **ML** | `linear_regression`, `kmeans`, `pca`, `normalize`, `sigmoid`, `relu`, `softmax`, `mean`, `std`, `dot`, `matmul` | NumPy + scikit-learn |
| **Vector Store** | `vector_create`, `vector_add`, `vector_search` | Hash embeddings + NumPy; FAISS if installed; sentence-transformers for semantic search |
| **Memory** | `memory_new`, `memory_save`, `memory_recall`, `memory_forget`, `memory_stats` | SQLite |
| **Quantum-inspired** | `quantum_encode`, `quantum_decode`, `quantum_measure`, `svd_compress` | Classical amplitude encoding (NOT quantum computing) |
| **Compression** | `compress_zh` / `decompress_zh`, `compress_zlib` | Dictionary coding + zlib; honest metrics |
| **Crypto** | `md5`, `sha1`, `sha256`, `sha512`, `base64_*`, `hex_*`, `uuid`, `token`, `gen_password` | stdlib hashlib, secrets |
| **Strings** | `upper`, `lower`, `trim`, `split`, `join`, `replace`, `contains`, `startswith`, `endswith`, `match`, `gmatch`, `gsub` | Pure Python |
| **File I/O** | `read`, `write`, `append`, `ls`, `exists`, `mkdir`, `rm` | stdlib pathlib/os |
| **Math** | `abs`, `floor`, `ceil`, `round`, `sqrt`, `pow`, `log`, `sin`, `cos`, `tan`, `min`, `max`, `random`, `range`, `pi`, `e` | stdlib math |
| **Collections** | `table`, `push`, `pop`, `sort`, `reverse`, `keys`, `values` | Pure Python |
| **JSON** | `json_encode`, `json_decode` | stdlib json |
| **System** | `time`, `date`, `datetime`, `sleep`, `env`, `cwd`, `typeof` | stdlib |
| **🆕 Flow** | `flow_new`, `flow_add`, `flow_connect`, `flow_branch`, `flow_run`, `flow_trace`, `flow_to_json` | BoRFlow engine |

**Total: 115 built-in functions · 53 automated tests · all real implementations.**

---

## Honest notes

**"Quantum" functions** are classical math (amplitude encoding = unit-norm vector; measurement = sampling from |amp|²). NOT quantum computing.

**"Chinese compression"** uses CJK ideographs via dictionary coding. Reduces character count, often **increases** UTF-8 byte count. Both metrics reported truthfully.

**LLM blocks** require Ollama running locally (or configured host). If Ollama isn't reachable, the block raises a clear error — it does NOT fake a completion.

**HTTP blocks** make real `urllib.request` calls with real timeouts. No mocked responses.

**Pentest tools** from v1/v2 removed (they were fake stubs). Will return as opt-in `borlang_net` module with real `subprocess` + sanitization.

---

## Install

```bash
# Minimum (core + flow work with just these)
pip install numpy scikit-learn

# Optional: faster vector search
pip install faiss-cpu

# Optional: real semantic embeddings
pip install sentence-transformers
```

---

## File structure

```
borlang.py          — interpreter (lexer + parser + evaluator)
borlang_stdlib.py   — standard library (100+ functions)
borlang_flow.py     — 🆕 agentic workflow engine (BoRFlow)
test_borlang.py     — core tests (38 passing)
test_flow.py        — flow tests (15 passing)
playground.html     — code editor playground
flow_designer.html  — 🆕 visual flow designer (n8n-style)
examples/
  demo_v3.bor       — full ML/Vector/Memory demo
  agent_rag.bor     — 🆕 agentic RAG pipeline demo
```

---

## Use case: small agentic language model

With BoRFlow + BoRLang's ML/vector stack, you can build a **small language model agent** entirely on your own hardware:

1. **Retrieve**: `vector_search` over indexed documents
2. **Reason**: `llm` block calling local Ollama
3. **Act**: `condition` branches, `loop` over results, `http` to downstream APIs
4. **Remember**: `memory_save`/`memory_recall` for conversation state

The whole agent is a BoRFlow — versionable, serializable to JSON, renderable as a visual diagram.

---

## Roadmap

- **v3.2**: `borlang_net` with real subprocess-based pentest tools (opt-in, with authorization flags)
- **v3.3**: Flow persistence (save/load `.bflow` files)
- **v3.4**: Multi-model LLM routing (Ollama + OpenAI + local GGUF via llama-cpp-python)
- **v4.0**: CloudChain integration — BoRLang/BoRFlow as smart contract + orchestration layer

---

## License

MIT — see LICENSE file.

**by L.L.B && D.B** — *"ship what works, document what doesn't."*
