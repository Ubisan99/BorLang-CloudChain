"""
BoRFlow — agentic workflow engine for BoRLang.

Build flows as a DAG of nodes. Each node is an action (http, llm, transform,
condition, loop, python). State flows through a shared context dict. Runs
sequentially by default; conditions branch, loops iterate.

Inspired by n8n and RAGFlow, but designed to be programmable directly from
BoRLang — build a flow the same way you'd build a block-based robot program:

    flow = flow_new("my_flow")
    flow_add(flow, "fetch", "http", {url: "https://api.example.com"})
    flow_add(flow, "extract", "transform", {field: "data.users"})
    flow_add(flow, "loop", "loop", {over: "users"})
    flow_connect(flow, "fetch", "extract")
    flow_connect(flow, "extract", "loop")
    result = flow_run(flow)

Design principles:
- Every action does what it says or raises. No simulated outputs.
- LLM calls require explicit backend config (Ollama, OpenAI, etc.) — no fake
  inference.
- Context is just a dict. Every node reads/writes keys.
- Flows serialize to JSON for UI rendering.
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable


# ===========================================================================
# CORE DATA MODEL
# ===========================================================================

@dataclass
class Node:
    """A single step in a flow."""
    id: str
    type: str              # "action", "http", "llm", "transform", "condition", "loop", "python"
    config: dict           # Node-specific parameters
    next: list[str] = field(default_factory=list)       # Default next node(s)
    on_true: str | None = None   # For conditions
    on_false: str | None = None


@dataclass
class Flow:
    """A DAG of nodes with a start node and shared context."""
    name: str
    nodes: dict[str, Node] = field(default_factory=dict)
    start: str | None = None
    context: dict = field(default_factory=dict)
    trace: list[dict] = field(default_factory=list)      # Execution log
    _handlers: dict[str, Callable] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize the flow structure (not context) for UI rendering."""
        return json.dumps({
            "name": self.name,
            "start": self.start,
            "nodes": [
                {
                    "id": n.id, "type": n.type, "config": n.config,
                    "next": n.next, "on_true": n.on_true, "on_false": n.on_false,
                }
                for n in self.nodes.values()
            ],
        }, default=str, indent=2)


# ===========================================================================
# ACTION HANDLERS
# ===========================================================================

def _handler_http(node: Node, ctx: dict) -> Any:
    """HTTP GET/POST — real urllib call. Supports templating from context."""
    url = _render(node.config.get("url", ""), ctx)
    method = node.config.get("method", "GET").upper()
    headers = node.config.get("headers", {})
    body = node.config.get("body")
    timeout = node.config.get("timeout", 10)

    if not url:
        raise ValueError(f"http node '{node.id}': url is required")

    req_data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            req_data = json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
        else:
            req_data = str(body).encode()

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = content
            return {"status": resp.status, "body": parsed}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", errors="replace"), "error": True}
    except urllib.error.URLError as e:
        return {"status": 0, "error": str(e.reason)}


def _handler_llm(node: Node, ctx: dict) -> Any:
    """LLM call via Ollama HTTP API (http://localhost:11434 by default).

    Config:
      model: "qwen2.5:14b" (required)
      prompt: template string with {{key}} substitutions (required)
      host:  "http://localhost:11434" (optional)
      system: system prompt (optional)
    """
    model = node.config.get("model")
    prompt = _render(node.config.get("prompt", ""), ctx)
    system = node.config.get("system", "")
    host = node.config.get("host", "http://localhost:11434")

    if not model:
        raise ValueError(f"llm node '{node.id}': model is required")
    if not prompt:
        raise ValueError(f"llm node '{node.id}': prompt is required")

    payload = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system

    req = urllib.request.Request(
        f"{host}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=node.config.get("timeout", 60)) as resp:
            data = json.loads(resp.read().decode())
            return {"response": data.get("response", ""), "model": model}
    except urllib.error.URLError as e:
        # Honest error — no fake completion
        raise RuntimeError(
            f"llm node '{node.id}': could not reach Ollama at {host} ({e.reason}). "
            f"Start Ollama or change the 'host' config."
        )


def _handler_transform(node: Node, ctx: dict) -> Any:
    """Pick a field from context (dot notation) or apply a simple transform.

    Config:
      field: "data.users.0.name"   — extract nested path
      operation: "upper" | "lower" | "length" | "json_parse" | "json_stringify"
      input: key in ctx to transform (required if using operation)
    """
    if "field" in node.config:
        return _get_path(ctx, node.config["field"])

    op = node.config.get("operation")
    if not op:
        raise ValueError(f"transform node '{node.id}': need 'field' or 'operation'")
    src_key = node.config.get("input")
    if not src_key:
        raise ValueError(f"transform node '{node.id}': 'input' required with operation")
    value = ctx.get(src_key)

    if op == "upper":
        return str(value).upper()
    if op == "lower":
        return str(value).lower()
    if op == "length":
        return len(value) if value is not None else 0
    if op == "json_parse":
        return json.loads(str(value))
    if op == "json_stringify":
        return json.dumps(value, default=str)
    raise ValueError(f"transform node '{node.id}': unknown operation '{op}'")


def _handler_condition(node: Node, ctx: dict) -> Any:
    """Evaluate a condition and route to on_true/on_false.

    Config:
      left: key or literal
      op:   "==" | "!=" | "<" | ">" | "<=" | ">=" | "contains" | "exists"
      right: key or literal
    """
    left = _resolve(node.config.get("left"), ctx)
    right = _resolve(node.config.get("right"), ctx)
    op = node.config.get("op", "==")

    result = False
    if op == "==":
        result = left == right
    elif op == "!=":
        result = left != right
    elif op == "<":
        result = left < right
    elif op == ">":
        result = left > right
    elif op == "<=":
        result = left <= right
    elif op == ">=":
        result = left >= right
    elif op == "contains":
        result = right in left if left is not None else False
    elif op == "exists":
        result = left is not None
    else:
        raise ValueError(f"condition node '{node.id}': unknown op '{op}'")

    return {"result": result, "left": left, "right": right, "op": op}


def _handler_loop(node: Node, ctx: dict) -> Any:
    """Iterate over a collection, running a sub-flow for each item.

    Config:
      over: context key holding an iterable
      body: list of node ids to execute per iteration
      item_key: key name in context for the current item (default "item")
    """
    over_key = node.config.get("over")
    body_ids = node.config.get("body", [])
    item_key = node.config.get("item_key", "item")
    if not over_key:
        raise ValueError(f"loop node '{node.id}': 'over' required")

    iterable = ctx.get(over_key, [])
    if not hasattr(iterable, "__iter__"):
        raise ValueError(f"loop node '{node.id}': ctx['{over_key}'] is not iterable")

    flow = ctx.get("__flow__")
    results = []
    for item in iterable:
        ctx[item_key] = item
        for bid in body_ids:
            if bid in flow.nodes:
                result = _execute_node(flow.nodes[bid], ctx, flow)
                ctx[bid] = result
        results.append({k: ctx.get(k) for k in body_ids})

    return {"iterations": len(results), "results": results}


def _handler_python(node: Node, ctx: dict) -> Any:
    """Run a Python callable passed in config['fn'] with ctx as arg.

    This exists so BoRLang users can drop back to full Python when needed.
    Requires explicit callable — no eval() of arbitrary strings.
    """
    fn = node.config.get("fn")
    if not callable(fn):
        raise ValueError(f"python node '{node.id}': 'fn' must be callable")
    return fn(ctx)


def _handler_action(node: Node, ctx: dict) -> Any:
    """Generic action — runs a named handler registered on the flow."""
    name = node.config.get("name")
    flow = ctx.get("__flow__")
    handler = flow._handlers.get(name) if flow else None
    if handler is None:
        raise ValueError(f"action node '{node.id}': no handler '{name}' registered")
    return handler(node.config, ctx)


def _handler_print(node: Node, ctx: dict) -> Any:
    """Print a message (templated from context)."""
    msg = _render(node.config.get("message", ""), ctx)
    print(f"[{node.id}] {msg}")
    return msg


HANDLERS: dict[str, Callable[[Node, dict], Any]] = {
    "http": _handler_http,
    "llm": _handler_llm,
    "transform": _handler_transform,
    "condition": _handler_condition,
    "loop": _handler_loop,
    "python": _handler_python,
    "action": _handler_action,
    "print": _handler_print,
}


# ===========================================================================
# EXECUTION ENGINE
# ===========================================================================

def _execute_node(node: Node, ctx: dict, flow: Flow) -> Any:
    """Run a single node and return its result."""
    handler = HANDLERS.get(node.type)
    if handler is None:
        raise ValueError(f"unknown node type: {node.type}")

    start = time.time()
    try:
        result = handler(node, ctx)
        status = "ok"
        error = None
    except Exception as e:
        result = None
        status = "error"
        error = str(e)

    flow.trace.append({
        "node": node.id,
        "type": node.type,
        "status": status,
        "duration_ms": int((time.time() - start) * 1000),
        "result_preview": _preview(result),
        "error": error,
    })

    if status == "error":
        raise RuntimeError(f"node '{node.id}' failed: {error}")
    return result


def run_flow(flow: Flow, initial_context: dict | None = None, max_steps: int = 1000) -> dict:
    """Execute the flow from its start node until no more edges."""
    if flow.start is None:
        raise ValueError(f"flow '{flow.name}' has no start node")

    ctx = dict(initial_context or {})
    ctx["__flow__"] = flow
    flow.context = ctx
    flow.trace = []

    current = flow.start
    steps = 0
    while current is not None:
        if steps >= max_steps:
            raise RuntimeError(f"flow '{flow.name}' exceeded max_steps={max_steps}")
        steps += 1

        if current not in flow.nodes:
            raise ValueError(f"unknown node id: {current}")
        node = flow.nodes[current]
        result = _execute_node(node, ctx, flow)
        ctx[node.id] = result

        # Route to next node
        if node.type == "condition":
            current = node.on_true if result["result"] else node.on_false
        else:
            current = node.next[0] if node.next else None

    # Clean up internal references before returning
    ctx.pop("__flow__", None)
    return ctx


# ===========================================================================
# HELPERS
# ===========================================================================

def _render(template: str, ctx: dict) -> str:
    """Replace {{key}} and {{key.sub}} with context values."""
    import re as _re
    def repl(m):
        path = m.group(1).strip()
        val = _get_path(ctx, path)
        return str(val) if val is not None else ""
    return _re.sub(r"\{\{([^}]+)\}\}", repl, template)


def _get_path(data: Any, path: str) -> Any:
    """Walk a dotted path: 'data.users.0.name'."""
    parts = path.split(".")
    cur = data
    for p in parts:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, list):
            try:
                cur = cur[int(p)]
            except (ValueError, IndexError):
                return None
        else:
            try:
                cur = getattr(cur, p)
            except AttributeError:
                return None
    return cur


def _resolve(value: Any, ctx: dict) -> Any:
    """If value is a string of form '{{path}}', resolve it; else return as-is."""
    if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
        return _get_path(ctx, value[2:-2].strip())
    return value


def _preview(val: Any, limit: int = 80) -> str:
    s = str(val)
    return s if len(s) <= limit else s[:limit] + "..."


# ===========================================================================
# BORLANG-FACING API
# ===========================================================================

def br_flow_new(name: str) -> Flow:
    """Create an empty flow."""
    return Flow(name=name)


def br_flow_add(flow: Flow, node_id: str, node_type: str, config: dict = None) -> Flow:
    """Add a node. First added becomes the start node by default."""
    node = Node(id=node_id, type=node_type, config=config or {})
    flow.nodes[node_id] = node
    if flow.start is None:
        flow.start = node_id
    return flow


def br_flow_connect(flow: Flow, from_id: str, to_id: str) -> Flow:
    """Add a default edge from one node to another."""
    if from_id not in flow.nodes:
        raise ValueError(f"unknown node: {from_id}")
    if to_id not in flow.nodes:
        raise ValueError(f"unknown node: {to_id}")
    flow.nodes[from_id].next.append(to_id)
    return flow


def br_flow_branch(flow: Flow, cond_id: str, true_id: str, false_id: str) -> Flow:
    """Connect a condition node's true/false branches."""
    if cond_id not in flow.nodes:
        raise ValueError(f"unknown node: {cond_id}")
    node = flow.nodes[cond_id]
    if node.type != "condition":
        raise ValueError(f"node '{cond_id}' is not a condition")
    node.on_true = true_id
    node.on_false = false_id
    return flow


def br_flow_set_start(flow: Flow, node_id: str) -> Flow:
    if node_id not in flow.nodes:
        raise ValueError(f"unknown node: {node_id}")
    flow.start = node_id
    return flow


def br_flow_run(flow: Flow, initial: dict = None) -> dict:
    """Run the flow. Returns the final context."""
    return run_flow(flow, initial or {})


def br_flow_trace(flow: Flow) -> list:
    """Return the execution trace of the last run."""
    return flow.trace


def br_flow_to_json(flow: Flow) -> str:
    """Serialize flow structure for UI rendering."""
    return flow.to_json()


def br_flow_register(flow: Flow, name: str, fn: Callable) -> Flow:
    """Register a custom Python handler for 'action' nodes."""
    flow._handlers[name] = fn
    return flow


def build_flow_stdlib() -> dict:
    """Dict of BoRLang names → flow primitives."""
    return {
        "flow_new": br_flow_new,
        "flow_add": br_flow_add,
        "flow_connect": br_flow_connect,
        "flow_branch": br_flow_branch,
        "flow_set_start": br_flow_set_start,
        "flow_run": br_flow_run,
        "flow_trace": br_flow_trace,
        "flow_to_json": br_flow_to_json,
        "flow_register": br_flow_register,
    }
