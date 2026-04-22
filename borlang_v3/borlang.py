"""
BoRLang v0.2 — handwritten lexer + recursive descent parser + tree-walk interpreter.

Design:
- Zero external parsing deps (only uses the standard library for the core).
- Clean AST nodes as dataclasses — easy to extend.
- Lexical scoping, first-class functions, if/while/for, lists, dicts, method calls.

CLI:
    python borlang.py              # REPL
    python borlang.py file.bor     # run a file
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from borlang_stdlib import build_stdlib


# ===========================================================================
# LEXER
# ===========================================================================

T_NUM = "NUM"
T_STR = "STR"
T_NAME = "NAME"
T_KW = "KW"
T_OP = "OP"
T_NEWLINE = "NL"
T_EOF = "EOF"

KEYWORDS = {
    "if", "elif", "else", "end",
    "while", "for", "in",
    "def", "return",
    "true", "false", "nil",
    "and", "or", "not",
}

# Sorted longest-first so "==" matches before "="
OPERATORS = [
    "==", "!=", "<=", ">=",
    "=", "<", ">",
    "+", "-", "*", "/", "%",
    "(", ")", "[", "]", "{", "}",
    ",", ":", ".",
]


@dataclass
class Token:
    type: str
    value: Any
    line: int


class LexError(RuntimeError):
    pass


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    i, line, n = 0, 1, len(src)

    while i < n:
        c = src[i]

        if c == "\n":
            tokens.append(Token(T_NEWLINE, "\n", line))
            line += 1
            i += 1
            continue

        if c in " \t\r":
            i += 1
            continue

        # Comments: # ... or // ...
        if c == "#" or (c == "/" and i + 1 < n and src[i + 1] == "/"):
            while i < n and src[i] != "\n":
                i += 1
            continue

        # String literal
        if c == '"' or c == "'":
            quote, j, buf = c, i + 1, []
            while j < n and src[j] != quote:
                if src[j] == "\\" and j + 1 < n:
                    nxt = src[j + 1]
                    buf.append({"n": "\n", "t": "\t", "\\": "\\", quote: quote}.get(nxt, nxt))
                    j += 2
                    continue
                buf.append(src[j])
                j += 1
            if j >= n:
                raise LexError(f"unterminated string at line {line}")
            tokens.append(Token(T_STR, "".join(buf), line))
            i = j + 1
            continue

        # Number
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            j, saw_dot = i, False
            while j < n and (src[j].isdigit() or (src[j] == "." and not saw_dot)):
                if src[j] == ".":
                    saw_dot = True
                j += 1
            num_str = src[i:j]
            tokens.append(Token(T_NUM, float(num_str) if saw_dot else int(num_str), line))
            i = j
            continue

        # Identifier or keyword
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            tokens.append(Token(T_KW if word in KEYWORDS else T_NAME, word, line))
            i = j
            continue

        # Operator
        matched = False
        for op in OPERATORS:
            if src.startswith(op, i):
                tokens.append(Token(T_OP, op, line))
                i += len(op)
                matched = True
                break
        if matched:
            continue

        raise LexError(f"unexpected character {c!r} at line {line}")

    tokens.append(Token(T_EOF, None, line))
    return tokens


# ===========================================================================
# AST
# ===========================================================================

@dataclass
class Num: value: float
@dataclass
class Str: value: str
@dataclass
class Bool: value: bool
@dataclass
class Nil: pass
@dataclass
class Var: name: str
@dataclass
class ListLit: items: list
@dataclass
class DictLit: pairs: list
@dataclass
class BinOp: op: str; left: Any; right: Any
@dataclass
class UnaryNot: expr: Any
@dataclass
class Compare: op: str; left: Any; right: Any
@dataclass
class And: left: Any; right: Any
@dataclass
class Or: left: Any; right: Any
@dataclass
class Call: fn: Any; args: list
@dataclass
class Index: target: Any; key: Any
@dataclass
class Attr: target: Any; name: str
@dataclass
class Assign: target: str; value: Any
@dataclass
class IndexAssign: target: Any; key: Any; value: Any
@dataclass
class AttrAssign: target: Any; name: str; value: Any
@dataclass
class If: branches: list; else_body: list | None
@dataclass
class While: cond: Any; body: list
@dataclass
class For: var: str; iterable: Any; body: list
@dataclass
class FuncDef: name: str; params: list; body: list
@dataclass
class Return: value: Any
@dataclass
class ExprStmt: expr: Any


# ===========================================================================
# PARSER
# ===========================================================================

class ParseError(RuntimeError):
    pass


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = [t for t in tokens if t.type != T_NEWLINE]
        self.pos = 0

    def peek(self, offset=0) -> Token:
        return self.tokens[self.pos + offset]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def check(self, ttype, value=None) -> bool:
        tok = self.peek()
        return tok.type == ttype and (value is None or tok.value == value)

    def match(self, ttype, value=None) -> bool:
        if self.check(ttype, value):
            self.advance()
            return True
        return False

    def expect(self, ttype, value=None) -> Token:
        if not self.check(ttype, value):
            tok = self.peek()
            want = ttype + (f"({value!r})" if value else "")
            raise ParseError(
                f"expected {want} at line {tok.line}, got {tok.type}({tok.value!r})"
            )
        return self.advance()

    def parse_program(self) -> list:
        stmts = []
        while not self.check(T_EOF):
            stmts.append(self.parse_statement())
        return stmts

    def parse_statement(self):
        tok = self.peek()
        if tok.type == T_KW:
            if tok.value == "if":     return self.parse_if()
            if tok.value == "while":  return self.parse_while()
            if tok.value == "for":    return self.parse_for()
            if tok.value == "def":    return self.parse_def()
            if tok.value == "return": return self.parse_return()
        return self.parse_assign_or_expr()

    def parse_assign_or_expr(self):
        expr = self.parse_expr()
        if self.match(T_OP, "="):
            rhs = self.parse_expr()
            if isinstance(expr, Var):
                return Assign(target=expr.name, value=rhs)
            if isinstance(expr, Index):
                return IndexAssign(target=expr.target, key=expr.key, value=rhs)
            if isinstance(expr, Attr):
                return AttrAssign(target=expr.target, name=expr.name, value=rhs)
            raise ParseError(f"invalid assignment target: {type(expr).__name__}")
        return ExprStmt(expr=expr)

    def parse_if(self):
        self.expect(T_KW, "if")
        cond = self.parse_expr()
        self.match(T_OP, ":")
        branches = [(cond, self.parse_block({"elif", "else", "end"}))]
        while self.match(T_KW, "elif"):
            c = self.parse_expr()
            self.match(T_OP, ":")
            branches.append((c, self.parse_block({"elif", "else", "end"})))
        else_body = None
        if self.match(T_KW, "else"):
            self.match(T_OP, ":")
            else_body = self.parse_block({"end"})
        self.expect(T_KW, "end")
        return If(branches=branches, else_body=else_body)

    def parse_while(self):
        self.expect(T_KW, "while")
        cond = self.parse_expr()
        self.match(T_OP, ":")
        body = self.parse_block({"end"})
        self.expect(T_KW, "end")
        return While(cond=cond, body=body)

    def parse_for(self):
        self.expect(T_KW, "for")
        var = self.expect(T_NAME).value
        self.expect(T_KW, "in")
        iterable = self.parse_expr()
        self.match(T_OP, ":")
        body = self.parse_block({"end"})
        self.expect(T_KW, "end")
        return For(var=var, iterable=iterable, body=body)

    def parse_def(self):
        self.expect(T_KW, "def")
        name = self.expect(T_NAME).value
        self.expect(T_OP, "(")
        params = []
        if not self.check(T_OP, ")"):
            params.append(self.expect(T_NAME).value)
            while self.match(T_OP, ","):
                params.append(self.expect(T_NAME).value)
        self.expect(T_OP, ")")
        self.match(T_OP, ":")
        body = self.parse_block({"end"})
        self.expect(T_KW, "end")
        return FuncDef(name=name, params=params, body=body)

    def parse_return(self):
        self.expect(T_KW, "return")
        if (self.check(T_KW) and self.peek().value in {"end", "elif", "else"}) or self.check(T_EOF):
            return Return(value=Nil())
        return Return(value=self.parse_expr())

    def parse_block(self, stop: set[str]) -> list:
        stmts = []
        while not (self.check(T_KW) and self.peek().value in stop) and not self.check(T_EOF):
            stmts.append(self.parse_statement())
        return stmts

    # Precedence: or -> and -> not -> compare -> add -> mul -> unary -> postfix -> primary

    def parse_expr(self):         return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.match(T_KW, "or"):
            left = Or(left=left, right=self.parse_and())
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.match(T_KW, "and"):
            left = And(left=left, right=self.parse_not())
        return left

    def parse_not(self):
        if self.match(T_KW, "not"):
            return UnaryNot(expr=self.parse_not())
        return self.parse_compare()

    _COMP_OPS = {"==", "!=", "<", ">", "<=", ">="}

    def parse_compare(self):
        left = self.parse_add()
        while self.check(T_OP) and self.peek().value in self._COMP_OPS:
            op = self.advance().value
            left = Compare(op=op, left=left, right=self.parse_add())
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.check(T_OP) and self.peek().value in ("+", "-"):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self.parse_mul())
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.check(T_OP) and self.peek().value in ("*", "/", "%"):
            op = self.advance().value
            left = BinOp(op=op, left=left, right=self.parse_unary())
        return left

    def parse_unary(self):
        if self.match(T_OP, "-"):
            return BinOp(op="-", left=Num(value=0), right=self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        while True:
            if self.match(T_OP, "."):
                name = self.expect(T_NAME).value
                expr = Attr(target=expr, name=name)
            elif self.match(T_OP, "["):
                key = self.parse_expr()
                self.expect(T_OP, "]")
                expr = Index(target=expr, key=key)
            elif self.match(T_OP, "("):
                args = []
                if not self.check(T_OP, ")"):
                    args.append(self.parse_expr())
                    while self.match(T_OP, ","):
                        args.append(self.parse_expr())
                self.expect(T_OP, ")")
                expr = Call(fn=expr, args=args)
            else:
                break
        return expr

    def parse_primary(self):
        tok = self.peek()

        if tok.type == T_NUM:
            self.advance()
            return Num(value=tok.value)
        if tok.type == T_STR:
            self.advance()
            return Str(value=tok.value)
        if tok.type == T_KW:
            if tok.value == "true":
                self.advance(); return Bool(value=True)
            if tok.value == "false":
                self.advance(); return Bool(value=False)
            if tok.value == "nil":
                self.advance(); return Nil()
        if tok.type == T_NAME:
            self.advance()
            return Var(name=tok.value)
        if tok.type == T_OP:
            if tok.value == "(":
                self.advance()
                e = self.parse_expr()
                self.expect(T_OP, ")")
                return e
            if tok.value == "[":
                self.advance()
                items = []
                if not self.check(T_OP, "]"):
                    items.append(self.parse_expr())
                    while self.match(T_OP, ","):
                        items.append(self.parse_expr())
                self.expect(T_OP, "]")
                return ListLit(items=items)
            if tok.value == "{":
                self.advance()
                pairs = []
                if not self.check(T_OP, "}"):
                    pairs.append(self._parse_dict_pair())
                    while self.match(T_OP, ","):
                        pairs.append(self._parse_dict_pair())
                self.expect(T_OP, "}")
                return DictLit(pairs=pairs)

        raise ParseError(
            f"unexpected token at line {tok.line}: {tok.type}({tok.value!r})"
        )

    def _parse_dict_pair(self):
        tok = self.peek()
        if tok.type == T_STR:
            key = self.advance().value
        elif tok.type == T_NAME:
            key = self.advance().value
        else:
            raise ParseError(f"dict key must be string or name at line {tok.line}")
        self.expect(T_OP, ":")
        return (key, self.parse_expr())


# ===========================================================================
# INTERPRETER
# ===========================================================================

class BorLangError(RuntimeError):
    pass


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class Env:
    def __init__(self, parent=None):
        self.vars: dict = {}
        self.parent = parent

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise BorLangError(f"undefined: {name}")

    def set_new(self, name, value):
        self.vars[name] = value

    def assign(self, name, value):
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        self.vars[name] = value


class UserFunction:
    def __init__(self, name, params, body, closure, interp):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.interp = interp

    def __call__(self, *args):
        if len(args) != len(self.params):
            raise BorLangError(
                f"{self.name}() expected {len(self.params)} args, got {len(args)}"
            )
        local = Env(parent=self.closure)
        for p, v in zip(self.params, args):
            local.set_new(p, v)
        try:
            self.interp._exec_block(self.body, local)
        except ReturnSignal as r:
            return r.value
        return None


class Interpreter:
    def __init__(self):
        self.globals = Env()
        for name, fn in build_stdlib().items():
            self.globals.set_new(name, fn)

    def run(self, src: str):
        ast = Parser(tokenize(src)).parse_program()
        return self._exec_block(ast, self.globals)

    def _exec_block(self, stmts, env):
        result = None
        for stmt in stmts:
            result = self._exec(stmt, env)
        return result

    def _exec(self, node, env):
        method = getattr(self, f"_exec_{type(node).__name__}", None)
        if method is None:
            return self._eval(node, env)
        return method(node, env)

    def _exec_ExprStmt(self, node, env):
        return self._eval(node.expr, env)

    def _exec_Assign(self, node, env):
        value = self._eval(node.value, env)
        env.assign(node.target, value)
        return value

    def _exec_IndexAssign(self, node, env):
        t = self._eval(node.target, env)
        k = self._eval(node.key, env)
        v = self._eval(node.value, env)
        t[k] = v
        return v

    def _exec_AttrAssign(self, node, env):
        t = self._eval(node.target, env)
        v = self._eval(node.value, env)
        if isinstance(t, dict):
            t[node.name] = v
        else:
            setattr(t, node.name, v)
        return v

    def _exec_If(self, node, env):
        for cond, body in node.branches:
            if self._truthy(self._eval(cond, env)):
                self._exec_block(body, env)
                return None
        if node.else_body is not None:
            self._exec_block(node.else_body, env)

    def _exec_While(self, node, env):
        while self._truthy(self._eval(node.cond, env)):
            self._exec_block(node.body, env)

    def _exec_For(self, node, env):
        iterable = self._eval(node.iterable, env)
        for item in iterable:
            env.assign(node.var, item)
            self._exec_block(node.body, env)

    def _exec_FuncDef(self, node, env):
        fn = UserFunction(node.name, node.params, node.body, env, self)
        env.set_new(node.name, fn)

    def _exec_Return(self, node, env):
        raise ReturnSignal(self._eval(node.value, env))

    # ---- expression evaluation ----

    def _eval(self, node, env):
        method = getattr(self, f"_eval_{type(node).__name__}", None)
        if method is None:
            raise BorLangError(f"cannot evaluate: {type(node).__name__}")
        return method(node, env)

    def _eval_Num(self, node, env): return node.value
    def _eval_Str(self, node, env): return node.value
    def _eval_Bool(self, node, env): return node.value
    def _eval_Nil(self, node, env): return None
    def _eval_Var(self, node, env): return env.get(node.name)

    def _eval_ListLit(self, node, env):
        return [self._eval(i, env) for i in node.items]

    def _eval_DictLit(self, node, env):
        return {k: self._eval(v, env) for k, v in node.pairs}

    def _eval_BinOp(self, node, env):
        a, b = self._eval(node.left, env), self._eval(node.right, env)
        op = node.op
        if op == "+":
            if isinstance(a, str) or isinstance(b, str):
                return str(a) + str(b)
            return a + b
        if op == "-": return a - b
        if op == "*": return a * b
        if op == "/": return a / b
        if op == "%": return a % b
        raise BorLangError(f"bad op: {op}")

    def _eval_UnaryNot(self, node, env):
        return not self._truthy(self._eval(node.expr, env))

    def _eval_Compare(self, node, env):
        a, b = self._eval(node.left, env), self._eval(node.right, env)
        op = node.op
        return {
            "==": a == b, "!=": a != b,
            "<": a < b, ">": a > b,
            "<=": a <= b, ">=": a >= b,
        }[op]

    def _eval_And(self, node, env):
        a = self._eval(node.left, env)
        return a if not self._truthy(a) else self._eval(node.right, env)

    def _eval_Or(self, node, env):
        a = self._eval(node.left, env)
        return a if self._truthy(a) else self._eval(node.right, env)

    def _eval_Call(self, node, env):
        if isinstance(node.fn, Attr):
            obj = self._eval(node.fn.target, env)
            method = getattr(obj, node.fn.name, None)
            if method is None:
                raise BorLangError(
                    f"no method '{node.fn.name}' on {type(obj).__name__}"
                )
            return method(*[self._eval(a, env) for a in node.args])
        fn = self._eval(node.fn, env)
        return fn(*[self._eval(a, env) for a in node.args])

    def _eval_Index(self, node, env):
        return self._eval(node.target, env)[self._eval(node.key, env)]

    def _eval_Attr(self, node, env):
        obj = self._eval(node.target, env)
        if isinstance(obj, dict) and node.name in obj:
            return obj[node.name]
        return getattr(obj, node.name)

    @staticmethod
    def _truthy(v) -> bool:
        return bool(v)


# ===========================================================================
# CLI
# ===========================================================================

def main():
    interp = Interpreter()
    if len(sys.argv) > 1:
        interp.run(Path(sys.argv[1]).read_text())
        return

    print("BoRLang v3.0 — type 'exit' to quit")
    buffer = []
    while True:
        try:
            prompt = "... " if buffer else "bor> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip() == "exit" and not buffer:
            break
        buffer.append(line)
        try:
            result = interp.run("\n".join(buffer))
            if result is not None and len(buffer) == 1:
                print(result)
            buffer = []
        except (ParseError, LexError) as e:
            # If it looks incomplete, keep buffering
            if "EOF" in str(e):
                continue
            print(f"parse error: {e}")
            buffer = []
        except Exception as e:
            print(f"error: {e}")
            buffer = []


if __name__ == "__main__":
    main()
