"""打印模块与点对链表示的单元测试（Phase 1）。

重点：
1. spec §8 的打印表（含浮点 `0.5` 形式、字符串转义）；
2. 往返一致性：源文本 → 解析 → 转成数据 → 打印，应与源文本一致；
3. quote 数据与 cons 产物的表示一致性（spec §6/§11：不能打印成 `(1 2 . 3)` 或卡死）。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import NIL, Pair, Symbol, iter_list, scheme_list, to_data  # noqa: E402
from scheme.errors import SchemeTypeError  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_write  # noqa: E402


class WriteFormTests(unittest.TestCase):
    """spec §8 的打印表。"""

    def test_scalars(self):
        cases = [
            (True, "#t"),
            (False, "#f"),
            (42, "42"),
            (-7, "-7"),
            (0, "0"),
            (0.5, "0.5"),
            (3.14, "3.14"),
            (-0.5, "-0.5"),
            (2.0, "2.0"),
            (Symbol("foo"), "foo"),
            (Symbol("+"), "+"),
            (NIL, "()"),
            ("hello", '"hello"'),
            ("a\nb", '"a\\nb"'),
            ("a\tb", '"a\\tb"'),
            ('say "hi"', '"say \\"hi\\""'),
            ("a\\b", '"a\\\\b"'),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(to_write(value), expected)

    def test_pairs(self):
        cases = [
            (Pair(1, 2), "(1 . 2)"),
            (scheme_list([1, 2, 3]), "(1 2 3)"),
            (Pair(1, Pair(2, 3)), "(1 2 . 3)"),
            (Pair(NIL, NIL), "(())"),
            (scheme_list([]), "()"),
            (scheme_list([scheme_list([1, 2]), 3]), "((1 2) 3)"),
            (scheme_list([Symbol("a"), "s", 1.5, True]), '(a "s" 1.5 #t)'),
        ]
        for value, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(to_write(value), expected)


class RoundTripTests(unittest.TestCase):
    """源文本 → 解析 → to_data → to_write 应与源文本一致。"""

    CASES = [
        ("(1 2 3)", "(1 2 3)"),
        ("(1 . 2)", "(1 . 2)"),
        ("(1 2 . 3)", "(1 2 . 3)"),
        ("()", "()"),
        ("#t", "#t"),
        ("#f", "#f"),
        ("-7", "-7"),
        ("3.14", "3.14"),
        ("-0.5", "-0.5"),
        ("x", "x"),
        ("foo", "foo"),
        ('"hello world"', '"hello world"'),
        ('"a\\nb"', '"a\\nb"'),
        ('"say \\"hi\\""', '"say \\"hi\\""'),
        ("((1 2) (3 . 4))", "((1 2) (3 . 4))"),
        ('(a "s" 1.5 #t)', '(a "s" 1.5 #t)'),
    ]

    def test_round_trip(self):
        for source, expected in self.CASES:
            with self.subTest(source=source):
                self.assertEqual(to_write(to_data(parse(source)[0])), expected)


class ListRepresentationTests(unittest.TestCase):
    """quote 的数据必须是和 cons 一致的点对链（spec §6/§11）。"""

    def test_quote_data_matches_cons_construction(self):
        quoted = to_data(parse("(1 2 3)")[0])  # '(1 2 3) 走 quote 路线
        built = scheme_list([1, 2, 3])  # (list 1 2 3) 走 cons 路线
        self.assertEqual(to_write(quoted), to_write(built))
        self.assertEqual(iter_list(quoted), [1, 2, 3])

    def test_chain_shape_ends_with_nil(self):
        quoted = to_data(parse("(1 2 3)")[0])
        self.assertIsInstance(quoted, Pair)
        self.assertEqual(quoted.car, 1)
        self.assertIsInstance(quoted.cdr, Pair)
        self.assertEqual(quoted.cdr.car, 2)
        self.assertEqual(quoted.cdr.cdr.car, 3)
        self.assertIs(quoted.cdr.cdr.cdr, NIL)

    def test_empty_list_is_the_single_nil_object(self):
        self.assertIs(to_data(parse("()")[0]), NIL)
        self.assertIs(scheme_list([]), NIL)

    def test_nested_data(self):
        value = to_data(parse("((1 2) (3 . 4))")[0])
        self.assertEqual(to_write(value), "((1 2) (3 . 4))")

    def test_iter_list_rejects_improper_list(self):
        with self.assertRaises(SchemeTypeError):
            iter_list(Pair(1, 2))

    def test_iter_list_of_empty_list(self):
        self.assertEqual(iter_list(NIL), [])


if __name__ == "__main__":
    unittest.main()
