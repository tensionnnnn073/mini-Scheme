"""谓词内置过程的单元测试（Phase 8，spec §5 谓词各行 + §11 排错指南）。

重点是 Python 类型关系带来的两个陷阱（bool 是 int 的子类、Symbol 是 str 的子类），
以及 eq?（同一性）与 equal?（结构相等、先比类型）的区别。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.errors import SchemeArityError, SchemeTypeError  # noqa: E402
from scheme.evaluator import evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_write  # noqa: E402


class PredicateTestBase(unittest.TestCase):
    """公共脚手架：新环境 + 求值驱动 + 真假断言（谓词必须返回真正的布尔）。"""

    def setUp(self):
        self.env = make_global_env()

    def run_expr(self, text):
        """求值一段只含一个表达式的源码。"""
        return evaluate(parse(text)[0], self.env)

    def run_program(self, text):
        """按 CLI 的方式求值一段程序的每个顶层表达式，返回结果列表。"""
        return [evaluate(expr, self.env) for expr in parse(text)]

    def write(self, text):
        """求值并把结果写成 write 形式（列表用文本比较）。"""
        return to_write(self.run_expr(text))

    def assertPositive(self, source):
        """断言源码求值为 #t（用 assertIs 排除 0、非空表等真值）。"""
        self.assertIs(self.run_expr(source), True, source)

    def assertNegative(self, source):
        """断言源码求值为 #f。"""
        self.assertIs(self.run_expr(source), False, source)


class TypePredicateTests(PredicateTestBase):
    """number? / boolean? / symbol? / string? / procedure?（spec §5）。"""

    def test_number(self):
        for source in ("(number? 5)", "(number? 0.5)", "(number? -3)", "(number? (/ 1 2))"):
            with self.subTest(source=source):
                self.assertPositive(source)
        # 布尔不是数字：Python 里 True == 1，必须单独排除（spec §11）
        for source in (
            "(number? 'x)",
            "(number? #t)",
            "(number? #f)",
            '(number? "5")',
            "(number? '())",
            "(number? (list 1))",
        ):
            with self.subTest(source=source):
                self.assertNegative(source)

    def test_boolean(self):
        for source in ("(boolean? #t)", "(boolean? #f)", "(boolean? (= 1 1))"):
            with self.subTest(source=source):
                self.assertPositive(source)
        for source in ("(boolean? 0)", "(boolean? 1)", "(boolean? '())", '(boolean? "true")'):
            with self.subTest(source=source):
                self.assertNegative(source)

    def test_symbol(self):
        for source in ("(symbol? 'x)", "(symbol? (quote a))"):
            with self.subTest(source=source):
                self.assertPositive(source)
        for source in ('(symbol? "x")', "(symbol? 1)", "(symbol? #t)", "(symbol? '())"):
            with self.subTest(source=source):
                self.assertNegative(source)

    def test_string(self):
        for source in ('(string? "s")', '(string? "")'):
            with self.subTest(source=source):
                self.assertPositive(source)
        # 符号是 str 的子类，不能算字符串（spec §11）
        for source in ("(string? 's)", "(string? 5)", "(string? '())", "(string? #t)"):
            with self.subTest(source=source):
                self.assertNegative(source)

    def test_procedure(self):
        for source in ("(procedure? car)", "(procedure? +)", "(procedure? (lambda (x) x))"):
            with self.subTest(source=source):
                self.assertPositive(source)
        for source in ("(procedure? 1)", "(procedure? 'car)", "(procedure? '())", '(procedure? "s")'):
            with self.subTest(source=source):
                self.assertNegative(source)


class NumericPredicateTests(PredicateTestBase):
    """zero? / even? / odd?：参数必须是数（spec §5）。"""

    def test_zero(self):
        self.assertPositive("(zero? 0)")
        self.assertPositive("(zero? 0.0)")
        self.assertPositive("(zero? (- 3 3))")
        self.assertNegative("(zero? 1)")
        self.assertNegative("(zero? -1)")

    def test_even_and_odd(self):
        self.assertPositive("(even? 8)")
        self.assertPositive("(even? 0)")
        self.assertPositive("(even? (- 4 2))")
        self.assertNegative("(even? 7)")
        self.assertPositive("(odd? 7)")
        self.assertPositive("(odd? 1)")
        self.assertNegative("(odd? 8)")

    def test_numeric_predicates_require_numbers(self):
        for source in ("(zero? '())", "(zero? #f)", '(even? "2")', "(odd? 'a)", "(even? (list 1))"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeTypeError):
                    self.run_expr(source)


class EqualityPredicateTests(PredicateTestBase):
    """eq? 比同一性，equal? 比结构（spec §5/§11）。"""

    def test_eq_on_atoms_compares_by_value(self):
        self.assertPositive("(eq? 'a 'a)")
        self.assertNegative("(eq? 'a 'b)")
        self.assertNegative('(eq? \'a "a")')
        self.assertPositive("(eq? 2 2)")
        self.assertNegative("(eq? 2 3)")
        self.assertPositive("(eq? #t #t)")
        self.assertPositive("(eq? #f #f)")
        self.assertNegative("(eq? #t #f)")
        self.assertNegative("(eq? #t 1)")  # 布尔与数字不同类型（spec §11）

    def test_eq_on_compound_data_is_identity(self):
        self.assertPositive("(eq? '() '())")  # 空表是单例
        self.assertPositive("(eq? '() (list))")
        self.assertNegative("(eq? '(1) '(1))")
        self.assertNegative("(eq? (list 1) (list 1))")
        self.assertNegative("(eq? (cons 1 2) (cons 1 2))")
        self.run_expr("(define xs '(1 2))")
        self.assertPositive("(eq? xs xs)")
        self.run_expr("(define alias xs)")
        self.assertPositive("(eq? xs alias)")
        self.assertNegative("(eq? xs '(1 2))")

    def test_equal_is_structural_and_compares_types_first(self):
        self.assertPositive("(equal? '(1 2 3) (list 1 2 3))")
        self.assertPositive("(equal? '(1 (2 3)) (list 1 (list 2 3)))")
        self.assertPositive("(equal? (cons 1 2) (cons 1 2))")
        self.assertPositive("(equal? '() '())")
        self.assertPositive("(equal? 'a 'a)")
        self.assertPositive('(equal? "ab" "ab")')
        self.assertPositive("(equal? 1 1)")
        self.assertPositive("(equal? car car)")
        self.assertNegative("(equal? car cdr)")
        self.assertNegative("(equal? #t 1)")  # 先比类型：布尔与数字
        self.assertNegative('(equal? \'a "a")')  # 先比类型：符号与字符串
        self.assertNegative('(equal? 1 "1")')
        self.assertNegative("(equal? '(1 2) '(1 3))")
        self.assertNegative("(equal? '(1 2) '(1 2 3))")
        self.assertNegative("(equal? (list 1) 1)")

    def test_equal_is_weaker_than_eq_on_fresh_lists(self):
        self.assertNegative("(eq? '(1) '(1))")
        self.assertPositive("(equal? '(1) '(1))")


class PredicateIntegrationTests(PredicateTestBase):
    """谓词与列表/高阶函数/控制流一起用（spec §12 阶梯 009/012）。"""

    FILTER = (
        "(define (filter pred xs)"
        " (cond ((null? xs) '())"
        "       ((pred (car xs)) (cons (car xs) (filter pred (cdr xs))))"
        "       (else (filter pred (cdr xs)))))"
    )

    def test_builtin_predicate_used_as_a_procedure_value(self):
        self.run_expr(self.FILTER)
        self.assertEqual(self.write("(filter even? '(1 2 3 4 5 6))"), "(2 4 6)")
        self.assertEqual(self.write("(filter (lambda (x) (> x 3)) (list 1 2 3 4))"), "(4)")

    def test_predicates_inside_cond_and_if(self):
        self.assertEqual(self.write("(cond ((even? 3) 'even) ((odd? 3) 'odd) (else 'other))"), "odd")
        self.assertEqual(self.write("(if (equal? '(1 2) (list 1 2)) 'same 'different)"), "same")
        self.assertEqual(self.write("(cond ((procedure? car) 'proc) (else 'not-proc))"), "proc")
        self.assertEqual(self.write("(if (and (symbol? 'a) (number? 1)) 'yes 'no)"), "yes")

    def test_counting_with_equal(self):
        self.assertEqual(
            self.run_program(
                "(define (count v xs) (if (null? xs) 0 (+ (if (equal? v (car xs)) 1 0)"
                " (count v (cdr xs)))))\n"
                "(count 'a '(a b a c a))"
            )[1],
            3,
        )

    def test_not_still_comes_from_arithmetic(self):
        self.assertPositive("(not #f)")
        self.assertNegative("(not 0)")  # 只有 #f 是假
        self.assertNegative("(not '())")


class PredicateArityTests(PredicateTestBase):
    """参数个数不符抛 SchemeArityError（spec §11）。"""

    def test_arity_errors(self):
        for source in ("(number?)", "(even?)", "(procedure? 1 2)", "(eq? 1)", "(eq? 1 2 3)", "(equal? 1)"):
            with self.subTest(source=source):
                with self.assertRaises(SchemeArityError):
                    self.run_expr(source)


if __name__ == "__main__":
    unittest.main()

