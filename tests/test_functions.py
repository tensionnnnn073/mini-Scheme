"""define / lambda / 闭包 的单元测试（Phase 4，spec §4.5/§4.6/§7/§9）。

覆盖：define 的两种写法与返回值、lambda 只在调用时求值函数体、
闭包记住定义时的环境、词法遮蔽、参数个数校验、递归与深递归。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import Closure, Symbol  # noqa: E402
from scheme.errors import SchemeArityError, SchemeError, SchemeSyntaxError  # noqa: E402
from scheme.evaluator import apply, evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_write  # noqa: E402

# main.py 会把递归上限提高（Scheme 的一次调用会展开成数倍 Python 栈帧，spec §10 不要
# 求尾调用优化）；测试直接调用 evaluate，这里做同样的兜底，让深递归用例与命令行一致。
sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))


class FunctionTestBase(unittest.TestCase):
    """公共脚手架：新环境 + 求值驱动。"""

    def setUp(self):
        self.env = make_global_env()

    def run_expr(self, text):
        """求值一段只含一个表达式的源码。"""
        return evaluate(parse(text)[0], self.env)

    def run_program(self, text):
        """按 CLI 的方式（spec §2）求值一段程序的每个顶层表达式，返回结果列表。"""
        return [evaluate(expr, self.env) for expr in parse(text)]


class DefineTests(FunctionTestBase):
    """define 绑定并返回被定义的符号名（spec §4.5）。"""

    def test_define_returns_the_symbol_name(self):
        self.assertEqual(to_write(self.run_expr("(define pi 3)")), "pi")

    def test_spec_example(self):
        values = self.run_program("(define pi 3)\n(+ pi 1)")
        self.assertEqual(to_write(values[0]), "pi")
        self.assertEqual(values[1], 4)

    def test_function_shorthand(self):
        values = self.run_program("(define (square x) (* x x))\n(square 7)")
        self.assertEqual(to_write(values[0]), "square")
        self.assertEqual(values[1], 49)

    def test_function_shorthand_binds_a_closure(self):
        self.assertIsInstance(self.run_expr("(define (square x) (* x x))"), Symbol)
        self.assertIsInstance(self.env.lookup("square"), Closure)

    def test_right_hand_side_is_evaluated_before_binding(self):
        self.run_expr("(define x (if #t 1 2))")
        self.assertEqual(self.env.lookup("x"), 1)

    def test_define_inside_begin(self):
        # spec §4.8 的例子：define 在 begin 里照样生效，begin 返回最后一个值
        self.assertEqual(self.run_expr("(begin (define z 1) (+ z 41))"), 42)
        self.assertEqual(self.env.lookup("z"), 1)

    def test_redefinition_replaces_the_binding(self):
        self.run_program("(define x 1)\n(define x 2)")
        self.assertEqual(self.env.lookup("x"), 2)

    def test_variable_closure_reports_the_defined_name(self):
        # (define f (lambda ...)) 也是命名函数，参数个数报错要报出 f
        self.run_expr("(define square (lambda (x) (* x x)))")
        with self.assertRaises(SchemeArityError) as context:
            self.run_expr("(square 1 2)")
        self.assertIn("square", str(context.exception))

    def test_malformed_defines(self):
        cases = (
            "(define)",
            "(define x)",
            "(define x 1 2)",
            "(define 1 2)",
            "(define () 1)",
            "(define (5 x) 1)",
        )
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(SchemeSyntaxError):
                    self.run_expr(source)


class LambdaTests(FunctionTestBase):
    """lambda 制造闭包，函数体到调用时才求值（spec §4.6）。"""

    def test_spec_example(self):
        self.assertEqual(self.run_expr("((lambda (x) (* x 2)) 5)"), 10)

    def test_lambda_produces_a_closure(self):
        self.assertIsInstance(self.run_expr("(lambda (x) (* x x))"), Closure)
        self.assertIsInstance(self.run_expr("(lambda () 1)"), Closure)

    def test_body_is_not_evaluated_at_creation_time(self):
        closure = self.run_expr("(lambda (x) (/ 1 0))")  # 造出来这一步不该报错
        self.assertIsInstance(closure, Closure)
        with self.assertRaises(SchemeError):
            apply(closure, [1])  # 调用时才求值函数体

    def test_zero_parameters(self):
        self.assertEqual(self.run_expr("((lambda () 42))"), 42)

    def test_body_returns_the_last_expression(self):
        self.assertEqual(self.run_expr("((lambda (x) x 7) 1)"), 7)

    def test_parameters_shadow_outer_bindings_without_leaking(self):
        self.run_expr("(define x 1)")
        self.assertEqual(self.run_expr("((lambda (x) (* x 10)) 5)"), 50)
        self.assertEqual(self.env.lookup("x"), 1)

    def test_define_with_lambda_is_equivalent_to_the_shorthand(self):
        values = self.run_program("(define square (lambda (x) (* x x)))\n(square 7)")
        self.assertEqual(to_write(values[0]), "square")
        self.assertEqual(values[1], 49)

    def test_argument_count_is_checked(self):
        self.run_expr("(define (f x) x)")
        self.assertEqual(self.run_expr("(f 1)"), 1)
        for source in ("(f)", "(f 1 2)", "((lambda (x y) x) 1)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeArityError):
                    self.run_expr(source)

    def test_malformed_lambdas(self):
        cases = (
            "(lambda)",
            "(lambda (x))",
            "(lambda x x)",
            "(lambda (x x) x)",
            "(lambda (1) 1)",
            "(lambda (x . rest) x)",
        )
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(SchemeSyntaxError):
                    self.run_expr(source)


class ClosureTests(FunctionTestBase):
    """闭包记住定义时的环境（spec §4.6/§9）。"""

    def test_returned_closure_remembers_its_definition_environment(self):
        values = self.run_program(
            "(define (make-adder n) (lambda (x) (+ x n)))\n"
            "(define add5 (make-adder 5))\n"
            "(add5 10)"
        )
        self.assertEqual(to_write(values[0]), "make-adder")
        self.assertEqual(to_write(values[1]), "add5")
        self.assertEqual(values[2], 15)

    def test_each_call_captures_its_own_value(self):
        self.run_expr("(define (make-adder n) (lambda (x) (+ x n)))")
        self.assertEqual(self.run_expr("((make-adder 100) 7)"), 107)
        self.assertEqual(self.run_expr("((make-adder -1) 7)"), 6)

    def test_closure_sees_later_global_redefinition(self):
        # 全局绑定只有一个环境对象，重定义后旧函数查到的是新值（spec §9）
        self.run_program("(define n 10)\n(define (add-n x) (+ x n))\n(define n 20)")
        self.assertEqual(self.run_expr("(add-n 1)"), 21)

    def test_closures_can_be_passed_as_arguments(self):
        self.run_expr("(define (twice f x) (f (f x)))")
        self.assertEqual(self.run_expr("(twice (lambda (n) (+ n 1)) 5)"), 7)

    def test_nested_closures_capture_every_layer(self):
        values = self.run_program(
            "(define (add-then-mul a) (lambda (b) (lambda (c) (* (+ a b) c))))\n"
            "(((add-then-mul 1) 2) 3)"
        )
        self.assertEqual(values[1], 9)

    def test_all_arguments_are_evaluated_before_the_call(self):
        self.run_expr("(define (pick a b) a)")
        self.assertEqual(to_write(self.run_expr("(pick 'first 'second)")), "first")
        with self.assertRaises(SchemeError):
            self.run_expr("(pick 'first (/ 1 0))")  # 应用序：实参先全部求值


class RecursionTests(FunctionTestBase):
    """递归：define 的函数体内可见自己的名字（spec §7）。"""

    def setUp(self):
        super().setUp()
        self.run_expr("(define (fact n) (if (= n 0) 1 (* n (fact (- n 1)))))")

    def test_spec_example(self):
        self.assertEqual(self.run_expr("(fact 3)"), 6)

    def test_larger_argument(self):
        self.assertEqual(self.run_expr("(fact 10)"), 3628800)

    def test_integers_are_exact(self):
        self.assertEqual(self.run_expr("(fact 20)"), 2432902008176640000)

    def test_mutual_recursion(self):
        self.run_program(
            "(define (my-even? n) (if (= n 0) #t (my-odd? (- n 1))))\n"
            "(define (my-odd? n) (if (= n 0) #f (my-even? (- n 1))))"
        )
        self.assertIs(self.run_expr("(my-even? 10)"), True)
        self.assertIs(self.run_expr("(my-even? 7)"), False)
        self.assertIs(self.run_expr("(my-odd? 7)"), True)

    def test_recursion_that_accumulates_a_result(self):
        self.run_expr("(define (sum-to n) (if (= n 0) 0 (+ n (sum-to (- n 1)))))")
        self.assertEqual(self.run_expr("(sum-to 100)"), 5050)

    def test_deep_recursion_is_not_a_python_stack_error(self):
        # main.py 把递归上限提到 20000，测试里同样兜底（spec §10 不要求尾调用优化）
        self.run_expr("(define (count-down n) (if (= n 0) 'done (count-down (- n 1))))")
        self.assertEqual(to_write(self.run_expr("(count-down 500)")), "done")


class ProcedurePrintingTests(FunctionTestBase):
    """过程打印成 #<procedure>（spec §8；验收测试不依赖确切格式）。"""

    def test_primitive_procedure(self):
        self.assertEqual(to_write(self.run_expr("+")), "#<procedure>")

    def test_anonymous_closure(self):
        self.assertEqual(to_write(self.run_expr("(lambda (x) (* x 2))")), "#<procedure>")

    def test_named_closure(self):
        self.run_expr("(define (square x) (* x x))")
        self.assertEqual(to_write(self.run_expr("square")), "#<procedure>")


if __name__ == "__main__":
    unittest.main()
