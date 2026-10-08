"""列表内置过程的单元测试（Phase 6，spec §5 列表各行 + §6/§7）。

覆盖 cons / car / cdr / list / length / append / null? / pair? / list?，
以及"用语言本身定义 map/filter"这条验收路线（spec §10 明确 map/filter 不内置）。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import NIL, Pair  # noqa: E402
from scheme.errors import SchemeArityError, SchemeError, SchemeTypeError  # noqa: E402
from scheme.evaluator import evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_write  # noqa: E402


class ListTestBase(unittest.TestCase):
    """公共脚手架：新环境 + 求值驱动（列表用打印文本比较，Pair 没有结构相等）。"""

    def setUp(self):
        self.env = make_global_env()

    def run_expr(self, text):
        """求值一段只含一个表达式的源码。"""
        return evaluate(parse(text)[0], self.env)

    def run_program(self, text):
        """按 CLI 的方式求值一段程序的每个顶层表达式，返回结果列表。"""
        return [evaluate(expr, self.env) for expr in parse(text)]

    def write(self, text):
        """求值并把结果写成 write 形式。"""
        return to_write(self.run_expr(text))


class ConsCarCdrTests(ListTestBase):
    """cons / car / cdr：列表就是点对链（spec §6）。"""

    def test_spec_examples(self):
        self.assertEqual(self.write("(car '(1 2 3))"), "1")
        self.assertEqual(self.write("(cdr '(1 2 3))"), "(2 3)")
        self.assertEqual(self.write("(cons 1 '(2 3))"), "(1 2 3)")
        self.assertEqual(self.write("(cons 1 2)"), "(1 . 2)")

    def test_car_and_cdr_walk_the_chain(self):
        self.assertEqual(self.write("(car (cdr '(1 2 3)))"), "2")
        self.assertEqual(self.write("(cdr (cdr '(1 2 3)))"), "(3)")
        self.assertEqual(self.write("(car (cdr (cdr '(1 2 3))))"), "3")

    def test_car_and_cdr_of_a_dotted_pair(self):
        self.assertEqual(self.write("(car '(1 . 2))"), "1")
        self.assertEqual(self.write("(cdr '(1 . 2))"), "2")

    def test_quote_and_cons_share_the_same_representation(self):
        quoted = self.run_expr("'(1 2)")
        constructed = self.run_expr("(cons 1 (cons 2 '()))")
        self.assertEqual(to_write(quoted), to_write(constructed))
        self.assertEqual(to_write(self.run_expr("(car (list 1 2 3))")), "1")

    def test_lists_are_chains_ending_with_the_empty_list(self):
        pair = self.run_expr("(list 1 2)")
        self.assertIsInstance(pair, Pair)
        self.assertEqual(to_write(pair.car), "1")
        self.assertIs(pair.cdr.cdr, NIL)

    def test_cons_builds_a_new_pair_without_touching_its_arguments(self):
        self.run_expr("(define xs '(2 3))")
        extended = self.run_expr("(cons 1 xs)")
        self.assertEqual(to_write(extended), "(1 2 3)")
        self.assertEqual(to_write(self.env.lookup("xs")), "(2 3)")


class ListConstructionTests(ListTestBase):
    """list：把实参打包成点对链（spec §5/§6）。"""

    def test_empty_list(self):
        self.assertIs(self.run_expr("(list)"), NIL)
        self.assertEqual(self.write("(list)"), "()")

    def test_spec_example(self):
        self.assertEqual(self.write("(list 1 2 3)"), "(1 2 3)")

    def test_arguments_are_evaluated_first(self):
        self.assertEqual(self.write("(list (+ 1 1) (* 2 2))"), "(2 4)")

    def test_nested_lists(self):
        self.assertEqual(self.write("(list (list 1 2) 3)"), "((1 2) 3)")

    def test_mixed_values(self):
        self.assertEqual(self.write("(list 'a \"b\" #t 1)"), '(a "b" #t 1)')


class LengthAndAppendTests(ListTestBase):
    """length / append（spec §5）。"""

    def test_length(self):
        self.assertEqual(self.run_expr("(length '(a b c d))"), 4)
        self.assertEqual(self.run_expr("(length '())"), 0)
        self.assertEqual(self.run_expr("(length (list 1 2 3 4 5))"), 5)

    def test_length_rejects_dotted_pairs(self):
        with self.assertRaises(SchemeTypeError):
            self.run_expr("(length (cons 1 2))")
        with self.assertRaises(SchemeTypeError):
            self.run_expr("(length 5)")

    def test_append(self):
        self.assertEqual(self.write("(append '(1 2) '(3 4))"), "(1 2 3 4)")
        self.assertEqual(self.write("(append)"), "()")
        self.assertEqual(self.write("(append '(1 2))"), "(1 2)")
        self.assertEqual(self.write("(append '() '(1))"), "(1)")
        self.assertEqual(self.write("(append '(1) '() '(2))"), "(1 2)")
        self.assertEqual(self.write("(append '(1) '(2) '(3) '(4))"), "(1 2 3 4)")

    def test_append_last_argument_may_be_any_value(self):
        # 与 Scheme 一致：(append '(1 2) 3) = (1 2 . 3)
        self.assertEqual(self.write("(append '(1 2) 3)"), "(1 2 . 3)")
        self.assertEqual(self.write("(append '(1) (cons 2 3))"), "(1 2 . 3)")

    def test_append_requires_true_lists_before_the_last_argument(self):
        with self.assertRaises(SchemeTypeError):
            self.run_expr("(append (cons 1 2) '(3))")

    def test_append_does_not_modify_its_arguments(self):
        self.run_expr("(define xs '(1 2))")
        self.assertEqual(self.write("(append xs '(3))"), "(1 2 3)")
        self.assertEqual(self.run_expr("(length xs)"), 2)
        self.assertEqual(self.write("(car xs)"), "1")


class ListPredicateTests(ListTestBase):
    """null? / pair? / list?（spec §5/§6）。"""

    def test_null(self):
        self.assertIs(self.run_expr("(null? '())"), True)
        self.assertIs(self.run_expr("(null? (list))"), True)
        self.assertIs(self.run_expr("(null? (cdr '(1)))"), True)
        self.assertIs(self.run_expr("(null? '(1))"), False)
        self.assertIs(self.run_expr("(null? (cons 1 2))"), False)
        self.assertIs(self.run_expr("(null? 0)"), False)
        self.assertIs(self.run_expr("(null? \"\")"), False)
        self.assertIs(self.run_expr("(null? #f)"), False)

    def test_pair(self):
        self.assertIs(self.run_expr("(pair? '(1 2))"), True)
        self.assertIs(self.run_expr("(pair? (cons 1 2))"), True)
        self.assertIs(self.run_expr("(pair? '(1))"), True)
        self.assertIs(self.run_expr("(pair? '())"), False)
        self.assertIs(self.run_expr("(pair? 1)"), False)
        self.assertIs(self.run_expr("(pair? 'a)"), False)

    def test_list(self):
        self.assertIs(self.run_expr("(list? '(1 2))"), True)
        self.assertIs(self.run_expr("(list? '())"), True)
        self.assertIs(self.run_expr("(list? (list 1))"), True)
        self.assertIs(self.run_expr("(list? (cons 1 '()))"), True)
        # 点对不是列表：链尾不是空表（spec §6）
        self.assertIs(self.run_expr("(list? (cons 1 2))"), False)
        self.assertIs(self.run_expr("(list? (cons 1 (cons 2 3)))"), False)
        self.assertIs(self.run_expr("(list? 5)"), False)
        self.assertIs(self.run_expr("(list? \"ab\")"), False)


# spec §10：map / filter 不内置，必须在程序里用语言本身定义。
MAP_SOURCE = "(define (map f xs) (if (null? xs) '() (cons (f (car xs)) (map f (cdr xs)))))"
FILTER_SOURCE = (
    "(define (filter pred xs)"
    " (cond ((null? xs) '())"
    "       ((pred (car xs)) (cons (car xs) (filter pred (cdr xs))))"
    "       (else (filter pred (cdr xs)))))"
)


class HigherOrderListTests(ListTestBase):
    """用内置的列表操作手写高阶函数（spec §7 的验收路线）。"""

    def test_map_with_a_lambda(self):
        self.run_expr(MAP_SOURCE)
        self.assertEqual(self.write("(map (lambda (x) (* x x)) '(1 2 3 4))"), "(1 4 9 16)")

    def test_map_with_a_builtin_procedure(self):
        self.run_expr(MAP_SOURCE)
        self.assertEqual(self.write("(map abs '(-1 2 -3))"), "(1 2 3)")

    def test_map_over_the_empty_list(self):
        self.run_expr(MAP_SOURCE)
        self.assertEqual(self.write("(map (lambda (x) x) '())"), "()")

    def test_map_preserves_the_length(self):
        self.run_expr(MAP_SOURCE)
        self.assertEqual(self.run_expr("(length (map (lambda (x) x) '(1 2 3)))"), 3)

    def test_map_can_build_nested_lists(self):
        self.run_expr(MAP_SOURCE)
        self.assertEqual(self.write("(map (lambda (x) (cons x '())) '(1 2))"), "((1) (2))")

    def test_filter_with_a_lambda(self):
        self.run_expr(FILTER_SOURCE)
        self.assertEqual(self.write("(filter (lambda (x) (> x 2)) '(1 2 3 4 5))"), "(3 4 5)")

    def test_filter_can_drop_everything(self):
        self.run_expr(FILTER_SOURCE)
        self.assertEqual(self.write("(filter (lambda (x) (> x 9)) '(1 2 3))"), "()")

    def test_map_and_filter_compose(self):
        self.run_program(MAP_SOURCE + FILTER_SOURCE)
        self.assertEqual(
            self.write("(map (lambda (x) (* 10 x)) (filter (lambda (x) (> x 2)) '(1 2 3 4)))"),
            "(30 40)",
        )

    def test_reverse_with_an_accumulator(self):
        self.run_expr("(define (rev xs acc) (if (null? xs) acc (rev (cdr xs) (cons (car xs) acc))))")
        self.assertEqual(self.write("(rev '(1 2 3) '())"), "(3 2 1)")
        self.assertEqual(self.write("(rev '() '())"), "()")

    def test_append_can_be_defined_in_the_language(self):
        self.run_expr(
            "(define (my-append a b) (if (null? a) b (cons (car a) (my-append (cdr a) b))))"
        )
        self.assertEqual(self.write("(my-append '(1 2) '(3 4))"), "(1 2 3 4)")
        self.assertEqual(self.write("(my-append '() '(3))"), "(3)")

    def test_map_and_filter_are_not_built_in(self):
        """spec §10：这两个名字必须由用户程序自己定义。"""
        for name in ("map", "filter"):
            with self.assertRaises(SchemeError):
                self.run_expr(name)


class ListErrorTests(ListTestBase):
    """参数个数 / 类型不符都走 SchemeError 体系（spec §11）。"""

    def test_arity_errors(self):
        sources = (
            "(cons 1)",
            "(cons)",
            "(cons 1 2 3)",
            "(car)",
            "(car 1 2)",
            "(cdr)",
            "(length)",
            "(length '() '())",
            "(null?)",
            "(pair? 1 2)",
            "(list?)",
        )
        for source in sources:
            with self.assertRaises(SchemeArityError):
                self.run_expr(source)

    def test_car_and_cdr_reject_non_pairs(self):
        sources = ("(car '())", "(cdr '())", "(car 5)", "(cdr \"s\")", "(car #t)", "(car 'a)")
        for source in sources:
            with self.assertRaises(SchemeTypeError):
                self.run_expr(source)

    def test_error_types_derive_from_scheme_error(self):
        self.assertTrue(issubclass(SchemeArityError, SchemeError))
        self.assertTrue(issubclass(SchemeTypeError, SchemeError))


if __name__ == "__main__":
    unittest.main()

