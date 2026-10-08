"""let 的单元测试（Phase 5，spec §4.7/§9）。

重点是**并行绑定**：所有绑定表达式都在外层环境求值完，绑定之间互不可见；
以及 let 新建的作用域不会泄漏到外层。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import PrimitiveProcedure  # noqa: E402
from scheme.errors import SchemeNameError, SchemeSyntaxError  # noqa: E402
from scheme.evaluator import evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402


class LetTestBase(unittest.TestCase):
    """公共脚手架：新环境 + 求值驱动 + 记录调用的探针。"""

    def setUp(self):
        self.env = make_global_env()

    def run_expr(self, text):
        """求值一段只含一个表达式的源码。"""
        return evaluate(parse(text)[0], self.env)

    def run_program(self, text):
        """按 CLI 的方式求值一段程序的每个顶层表达式，返回结果列表。"""
        return [evaluate(expr, self.env) for expr in parse(text)]

    def install_recorder(self):
        """装上 record，用来观察绑定表达式与体的求值顺序。"""
        calls = []

        def record(args):
            calls.append(args)
            return args[0]

        self.env.define("record", PrimitiveProcedure("record", record, 1, None))
        return calls


class LetTests(LetTestBase):
    """let 的并行绑定与新作用域（spec §4.7）。"""

    def test_spec_examples(self):
        self.assertEqual(self.run_expr("(let ((x 3) (y 4)) (+ x y))"), 7)
        self.assertEqual(self.run_expr("(let ((a 1)) (let ((b (+ a 1))) (* a b)))"), 2)

    def test_body_returns_the_last_expression(self):
        self.assertEqual(self.run_expr("(let ((x 1)) x 2 3)"), 3)

    def test_no_bindings(self):
        self.run_expr("(define outer 5)")
        self.assertEqual(self.run_expr("(let () outer)"), 5)

    def test_bindings_are_parallel_not_sequential(self):
        # 绑定串里出现的 x 是**外层**的 x，而不是同一个 let 刚绑上的 x（spec §4.7）
        self.run_expr("(define x 10)")
        self.assertEqual(self.run_expr("(let ((x 1) (y x)) y)"), 10)

    def test_binding_expressions_are_evaluated_in_written_order(self):
        calls = self.install_recorder()
        self.assertEqual(self.run_expr("(let ((a (record 1)) (b (record 2))) b)"), 2)
        self.assertEqual(calls, [[1], [2]])

    def test_binding_expressions_are_evaluated_before_the_body(self):
        calls = self.install_recorder()
        self.assertEqual(self.run_expr("(let ((a (record 1))) (record 9) a)"), 1)
        self.assertEqual(calls, [[1], [9]])  # 绑定先算，体后算

    def test_shadowing_does_not_leak_outside(self):
        self.run_expr("(define x 1)")
        self.assertEqual(self.run_expr("(let ((x 5)) (+ x 1))"), 6)
        self.assertEqual(self.env.lookup("x"), 1)

    def test_inner_define_stays_in_the_let_frame(self):
        self.assertEqual(self.run_expr("(let ((x 1)) (define y 2) (+ x y))"), 3)
        with self.assertRaises(SchemeNameError):
            self.env.lookup("y")

    def test_a_let_binding_can_be_captured_by_a_closure(self):
        values = self.run_program(
            "(define add-ten (let ((n 10)) (lambda (x) (+ x n))))\n(add-ten 5)"
        )
        self.assertEqual(values[1], 15)

    def test_let_can_hold_functions(self):
        self.assertEqual(self.run_expr("((let ((f (lambda (x) (* x 2)))) f) 21)"), 42)

    def test_nested_lets_shadow_each_other(self):
        self.assertEqual(self.run_expr("(let ((x 1)) (let ((x 2)) x))"), 2)

    def test_let_inside_recursion(self):
        values = self.run_program(
            "(define (sum-to n)"
            " (if (= n 0) 0 (let ((rest (sum-to (- n 1)))) (+ n rest))))\n"
            "(sum-to 10)"
        )
        self.assertEqual(values[1], 55)

    def test_body_can_contain_begin(self):
        self.assertEqual(self.run_expr("(let ((n 2)) (begin (define m 3) (* n m)))"), 6)

    def test_duplicate_binding_names_let_the_last_one_win(self):
        # spec §4.7 没有禁止重名，验收用例里就有这种写法：
        # 绑定表达式照旧全部在外层求值，写进新环境时按书写顺序，后一个覆盖前一个。
        self.assertEqual(self.run_expr("(let ((x 1) (x 2)) x)"), 2)
        self.run_expr("(define x 10)")
        self.assertEqual(self.run_expr("(let ((x 1) (y x)) y)"), 10)  # 并行不受重名影响
        self.assertEqual(self.run_expr("(let ((x 5) (x (+ x 1))) x)"), 11)

    def test_malformed_lets(self):
        cases = (
            "(let)",
            "(let ((x 1)))",
            "(let (x 1) x)",
            "(let ((x)) x)",
            "(let ((x 1 2)) x)",
            "(let ((1 2)) 1)",
            "(let ((x . 1)) x)",
        )
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(SchemeSyntaxError):
                    self.run_expr(source)


if __name__ == "__main__":
    unittest.main()
