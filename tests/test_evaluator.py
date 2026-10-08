"""求值器核心的单元测试（Phase 2，README §4 / spec §1、§9）。

覆盖：自求值的基本值、变量引用、应用序求值、嵌套调用、操作符来自变量、
参数个数校验、非过程调用、空应用、点对写法、未绑定名字、真假判定、过程打印。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import NIL, PrimitiveProcedure, Symbol, is_truthy  # noqa: E402
from scheme.errors import (  # noqa: E402
    SchemeArityError,
    SchemeNameError,
    SchemeSyntaxError,
    SchemeTypeError,
)
from scheme.evaluator import apply, evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_write  # noqa: E402


class EvaluatorTestBase(unittest.TestCase):
    """公共脚手架：每个用例一个全新的全局环境 + 最小求值驱动。"""

    def setUp(self):
        self.env = make_global_env()

    def run_expr(self, text):
        """求值一段只含一个表达式的源码。"""
        return evaluate(parse(text)[0], self.env)


class SelfEvaluatingTests(EvaluatorTestBase):
    """数字 / 浮点 / 布尔 / 字符串自己就是值，不求值（spec §9）。"""

    def test_basic_values_return_themselves(self):
        cases = [(7, 7), (3.5, 3.5), (True, True), (False, False), ("text", "text")]
        for expr, expected in cases:
            with self.subTest(expr=expr):
                self.assertEqual(evaluate(expr, self.env), expected)

    def test_booleans_survive_as_booleans(self):
        self.assertIs(evaluate(parse("#t")[0], self.env), True)
        self.assertIs(evaluate(parse("#f")[0], self.env), False)


class SymbolLookupTests(EvaluatorTestBase):
    """符号要去环境里查（spec §9）。"""

    def test_bound_symbol(self):
        self.env.define("x", 42)
        self.assertEqual(self.run_expr("x"), 42)

    def test_unbound_symbol_raises(self):
        with self.assertRaises(SchemeNameError):
            self.run_expr("nope")

    def test_unbound_symbol_in_operator_position_raises(self):
        with self.assertRaises(SchemeNameError):
            self.run_expr("(nope 1)")


class ApplicationTests(EvaluatorTestBase):
    """函数调用：应用序求值 + apply（spec §1/§9）。"""

    def test_simple_call(self):
        self.assertEqual(self.run_expr("(+ 1 2)"), 3)

    def test_nested_call_follows_spec_example(self):
        # spec §1 的逐步求值例子：(* (+ 1 2) 3) → 9
        self.assertEqual(self.run_expr("(* (+ 1 2) 3)"), 9)

    def test_deeply_nested_call(self):
        self.assertEqual(self.run_expr("(+ (* 2 3) (- 10 4 1))"), 11)

    def test_arguments_are_evaluated_before_the_call(self):
        # 应用序：实参先全部算成值，过程收到的是值而不是表达式（spec §9）
        seen = []
        self.env.define(
            "record",
            PrimitiveProcedure("record", lambda args: bool(seen.append(args)), 0, None),
        )
        self.run_expr("(record (+ 1 2) (* 2 3))")
        self.assertEqual(seen, [[3, 6]])

    def test_operator_may_come_from_a_variable(self):
        self.env.define("add", self.env.lookup("+"))
        self.assertEqual(self.run_expr("(add 1 2)"), 3)

    def test_custom_primitive(self):
        self.env.define(
            "double", PrimitiveProcedure("double", lambda args: args[0] * 2, 1, 1)
        )
        self.assertEqual(self.run_expr("(double 21)"), 42)

    def test_custom_primitive_arity_is_checked(self):
        self.env.define(
            "double", PrimitiveProcedure("double", lambda args: args[0] * 2, 1, 1)
        )
        with self.assertRaises(SchemeArityError):
            self.run_expr("(double 1 2)")

    def test_apply_with_explicit_arguments(self):
        self.assertEqual(apply(self.env.lookup("+"), [1, 2, 3]), 6)

    def test_calling_a_non_procedure_raises(self):
        # spec §11 的第一种现象：把 1 当函数调用
        with self.assertRaises(SchemeTypeError):
            self.run_expr("(1 2)")

    def test_calling_a_value_result_raises(self):
        self.env.define("x", "text")
        with self.assertRaises(SchemeTypeError):
            self.run_expr("(x)")

    def test_empty_application_is_a_syntax_error(self):
        with self.assertRaises(SchemeSyntaxError):
            self.run_expr("()")

    def test_dotted_form_is_not_evaluatable(self):
        with self.assertRaises(SchemeSyntaxError):
            self.run_expr("(1 . 2)")


class ProcedurePrintingTests(EvaluatorTestBase):
    """过程打印成 #<procedure>（spec §8）。"""

    def test_primitive_prints_as_procedure(self):
        self.assertEqual(to_write(self.env.lookup("+")), "#<procedure>")
        self.assertEqual(to_write(self.env.lookup("not")), "#<procedure>")


class TruthinessTests(unittest.TestCase):
    """只有 #f 是假（spec §4.4/§9）。"""

    def test_only_false_is_falsy(self):
        self.assertFalse(is_truthy(False))

    def test_everything_else_is_truthy(self):
        for value in (True, 0, 0.0, "", Symbol("x"), NIL, None):
            with self.subTest(value=value):
                self.assertTrue(is_truthy(value))


if __name__ == "__main__":
    unittest.main()
