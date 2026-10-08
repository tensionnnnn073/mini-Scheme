"""词法模块的单元测试（Phase 1）。

覆盖 spec §3 的每种零件、spec §5 的 `-` 歧义（`-7` 是数字、`-` 是符号）、
点对标记 `.` 与小数点 `1.2` 的区分，以及非法输入要抛 SchemeSyntaxError。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

# 让测试能导入 src/ 下的 scheme 包（不依赖当前工作目录）。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import Symbol  # noqa: E402
from scheme.errors import SchemeSyntaxError  # noqa: E402
from scheme.lexer import TokenKind, tokenize  # noqa: E402


def kinds(text):
    """分词后只取类别序列，便于断言。"""
    return [token.kind for token in tokenize(text)]


class TokenizeKindTests(unittest.TestCase):
    """词的类别序列。"""

    def test_simple_application(self):
        self.assertEqual(
            kinds("(+ 1 2.5)"),
            [
                TokenKind.LPAREN,
                TokenKind.SYMBOL,
                TokenKind.INT,
                TokenKind.FLOAT,
                TokenKind.RPAREN,
                TokenKind.EOF,
            ],
        )

    def test_quote_shorthand(self):
        self.assertEqual(kinds("'x"), [TokenKind.QUOTE, TokenKind.SYMBOL, TokenKind.EOF])

    def test_dotted_pair(self):
        self.assertEqual(
            kinds("(1 . 2)"),
            [
                TokenKind.LPAREN,
                TokenKind.INT,
                TokenKind.DOT,
                TokenKind.INT,
                TokenKind.RPAREN,
                TokenKind.EOF,
            ],
        )

    def test_comment_runs_to_end_of_line(self):
        self.assertEqual(
            kinds("(+ 1 2) ; 注释里的 ( ) 与 3\n3"),
            [
                TokenKind.LPAREN,
                TokenKind.SYMBOL,
                TokenKind.INT,
                TokenKind.INT,
                TokenKind.RPAREN,
                TokenKind.INT,
                TokenKind.EOF,
            ],
        )

    def test_empty_input_only_has_eof(self):
        self.assertEqual(kinds(""), [TokenKind.EOF])
        self.assertEqual(kinds("   \n\t ; 只有注释\n"), [TokenKind.EOF])


class TokenizeValueTests(unittest.TestCase):
    """词的值与位置。"""

    def test_integers(self):
        for text, expected in (("42", 42), ("-7", -7), ("0", 0), ("+5", 5)):
            with self.subTest(text=text):
                token = tokenize(text)[0]
                self.assertEqual(token.kind, TokenKind.INT)
                self.assertEqual(token.value, expected)

    def test_floats(self):
        for text, expected in (("3.14", 3.14), ("-0.5", -0.5), (".5", 0.5), ("1.", 1.0)):
            with self.subTest(text=text):
                token = tokenize(text)[0]
                self.assertEqual(token.kind, TokenKind.FLOAT)
                self.assertEqual(token.value, expected)

    def test_booleans(self):
        self.assertIs(tokenize("#t")[0].value, True)
        self.assertIs(tokenize("#f")[0].value, False)
        self.assertEqual(tokenize("#t")[0].kind, TokenKind.BOOL)

    def test_minus_is_symbol_but_negative_number_is_not(self):
        # spec §5：孤立的 `-` 是减法过程；`-7` 必须是数字。
        minus = tokenize("-")[0]
        self.assertEqual((minus.kind, minus.value), (TokenKind.SYMBOL, Symbol("-")))
        self.assertEqual(tokenize("-7")[0].kind, TokenKind.INT)

    def test_symbols_are_case_sensitive(self):
        self.assertEqual(tokenize("foo")[0].value, Symbol("foo"))
        self.assertNotEqual(tokenize("foo")[0].value, Symbol("FOO"))
        self.assertEqual(tokenize("FOO")[0].value.name, "FOO")

    def test_operator_symbols(self):
        for text in ("+", "*", "<=", "null?", "x1"):
            with self.subTest(text=text):
                self.assertEqual(tokenize(text)[0].kind, TokenKind.SYMBOL)

    def test_string_escapes(self):
        cases = [
            ('"a\\nb"', "a\nb"),          # \n
            ('"a\\tb"', "a\tb"),          # \t
            ('"say \\"hi\\""', 'say "hi"'),  # \"
            ('"a\\\\b"', "a\\b"),         # \\
            ('"a\\qb"', "aqb"),           # 未列出的转义按字面字符处理
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(tokenize(source)[0].value, expected)

    def test_string_keeps_spaces_and_delimiters(self):
        self.assertEqual(tokenize('"hello world"')[0].value, "hello world")
        self.assertEqual(tokenize('"(1 2) ; \'"')[0].value, "(1 2) ; '")

    def test_line_and_column(self):
        token = tokenize("\n  foo")[0]
        self.assertEqual((token.line, token.col), (2, 3))


class TokenizeErrorTests(unittest.TestCase):
    """非法输入必须抛 SchemeSyntaxError（而不是让别的异常冒泡）。"""

    def test_unterminated_string(self):
        with self.assertRaises(SchemeSyntaxError):
            tokenize('"abc')

    def test_unterminated_string_across_lines(self):
        with self.assertRaises(SchemeSyntaxError):
            tokenize('"abc\ndef')

    def test_unknown_hash_literal(self):
        with self.assertRaises(SchemeSyntaxError):
            tokenize("#x")


if __name__ == "__main__":
    unittest.main()
