"""Tests for BoRFlow — the agentic workflow engine."""

from borlang import Interpreter
from borlang_flow import Flow, Node, run_flow, br_flow_new, br_flow_add, br_flow_connect


# ===========================================================================
# Direct Python API
# ===========================================================================

def test_sequential_flow():
    """Three print nodes run in order."""
    flow = Flow(name="seq")
    flow.nodes["a"] = Node("a", "print", {"message": "A"}, next=["b"])
    flow.nodes["b"] = Node("b", "print", {"message": "B"}, next=["c"])
    flow.nodes["c"] = Node("c", "print", {"message": "C"})
    flow.start = "a"
    result = run_flow(flow)
    assert result["a"] == "A"
    assert result["b"] == "B"
    assert result["c"] == "C"
    assert len(flow.trace) == 3


def test_transform_field_extraction():
    flow = Flow(name="xform")
    flow.nodes["pick"] = Node("pick", "transform", {"field": "user.name"})
    flow.start = "pick"
    result = run_flow(flow, {"user": {"name": "Borty"}})
    assert result["pick"] == "Borty"


def test_transform_operation():
    flow = Flow(name="xform2")
    flow.nodes["up"] = Node("up", "transform", {"input": "name", "operation": "upper"})
    flow.start = "up"
    result = run_flow(flow, {"name": "hello"})
    assert result["up"] == "HELLO"


def test_condition_true_branch():
    flow = Flow(name="cond")
    flow.nodes["check"] = Node("check", "condition",
                                {"left": "{{x}}", "op": ">", "right": 10},
                                on_true="yes", on_false="no")
    flow.nodes["yes"] = Node("yes", "print", {"message": "big"})
    flow.nodes["no"] = Node("no", "print", {"message": "small"})
    flow.start = "check"
    result = run_flow(flow, {"x": 42})
    assert result["yes"] == "big"
    assert "no" not in result or result.get("no") is None


def test_condition_false_branch():
    flow = Flow(name="cond2")
    flow.nodes["check"] = Node("check", "condition",
                                {"left": "{{x}}", "op": ">", "right": 10},
                                on_true="yes", on_false="no")
    flow.nodes["yes"] = Node("yes", "print", {"message": "big"})
    flow.nodes["no"] = Node("no", "print", {"message": "small"})
    flow.start = "check"
    result = run_flow(flow, {"x": 5})
    assert result["no"] == "small"


def test_loop_over_list():
    captured = []

    def capture(ctx):
        captured.append(ctx["item"])
        return ctx["item"] * 2

    flow = Flow(name="loop")
    flow.nodes["double"] = Node("double", "python", {"fn": capture})
    flow.nodes["iter"] = Node("iter", "loop",
                               {"over": "numbers", "body": ["double"]})
    flow.start = "iter"
    result = run_flow(flow, {"numbers": [1, 2, 3]})
    assert captured == [1, 2, 3]
    assert result["iter"]["iterations"] == 3


def test_python_handler():
    def compute(ctx):
        return ctx.get("x", 0) * 10

    flow = Flow(name="py")
    flow.nodes["calc"] = Node("calc", "python", {"fn": compute})
    flow.start = "calc"
    result = run_flow(flow, {"x": 5})
    assert result["calc"] == 50


def test_custom_action_handler():
    flow = br_flow_new("custom")
    br_flow_add(flow, "run", "action", {"name": "my_handler", "arg": 42})

    def my_handler(config, ctx):
        return config["arg"] + 1

    flow._handlers["my_handler"] = my_handler
    result = run_flow(flow)
    assert result["run"] == 43


def test_template_rendering():
    flow = Flow(name="tpl")
    flow.nodes["msg"] = Node("msg", "print",
                              {"message": "Hello {{name}}, you are {{age}}!"})
    flow.start = "msg"
    result = run_flow(flow, {"name": "Borty", "age": 30})
    assert result["msg"] == "Hello Borty, you are 30!"


def test_flow_trace():
    flow = Flow(name="traced")
    flow.nodes["a"] = Node("a", "print", {"message": "hi"}, next=["b"])
    flow.nodes["b"] = Node("b", "print", {"message": "bye"})
    flow.start = "a"
    run_flow(flow)
    trace = flow.trace
    assert len(trace) == 2
    assert trace[0]["node"] == "a"
    assert trace[0]["status"] == "ok"
    assert "duration_ms" in trace[0]


def test_flow_to_json():
    flow = br_flow_new("serializable")
    br_flow_add(flow, "n1", "print", {"message": "hello"})
    br_flow_add(flow, "n2", "print", {"message": "world"})
    br_flow_connect(flow, "n1", "n2")
    import json
    data = json.loads(flow.to_json())
    assert data["name"] == "serializable"
    assert data["start"] == "n1"
    assert len(data["nodes"]) == 2


def test_error_propagation():
    def boom(ctx):
        raise ValueError("intentional")

    flow = Flow(name="bad")
    flow.nodes["x"] = Node("x", "python", {"fn": boom})
    flow.start = "x"
    try:
        run_flow(flow)
        assert False, "should have raised"
    except RuntimeError as e:
        assert "intentional" in str(e)


# ===========================================================================
# Via BoRLang language
# ===========================================================================

def test_flow_from_borlang_simple():
    i = Interpreter()
    i.run("""
        f = flow_new("test")
        flow_add(f, "hello", "print", {message: "Hello from BoRLang!"})
        flow_add(f, "bye", "print", {message: "Goodbye!"})
        flow_connect(f, "hello", "bye")
        result = flow_run(f)
    """)
    result = i.globals.get("result")
    assert result["hello"] == "Hello from BoRLang!"
    assert result["bye"] == "Goodbye!"


def test_flow_from_borlang_with_condition():
    i = Interpreter()
    i.run("""
        f = flow_new("check_age")
        flow_add(f, "check", "condition", {left: "{{age}}", op: ">=", right: 18})
        flow_add(f, "adult", "print", {message: "adult user"})
        flow_add(f, "minor", "print", {message: "minor user"})
        flow_branch(f, "check", "adult", "minor")
        result = flow_run(f, {age: 25})
    """)
    result = i.globals.get("result")
    assert result["adult"] == "adult user"


def test_flow_from_borlang_transform_chain():
    i = Interpreter()
    i.run("""
        f = flow_new("extract")
        flow_add(f, "pick", "transform", {field: "data.user.name"})
        flow_add(f, "yell", "transform", {input: "pick", operation: "upper"})
        flow_connect(f, "pick", "yell")
        result = flow_run(f, {data: {user: {name: "borty"}}})
    """)
    result = i.globals.get("result")
    assert result["pick"] == "borty"
    assert result["yell"] == "BORTY"


if __name__ == "__main__":
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
