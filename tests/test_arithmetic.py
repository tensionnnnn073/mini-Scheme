"""算术 / 比较 / not 内置过程的单元测试（Phase 2，spec §5）。

这些用例走完整路径：源码文本 → 词法 → 语法 → 求值 → 内置过程，
顺带验证内置过程确实装进了 make_global_env()。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import NIL, Symbol  # noqa: E402
from scheme.errors import (  # noqa: E402
    SchemeArityError,
    SchemeError,
    SchemeNameError,
    SchemeTypeError,
)
from scheme.evaluator import evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402


class ArithmeticTestBase(unittest.TestCase):
    """公共脚手架：每个用例一个全新的全局环境 + 最小求值驱动。"""

    def setUp(self):
        self.env = make_global_env()

    def run_expr(self, text):
        """求值一段只含一个表达式的源码。"""
        return evaluate(parse(text)[0], self.env)


class InstallationTests(ArithmeticTestBase):
    """初始环境里应当有 spec §5 的算术/比较/布尔过程。"""

    NAMES = ("+", "-", "*", "/", "modulo", "quotient", "expt", "abs",
             "=", "<", ">", "<=", ">=", "not")

    def test_all_procedures_are_installed(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                self.env.lookup(name)  # 查不到会抛 SchemeNameError

    def test_global_env_has_no_parent(self):
        self.assertIsNone(self.env.parent)

    def test_environments_are_independent(self):
        other = make_global_env()
        self.env.define("x", 1)
        with self.assertRaises(SchemeNameError):
            other.lookup("x")


class ArithmeticValueTests(ArithmeticTestBase):
    """spec §5 的算术例子与类型规则。"""

    def test_spec_examples(self):
        cases = [
            ("(+ 1 2 3)", 6),
            ("(- 10 4 1)", 5),
            ("(* 2 3 4)", 24),
            ("(/ 7 2)", 3),
            ("(/ -7 2)", -3),
            ("(modulo 17 5)", 2),
            ("(quotient 17 5)", 3),
            ("(quotient -7 2)", -3),
            ("(expt 2 10)", 1024),
            ("(abs (- 5 9))", 4),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(self.run_expr(source), expected)

    def test_identity_values_for_no_arguments(self):
        self.assertEqual(self.run_expr("(+)"), 0)
        self.assertEqual(self.run_expr("(*)"), 1)

    def test_single_argument_minus_negates(self):
        self.assertEqual(self.run_expr("(- 5)"), -5)
        self.assertEqual(self.run_expr("(- -3)"), 3)

    def test_integer_results_stay_integers(self):
        value = self.run_expr("(+ 1 2)")
        self.assertIsInstance(value, int)
        self.assertNotIsInstance(value, bool)
        self.assertEqual(value, 3)

    def test_float_contagion(self):
        self.assertEqual(self.run_expr("(+ 1 2.5)"), 3.5)
        self.assertIsInstance(self.run_expr("(+ 1 2.5)"), float)

    def test_single_argument_division_is_reciprocal(self):
        value = self.run_expr("(/ 2)")
        self.assertIsInstance(value, float)
        self.assertEqual(value, 0.5)
        self.assertEqual(self.run_expr("(/ 4)"), 0.25)

    def test_integer_division_truncates_toward_zero(self):
        cases = [
            ("(/ 7 2)", 3),
            ("(/ -7 2)", -3),
            ("(/ 7 -2)", -3),
            ("(/ -7 -2)", 3),
            ("(/ 26 2 3)", 4),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                value = self.run_expr(source)
                self.assertEqual(value, expected)
                self.assertIsInstance(value, int)

    def test_float_division_when_any_argument_is_float(self):
        self.assertEqual(self.run_expr("(/ 7 2.0)"), 3.5)

    def test_modulo_uses_python_semantics(self):
        self.assertEqual(self.run_expr("(modulo 17 5)"), 2)
        self.assertEqual(self.run_expr("(modulo -7 2)"), 1)

    def test_expt_with_negative_power_is_float(self):
        value = self.run_expr("(expt 2 -1)")
        self.assertIsInstance(value, float)
        self.assertEqual(value, 0.5)

    def test_abs_of_float(self):
        self.assertEqual(self.run_expr("(abs -3.5)"), 3.5)


class ComparisonTests(ArithmeticTestBase):
    """链式比较（spec §5）。"""

    def test_chained_comparisons(self):
        cases = [
            ("(< 2 3 4)", True),
            ("(< 2 4 3)", False),
            ("(<= 1 1 2)", True),
            ("(> 5 4 3)", True),
            ("(>= 3 3 2)", True),
            ("(= 3 3 3)", True),
            ("(= 3 3 4)", False),
            ("(> 5 5)", False),
            ("(= 1 1)", True),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertIs(self.run_expr(source), expected)

    def test_single_argument_comparison_is_true(self):
        self.assertIs(self.run_expr("(< 2)"), True)

    def test_comparison_supports_symbols(self):
        # 符号按名字比较（spec §5）；用变量传入，让这个用例不依赖读入期的 quote 简写。
        self.env.define("a", Symbol("apple"))
        self.env.define("b", Symbol("banana"))
        self.assertIs(self.run_expr("(< a b)"), True)
        self.assertIs(self.run_expr("(> a b)"), False)
        self.assertIs(self.run_expr("(= a a)"), True)
        self.assertIs(self.run_expr("(<= a a)"), True)
        self.assertIs(self.run_expr("(<= a b)"), True)
        self.assertIs(self.run_expr("(<= b a)"), False)
        self.assertIs(self.run_expr("(>= a a)"), True)
        self.assertIs(self.run_expr("(>= b a)"), True)
        self.assertIs(self.run_expr("(>= a b)"), False)

    def test_comparison_rejects_mixed_types(self):
        self.env.define("a", Symbol("apple"))
        with self.assertRaises(SchemeTypeError):
            self.run_expr("(< 1 a)")

    def test_comparison_rejects_non_numbers(self):
        with self.assertRaises(SchemeTypeError):
            self.run_expr("(< 1 #t)")


class NotTests(ArithmeticTestBase):
    """not：只有 #f 是假（spec §5/§9）。"""

    def test_not_flips_only_hash_f(self):
        self.assertIs(self.run_expr("(not #f)"), True)
        self.assertIs(self.run_expr("(not #t)"), False)

    def test_zero_empty_string_and_empty_list_are_truthy(self):
        self.env.define("zero", 0)
        self.env.define("text", "")
        self.env.define("empty", NIL)
        for source in ("(not zero)", "(not text)", "(not empty)"):
            with self.subTest(source=source):
                self.assertIs(self.run_expr(source), False)


class ArithmeticErrorTests(ArithmeticTestBase):
    """错误路径：类型、个数、除零都必须变成 SchemeError 的子类（spec §11）。"""

    def test_boolean_is_not_a_number(self):
        for source in ("(+ 1 #t)", "(* 2 #f)", "(abs #t)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeTypeError):
                    self.run_expr(source)

    def test_symbol_is_not_a_number(self):
        self.env.define("s", Symbol("x"))
        for source in ("(+ 1 s)", "(< s 2)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeTypeError):
                    self.run_expr(source)

    def test_modulo_and_quotient_require_integers(self):
        for source in ("(modulo 1.5 2)", "(quotient 7.5 2)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeTypeError):
                    self.run_expr(source)

    def test_division_by_zero(self):
        for source in ("(/ 1 0)", "(/ 0)", "(modulo 5 0)", "(quotient 5 0)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeError):
                    self.run_expr(source)

    def test_too_few_arguments(self):
        for source in ("(-)", "(/ )", "(abs)", "(not)", "(modulo 1)", "(expt 1)", "(<)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeArityError):
                    self.run_expr(source)

    def test_too_many_arguments(self):
        for source in ("(abs 1 2)", "(not #t #f)", "(modulo 1 2 3)", "(expt 1 2 3)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeArityError):
                    self.run_expr(source)

    def test_expt_with_irrational_result_is_reported(self):
        with self.assertRaises(SchemeError):
            self.run_expr("(expt -8 0.5)")


if __name__ == "__main__":
    unittest.main()
