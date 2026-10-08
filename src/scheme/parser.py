"""语法：词 → 表达式（嵌套数据结构）。spec §3 / §4 / §6。

公开接口：
    parse(text)          文本 → list[表达式]（顶层表达式的序列）
    parse_tokens(tokens) 词列表 → list[表达式]（便于单元测试）

表达式结构（还是"源程序的结构"，没有转成运行时数据）：
    基本值    int / float / bool / str / Symbol
    函数调用  Python list，例如 (+ 1 2) → [Symbol("+"), 1, 2]
    引用简写  'expr → [Symbol("quote"), expr]
    点对写法  (a b . c) → datatypes.DottedList([a, b], c)

quote 里的数据要到求值阶段由 datatypes.to_data 转成与 cons 一致的点对链
（spec §6、§11），本模块不负责这一步。
"""
from __future__ import annotations

from .datatypes import DottedList, Symbol
from .errors import SchemeSyntaxError
from .lexer import Token, TokenKind, tokenize


def parse(text: str) -> "list":
    """解析一段程序文本，返回其中的顶层表达式列表（spec §3/§4/§6）。"""
    return parse_tokens(tokenize(text))


def parse_tokens(tokens: "list") -> "list":
    """把词列表解析成顶层表达式列表（parse 的底层步骤，便于单元测试）。"""
    reader = _Reader(tokens)
    expressions = []
    while not reader.at_end():
        expressions.append(reader.read_expression())
    return expressions


class _Reader:
    """一次性读词器：把词序列读成嵌套的表达式结构。"""

    def __init__(self, tokens: "list") -> None:
        self._tokens = list(tokens)
        self._index = 0

    def at_end(self) -> bool:
        """是否已经读到输入结束。"""
        return self._peek().kind == TokenKind.EOF

    def read_expression(self) -> object:
        """读出一个完整的表达式。"""
        token = self._next()
        kind = token.kind
        if kind == TokenKind.LPAREN:
            return self._read_list(token)
        if kind == TokenKind.RPAREN:
            raise SchemeSyntaxError(f"第 {token.line} 行第 {token.col} 列：多余的 )")
        if kind == TokenKind.QUOTE:
            # spec §4.1：'expr 就是 (quote expr) 的简写
            return [Symbol("quote"), self.read_expression()]
        if kind == TokenKind.DOT:
            raise SchemeSyntaxError(
                f"第 {token.line} 行第 {token.col} 列：点对标记 . 只能出现在括号里"
            )
        if kind == TokenKind.EOF:
            raise SchemeSyntaxError(f"第 {token.line} 行：程序意外结束（缺少表达式）")
        return token.value

    def _peek(self) -> Token:
        """看下一个词（不消费）。"""
        return self._tokens[self._index]

    def _next(self) -> Token:
        """取下一个词并前移；EOF 会一直被返回，避免越界。"""
        token = self._tokens[self._index]
        if token.kind != TokenKind.EOF:
            self._index += 1
        return token

    def _read_list(self, open_token: Token) -> object:
        """读一个括号结构；返回 list（真列表）或 DottedList（点对写法）。"""
        items = []
        while True:
            token = self._peek()
            if token.kind == TokenKind.RPAREN:
                self._next()
                return items
            if token.kind == TokenKind.EOF:
                raise SchemeSyntaxError(f"第 {open_token.line} 行的 ( 没有对应的 )")
            if token.kind == TokenKind.DOT:  # spec §6 的点对写法 (a b . c)
                if not items:
                    raise SchemeSyntaxError(
                        f"第 {token.line} 行第 {token.col} 列：点对标记 . 前面至少要有一个元素"
                    )
                self._next()
                tail = self.read_expression()
                closing = self._peek()
                if closing.kind != TokenKind.RPAREN:
                    raise SchemeSyntaxError(
                        f"第 {closing.line} 行第 {closing.col} 列：点对的尾巴之后必须是 )"
                    )
                self._next()
                return DottedList(items, tail)
            items.append(self.read_expression())
