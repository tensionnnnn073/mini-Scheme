"""语法模块的单元测试（Phase 1）。

覆盖 spec §3/§4.1/§6：嵌套表达式、`'expr` 简写、点对 `(a b . c)`、
多顶层表达式、注释与空程序、以及各种括号/点对错误。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import DottedList, Symbol  # noqa: E402
from scheme.errors import SchemeSyntaxError  # noqa: E402
from scheme.parser import parse  # noqa: E402


class ParseExpressionTests(unittest.TestCase):
    """表达式结构。"""

    def test_application(self):
        self.assertEqual(parse("(+ 1 2)"), [[Symbol("+"), 1, 2]])

    def test_nested_application(self):
        self.assertEqual(
            parse("(* (+ 1 2) 3)"),
            [[Symbol("*"), [Symbol("+"), 1, 2], 3]],
        )

    def test_basic_values(self):
        self.assertEqual(
            parse('#t #f -7 3.14 x "s"'),
            [True, False, -7, 3.14, Symbol("x"), "s"],
        )

    def test_quote_shorthand_equals_quote_form(self):
        self.assertEqual(parse("'x"), [[Symbol("quote"), Symbol("x")]])
        self.assertEqual(parse("'x"), parse("(quote x)"))

    def test_quote_of_list(self):
        self.assertEqual(parse("'(1 2 3)"), [[Symbol("quote"), [1, 2, 3]]])
        self.assertEqual(parse("'()"), [[Symbol("quote"), []]])

    def test_nested_quote(self):
        self.assertEqual(parse("''x"), [[Symbol("quote"), [Symbol("quote"), Symbol("x")]]])

    def test_multiple_top_level_expressions(self):
        self.assertEqual(parse("1 2 3"), [1, 2, 3])

    def test_comments_and_blank_lines(self):
        source = "; 第一行注释\n(+ 1 2)\n\n; 再一条\n3\n"
        self.assertEqual(parse(source), [[Symbol("+"), 1, 2], 3])

    def test_empty_program(self):
        self.assertEqual(parse(""), [])
        self.assertEqual(parse("   \n; 只有注释"), [])

    def test_dotted_pair(self):
        node = parse("(1 . 2)")[0]
        self.assertIsInstance(node, DottedList)
        self.assertEqual(node.items, [1])
        self.assertEqual(node.tail, 2)

    def test_dotted_pair_with_several_items(self):
        node = parse("(1 2 . 3)")[0]
        self.assertEqual((node.items, node.tail), ([1, 2], 3))

    def test_dotted_pair_inside_list(self):
        node = parse("(1 (2 . 3))")[0]
        self.assertEqual(node[0], 1)
        self.assertEqual((node[1].items, node[1].tail), ([2], 3))


class ParseExampleFileTests(unittest.TestCase):
    """示例程序 01–06 必须能完整解析（不崩、不报语法错）。"""

    def test_all_example_files_parse(self):
        example_dir = os.path.join(_ROOT, "example")
        files = sorted(name for name in os.listdir(example_dir) if name.endswith(".scm"))
        self.assertEqual(len(files), 6)
        for name in files:
            with self.subTest(name=name):
                with open(os.path.join(example_dir, name), "r", encoding="utf-8") as handle:
                    self.assertTrue(parse(handle.read()))


class ParseErrorTests(unittest.TestCase):
    """非法结构必须抛 SchemeSyntaxError。"""

    def test_unclosed_paren(self):
        with self.assertRaises(SchemeSyntaxError):
            parse("(+ 1 2")

    def test_unexpected_closing_paren(self):
        with self.assertRaises(SchemeSyntaxError):
            parse(")")

    def test_dot_without_tail(self):
        with self.assertRaises(SchemeSyntaxError):
            parse("(1 . )")

    def test_dot_with_extra_elements(self):
        with self.assertRaises(SchemeSyntaxError):
            parse("(1 . 2 3)")

    def test_dot_at_top_level(self):
        with self.assertRaises(SchemeSyntaxError):
            parse(". 1")

    def test_quote_at_end_of_input(self):
        with self.assertRaises(SchemeSyntaxError):
            parse("'")

    def test_unclosed_paren_after_dot(self):
        with self.assertRaises(SchemeSyntaxError):
            parse("(1 . 2")


if __name__ == "__main__":
    unittest.main()
