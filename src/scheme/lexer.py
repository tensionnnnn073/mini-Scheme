"""词法：程序文本 → 词（token）列表。spec §3。

负责的零件：注释（`;` 到行尾）、整数、浮点、布尔（#t/#f）、符号、字符串
（`\\n` `\\t` `\\"` `\\\\` 转义）、`'` 引用简写、圆括号、点对标记 `.`。

公开产物：
    TokenKind          词类别：LPAREN RPAREN QUOTE DOT INT FLOAT BOOL STRING SYMBOL EOF
    Token              单个词：kind / value / line / col（行列用于报错定位）
    tokenize(text)     文本 → list[Token]；非法输入抛 SchemeSyntaxError

分词歧义备忘（已按这些规则实现）：
- `-7` / `-0.5` 是数字，孤立的 `-` 是符号（spec §5 的减法与单参数取反）；
- 单独的 `.`（两侧为分隔符）是点对标记，`1.2` / `.5` / `1.` 里的点属于数字；
- 符号大小写敏感（spec §3）；`#` 开头的字面量只认 `#t` 与 `#f`；
- 字符串转义只认 n、t、双引号、反斜杠四种写法，其余反斜杠组合按字面字符处理，
  以此保证"读入 → 打印"往返一致；
- 识别出的符号用 datatypes.Symbol 承载（与字符串是不同类型，spec §11）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .datatypes import Symbol
from .errors import SchemeSyntaxError


class TokenKind:
    """词的类别（用字符串常量，便于调试与测试断言）。"""

    LPAREN = "LPAREN"  # (
    RPAREN = "RPAREN"  # )
    QUOTE = "QUOTE"  # '（引用简写，spec §4.1）
    DOT = "DOT"  # .（点对标记，只出现在括号里，spec §6）
    INT = "INT"  # 42 / -7
    FLOAT = "FLOAT"  # 3.14 / -0.5 / .5
    BOOL = "BOOL"  # #t / #f
    STRING = "STRING"  # "hello"
    SYMBOL = "SYMBOL"  # foo / + / x1
    EOF = "EOF"  # 输入结束（每次分词的末尾都会追加一个）


@dataclass(frozen=True)
class Token:
    """一个词；value 是已经解释好的值：int / float / bool / str / Symbol。"""

    kind: str
    value: object
    line: int
    col: int


# 一个"原子"（数字/符号/布尔/点标记）结束于这些字符：空白、括号、引号、引用符、分号。
_DELIMITERS = frozenset(" \t\r\n()'\";")

_INT_PATTERN = re.compile(r"[+-]?[0-9]+\Z")
_FLOAT_PATTERN = re.compile(r"[+-]?(?:[0-9]+\.[0-9]*|\.[0-9]+)\Z")

# 字符串转义表（spec §3）；未列出的转义按字面字符处理。
_STRING_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def tokenize(text: str) -> "list":
    """把一段 mini-Scheme 程序文本切成词列表（末尾总有一个 EOF 词）。"""
    tokens = []
    index = 0
    line = 1
    col = 1
    length = len(text)

    while index < length:
        char = text[index]

        if char == "\n":  # 换行：只更新行列
            index, line, col = index + 1, line + 1, 1
            continue
        if char in " \t\r":  # 其它空白直接跳过（spec §3：零件之间用空白分开）
            index, col = index + 1, col + 1
            continue
        if char == ";":  # 注释：从 ; 到行尾（spec §3）
            while index < length and text[index] != "\n":
                index, col = index + 1, col + 1
            continue

        start_line, start_col = line, col

        if char == "(":
            tokens.append(Token(TokenKind.LPAREN, "(", start_line, start_col))
            index, col = index + 1, col + 1
            continue
        if char == ")":
            tokens.append(Token(TokenKind.RPAREN, ")", start_line, start_col))
            index, col = index + 1, col + 1
            continue
        if char == "'":  # 'expr 是 (quote expr) 的简写（spec §4.1）
            tokens.append(Token(TokenKind.QUOTE, "'", start_line, start_col))
            index, col = index + 1, col + 1
            continue
        if char == '"':
            value, index, line, col = _read_string(text, index, line, col)
            tokens.append(Token(TokenKind.STRING, value, start_line, start_col))
            continue

        start = index
        while index < length and text[index] not in _DELIMITERS:
            index, col = index + 1, col + 1
        tokens.append(_atom_token(text[start:index], start_line, start_col))

    tokens.append(Token(TokenKind.EOF, None, line, col))
    return tokens


def _read_string(text: str, start: int, line: int, col: int) -> "tuple":
    """从开引号处读一个字符串字面量，返回 (解析后的文本, 新下标, 新行, 新列)。"""
    index = start + 1
    col += 1
    chars = []
    while index < len(text):
        char = text[index]
        if char == '"':
            return "".join(chars), index + 1, line, col + 1
        if char == "\\":
            index += 1
            col += 1
            if index >= len(text):
                break
            escaped = text[index]
            chars.append(_STRING_ESCAPES.get(escaped, escaped))
            index, col = index + 1, col + 1
            continue
        if char == "\n":
            chars.append(char)
            index, line, col = index + 1, line + 1, 1
            continue
        chars.append(char)
        index, col = index + 1, col + 1
    raise SchemeSyntaxError(f"第 {line} 行：字符串未闭合（缺少结尾的双引号）")


def _atom_token(atom: str, line: int, col: int) -> Token:
    """把一个"原子"文本解释成 INT / FLOAT / BOOL / SYMBOL / DOT 词。"""
    if atom == ".":
        return Token(TokenKind.DOT, ".", line, col)
    if atom == "#t":
        return Token(TokenKind.BOOL, True, line, col)
    if atom == "#f":
        return Token(TokenKind.BOOL, False, line, col)
    if atom.startswith("#"):
        raise SchemeSyntaxError(
            f"第 {line} 行第 {col} 列：无法识别的字面量 {atom}（布尔只有 #t 与 #f）"
        )
    if _INT_PATTERN.match(atom):
        return Token(TokenKind.INT, int(atom), line, col)
    if _FLOAT_PATTERN.match(atom):
        return Token(TokenKind.FLOAT, float(atom), line, col)
    return Token(TokenKind.SYMBOL, Symbol(atom), line, col)
