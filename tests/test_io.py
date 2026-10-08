"""输出内置过程的单元测试（Phase 7，spec §5 输出两行 / §8 / §11）。

display 的要点：字符串不带引号、不换行、返回 None（所以顶层不打印它），
输出与顶层结果共用标准输出、顺序一致；newline 只输出一个换行。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import contextlib
import io as io_stream
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import main  # noqa: E402  (入口：验证 display 与顶层结果共用输出流)
from scheme.builtins import io as io_builtins  # noqa: E402
from scheme.datatypes import NIL  # noqa: E402
from scheme.errors import SchemeArityError  # noqa: E402
from scheme.evaluator import evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_display, to_write  # noqa: E402


class IoTestBase(unittest.TestCase):
    """公共脚手架：把 display / newline 重装到可抓取的 StringIO 上。"""

    def setUp(self):
        self.env = make_global_env()
        self.out = io_stream.StringIO()
        io_builtins.install(self.env, out=self.out)

    def run_expr(self, text):
        """求值一段只含一个表达式的源码。"""
        return evaluate(parse(text)[0], self.env)

    def printed(self, text):
        """按 CLI 的方式求值整段源码，返回这一次写到输出流里的文本。"""
        for expr in parse(text):
            evaluate(expr, self.env)
        return self.take()

    def take(self):
        """取走并清空目前写到流里的文本（每次断言只看这一次的输出）。"""
        text = self.out.getvalue()
        self.out.seek(0)
        self.out.truncate(0)
        return text


class DisplayTests(IoTestBase):
    """display / newline 的行为（spec §5）。"""

    def test_display_prints_without_a_newline_and_returns_no_value(self):
        self.assertIsNone(self.run_expr("(display 42)"))
        self.assertEqual(self.take(), "42")

    def test_display_of_a_string_has_no_quotes(self):
        self.run_expr('(display "hello")')
        self.assertEqual(self.take(), "hello")

    def test_display_keeps_real_newlines_in_strings(self):
        self.run_expr('(display "a\\nb")')
        self.assertEqual(self.take(), "a\nb")

    def test_display_of_lists_pairs_and_the_empty_list(self):
        self.assertEqual(self.printed("(display '(1 2 3))"), "(1 2 3)")
        self.assertEqual(self.printed("(display (cons 1 2))"), "(1 . 2)")
        self.assertEqual(self.printed("(display '())"), "()")

    def test_display_drops_the_quotes_of_nested_strings(self):
        self.assertEqual(self.printed('(display (list 1 "a"))'), "(1 a)")

    def test_display_of_atoms_and_procedures(self):
        self.assertEqual(self.printed("(display 'foo)"), "foo")
        self.assertEqual(self.printed("(display #t)"), "#t")
        self.assertEqual(self.printed("(display #f)"), "#f")
        self.assertEqual(self.printed("(display 0.5)"), "0.5")
        self.assertEqual(self.printed("(display car)"), "#<procedure>")
        self.assertEqual(self.printed("(display (lambda (x) x))"), "#<procedure>")

    def test_display_is_usable_for_side_effects(self):
        self.assertEqual(self.run_expr('(begin (display "x") 5)'), 5)
        self.assertEqual(self.take(), "x")

    def test_newline_writes_one_newline_and_returns_no_value(self):
        self.assertIsNone(self.run_expr("(newline)"))
        self.assertEqual(self.take(), "\n")

    def test_display_and_newline_in_sequence(self):
        self.assertEqual(self.printed("(display 1) (newline) (display 2)"), "1\n2")


class EntryPointOutputTests(unittest.TestCase):
    """入口把 display 的输出与顶层结果的打印写进同一个流（spec §2/§11）。"""

    def run_source(self, text):
        stream = io_stream.StringIO()
        with contextlib.redirect_stdout(stream):
            main.run_source(text, make_global_env())
        return stream.getvalue()

    def test_display_result_is_not_printed_again(self):
        self.assertEqual(self.run_source("(display 1) (newline) (* 2 3)"), "1\n6\n")

    def test_top_level_uses_write_form_while_display_does_not(self):
        # 顶层结果带引号并换行；display 的字符串不带引号、不补换行（spec §8）
        self.assertEqual(self.run_source('(display "hi")\n"hi"'), 'hi"hi"\n')


class PrinterDisplayFormTests(unittest.TestCase):
    """printer.to_display：与 write 形式的差别只在字符串（spec §8）。"""

    def test_strings_lose_quotes_and_escapes(self):
        self.assertEqual(to_display('a"b'), 'a"b')
        self.assertEqual(to_write('a"b'), '"a\\"b"')

    def test_other_values_are_unchanged(self):
        for value in (42, True, False, 0.5, NIL):
            with self.subTest(value=value):
                self.assertEqual(to_display(value), to_write(value))


class IoArityTests(IoTestBase):
    """参数个数不符抛 SchemeArityError（spec §11）。"""

    def test_arity_errors(self):
        for source in ("(display)", "(display 1 2)", "(newline 1)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeArityError):
                    self.run_expr(source)


if __name__ == "__main__":
    unittest.main()
