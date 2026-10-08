"""特殊形式的单元测试（Phase 3，spec §4）。

覆盖六个特殊形式的求值顺序：quote 不求值、if 与 cond 只走一个分支、
and/or 短路、begin 顺序执行，以及写法不对时抛 SchemeSyntaxError。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import NIL, Pair, PrimitiveProcedure  # noqa: E402
from scheme.errors import SchemeSyntaxError  # noqa: E402
from scheme.evaluator import evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_write  # noqa: E402


class SpecialFormTestBase(unittest.TestCase):
    """公共脚手架：新环境 + 求值驱动 + 记录调用的探针过程。"""

    def setUp(self):
        self.env = make_global_env()

    def run_expr(self, text):
        """求值一段只含一个表达式的源码。"""
        return evaluate(parse(text)[0], self.env)

    def install_spies(self):
        """装上 record / boom：一旦被调用就往返回的列表里留痕。

        用来证明"没被执行的分支/表达式"确实没有求值（spec §4.2/§4.3/§4.4）。
        record 返回第一个实参，boom 返回 1，都只为了不打断被测程序。
        """
        calls = []

        def record(args):
            calls.append(args)
            return args[0]

        def boom(args):
            calls.append(args)
            return 1

        self.env.define("record", PrimitiveProcedure("record", record, 1, None))
        self.env.define("boom", PrimitiveProcedure("boom", boom, 0, 1))
        return calls


class QuoteTests(SpecialFormTestBase):
    """quote 原样返回数据（spec §4.1）。"""

    def test_quote_returns_the_symbol_itself(self):
        self.assertEqual(to_write(self.run_expr("(quote x)")), "x")
        self.assertEqual(to_write(self.run_expr("'x")), "x")

    def test_quote_of_list(self):
        self.assertEqual(to_write(self.run_expr("'(1 2 3)")), "(1 2 3)")

    def test_quoted_list_is_a_cons_chain_ending_with_nil(self):
        # 引用数据必须与 cons 的表示一致（spec §6/§11）
        data = self.run_expr("'(1 2 3)")
        self.assertIsInstance(data, Pair)
        self.assertEqual(data.car, 1)
        self.assertEqual(to_write(data.cdr), "(2 3)")
        self.assertIs(data.cdr.cdr.cdr, NIL)

    def test_empty_list_literal(self):
        self.assertIs(self.run_expr("'()"), NIL)

    def test_quoted_symbols_are_not_evaluated(self):
        # (quote (a b)) 里的 a、b 不当变量求值，否则会抛未绑定名字
        self.assertEqual(to_write(self.run_expr("'(a b)")), "(a b)")

    def test_quoted_dotted_pair(self):
        data = self.run_expr("'(1 . 2)")
        self.assertIsInstance(data, Pair)
        self.assertEqual(to_write(data), "(1 . 2)")

    def test_nested_quote_keeps_the_inner_form_as_data(self):
        self.assertEqual(to_write(self.run_expr("'(quote x)")), "(quote x)")

    def test_symbols_and_strings_stay_distinct(self):
        self.assertEqual(to_write(self.run_expr("'a")), "a")
        self.assertEqual(to_write(self.run_expr('"a"')), '"a"')


class IfTests(SpecialFormTestBase):
    """if 只走一个分支（spec §4.2）。"""

    def test_spec_examples(self):
        self.assertEqual(to_write(self.run_expr("(if (> 3 2) 'yes 'no)")), "yes")
        self.assertEqual(to_write(self.run_expr("(if #f 'bad 'good)")), "good")
        self.assertEqual(self.run_expr("(if (= 1 2) 1 2)"), 2)

    def test_only_hash_f_counts_as_false(self):
        self.assertEqual(to_write(self.run_expr("(if 0 'zero 'other)")), "zero")

    def test_missing_else_branch_returns_no_value(self):
        self.assertIsNone(self.run_expr("(if #f 1)"))
        self.assertEqual(self.run_expr("(if #t 1)"), 1)

    def test_untaken_branch_is_not_evaluated(self):
        calls = self.install_spies()
        self.assertEqual(self.run_expr("(if #t 1 (boom))"), 1)
        self.assertEqual(self.run_expr("(if #f (boom) 2)"), 2)
        self.assertEqual(calls, [])

    def test_nested_if(self):
        self.assertEqual(self.run_expr("(if (= 1 1) (if (= 2 3) 1 2) 3)"), 2)


class CondTests(SpecialFormTestBase):
    """cond 从上到下找第一个为真的子句（spec §4.3）。"""

    def test_spec_examples(self):
        cases = [
            ("(cond ((= 1 2) 'a) ((= 2 2) 'b) (else 'c))", "b"),
            ("(cond (else 'd))", "d"),
            ("(cond ((> 2 3)) (else 42))", "42"),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(to_write(self.run_expr(source)), expected)

    def test_clause_without_body_returns_the_test_value(self):
        self.assertIs(self.run_expr("(cond ((= 2 2)))"), True)
        self.assertIs(self.run_expr("(cond (#t))"), True)

    def test_clause_body_may_have_several_expressions(self):
        self.assertEqual(self.run_expr("(cond (#t 1 2 3))"), 3)

    def test_else_clause_without_body(self):
        self.assertIs(self.run_expr("(cond (else))"), True)

    def test_no_matching_clause_returns_no_value(self):
        self.assertIsNone(self.run_expr("(cond ((= 1 2) 'a))"))
        self.assertIsNone(self.run_expr("(cond)"))

    def test_untaken_clause_bodies_are_not_evaluated(self):
        calls = self.install_spies()
        source = "(cond ((= 1 1) 10) ((= 2 2) (boom)))"
        self.assertEqual(self.run_expr(source), 10)
        self.assertEqual(calls, [])  # 第二个子句连测试都没求值

    def test_clause_body_runs_in_order_like_begin(self):
        calls = self.install_spies()
        self.assertEqual(self.run_expr("(cond (#t (record 1) (record 2)))"), 2)
        self.assertEqual(calls, [[1], [2]])

    def test_conditions_are_tested_in_order_until_one_matches(self):
        calls = self.install_spies()
        source = "(cond ((= 1 2) 'a) ((record 5) 'b))"
        self.assertEqual(to_write(self.run_expr(source)), "b")
        self.assertEqual(calls, [[5]])  # 只有第二个子句的测试被求值过


class AndOrTests(SpecialFormTestBase):
    """and / or 的短路求值（spec §4.4）。"""

    def test_and_without_arguments_is_true(self):
        self.assertIs(self.run_expr("(and)"), True)

    def test_or_without_arguments_is_false(self):
        self.assertIs(self.run_expr("(or)"), False)

    def test_and_returns_the_last_value_when_all_are_truthy(self):
        self.assertEqual(self.run_expr("(and 1 2 3)"), 3)
        self.assertEqual(to_write(self.run_expr("(and 'a 'b)")), "b")

    def test_and_returns_the_first_false_value(self):
        self.assertIs(self.run_expr("(and #t #f)"), False)
        self.assertIs(self.run_expr("(and #f 2 3)"), False)

    def test_or_returns_the_first_truthy_value(self):
        self.assertIs(self.run_expr("(or #f #t)"), True)
        self.assertEqual(to_write(self.run_expr("(or #f 'a 'b)")), "a")

    def test_or_returns_false_when_all_are_false(self):
        self.assertIs(self.run_expr("(or #f #f)"), False)

    def test_short_circuit_skips_the_division_by_zero(self):
        # spec §4.4 的原例：后面根本不执行，所以不会报错
        self.assertIs(self.run_expr("(and #f (/ 1 0))"), False)
        self.assertIs(self.run_expr("(or #t (/ 1 0))"), True)

    def test_short_circuit_skips_later_expressions(self):
        calls = self.install_spies()
        self.assertIs(self.run_expr("(and #f (boom))"), False)
        self.assertIs(self.run_expr("(or #t (boom))"), True)
        self.assertEqual(calls, [])


class BeginTests(SpecialFormTestBase):
    """begin 顺序执行（spec §4.8）。"""

    def test_begin_returns_the_last_value(self):
        self.assertEqual(self.run_expr("(begin 1 2 3)"), 3)
        self.assertEqual(to_write(self.run_expr("(begin 'a 'b)")), "b")

    def test_begin_evaluates_left_to_right(self):
        calls = self.install_spies()
        self.assertEqual(self.run_expr("(begin (record 1) (record 2))"), 2)
        self.assertEqual(calls, [[1], [2]])

    def test_begin_without_expressions_is_no_value(self):
        self.assertIsNone(self.run_expr("(begin)"))


class SpecialFormShapeTests(SpecialFormTestBase):
    """写法不对时要给出 SchemeSyntaxError（spec §11：不崩溃、信息清楚）。"""

    def test_malformed_forms(self):
        cases = (
            "(quote)",
            "(quote a b)",
            "(if)",
            "(if #t)",
            "(if #t 1 2 3)",
            "(cond 5)",
            "(cond ())",
        )
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(SchemeSyntaxError):
                    self.run_expr(source)

    def test_special_forms_take_precedence_over_variables(self):
        # 特殊形式由表头的名字直接分派，不会被同名变量遮蔽（spec §4）
        self.env.define("and", 0)
        self.assertIs(self.run_expr("(and #t #t)"), True)

    def test_quote_is_not_a_special_case_of_lists(self):
        # 未加 quote 的 (1 2 3) 仍按函数调用处理（spec §4.1/§11）
        with self.assertRaises(Exception) as context:
            self.run_expr("(1 2 3)")
        self.assertNotIsInstance(context.exception, SchemeSyntaxError)


if __name__ == "__main__":
    unittest.main()
