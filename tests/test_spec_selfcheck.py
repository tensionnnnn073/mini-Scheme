"""spec.md 逐条自检（全四段）：§3 词法 + §4 特殊形式 + §5/§6/§8 内置与打印 + §9 求值规则 + §2 CLI 约定。

把 spec 里写明的例子当验收用例：每条都用**全新的全局环境**跑真实入口
（`main.run_source`，与评分器一致：初始环境为空、每个结果独占一行、
结果为 None 不打印，spec §2），并把期望输出原文抄在断言里。

本文件只**读** spec.md，不改动它。各段对应一个 TestCase 类：
    TestSpecSyntaxAndSpecialForms   §3 词法 + §4 特殊形式（quote/if/cond/and/or/define/lambda/let/begin）
    TestSpecBuiltinsAndLists        §5 内置过程表格 + §6 点对链 + §8 打印（另含 §7 的阶乘例子）
    TestSpecEvalRulesAndErrors      §9 求值规则 + 错误类别（§11 的报错文字格式留给 CLI 段）
    TestSpecCLIConventions          §2 CLI 约定（错误路径、成功路径、stdin、多文件共享环境）

运行（仓库根目录）：python -m unittest tests.test_spec_selfcheck -v
"""
import contextlib
import io as io_stream
import os
import sys
import tempfile
import unittest
from unittest import mock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import main  # noqa: E402  (入口：与评分器走同一条代码路径)
from scheme.errors import (  # noqa: E402
    SchemeArityError,
    SchemeError,
    SchemeNameError,
    SchemeSyntaxError,
    SchemeTypeError,
)
from scheme.evaluator import evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_write  # noqa: E402


class SpecTestBase(unittest.TestCase):
    """公共脚手架：整段源码 → 入口 → 抓取它写到 stdout 的文本。"""

    def run_program(self, source):
        """在全新的全局环境里求值整段源码，返回它写到 stdout 的文本（spec §2）。"""
        stream = io_stream.StringIO()
        with contextlib.redirect_stdout(stream):
            main.run_source(source, make_global_env())
        return stream.getvalue()

    def assertProgram(self, source, expected):
        """断言整段源码的 stdout 与 spec 原文逐字符相同（含行数与末尾换行）。"""
        self.assertEqual(self.run_program(source), expected, msg=f"源码：{source!r}")

    def run_expr(self, text):
        """求值一段只含一个表达式的源码，返回它的值（用于检查"无值"与返回值）。"""
        return evaluate(parse(text)[0], make_global_env())

    def assertNoValue(self, source):
        """默认输出：结果为 None 的表达式不打印（spec §2）。"""
        self.assertProgram(source, "")


class TestSpecSyntaxAndSpecialForms(SpecTestBase):
    """§3 词法 + §4 特殊形式：每条断言对应 spec 里的一个例子。"""

    # ------------------------------------------------------------------ §3 词法

    def test_lexer_ignores_comments(self):
        self.assertProgram("; 整行注释，不算程序\n42\n", "42\n")
        self.assertProgram("(+ 5 ; 行内注释\n 3)\n", "8\n")
        self.assertNoValue("; 只有注释和空白\n\n")

    def test_lexer_literals_and_case_sensitivity(self):
        self.assertProgram("-7\n", "-7\n")  # 负整数字面量
        # 大小写敏感：foo 与 FOO 是两个不同的符号（spec §3）
        self.assertProgram("(quote foo)\n(quote FOO)\n", "foo\nFOO\n")
        self.assertProgram("(procedure? +)\n", "#t\n")  # `+` 也是普通符号

    def test_lexer_string_escapes(self):
        # write 形式把制表符/引号/反斜杠重新转义，所以期望文本与源码写法一致
        self.assertProgram('"a\\tb"\n', '"a\\tb"\n')
        self.assertProgram('"q\\"w\\\\e"\n', '"q\\"w\\\\e"\n')

    # --------------------------------------------------------------- §4.1 quote

    def test_quote_returns_data_untouched(self):
        self.assertProgram("'x\n", "x\n")
        self.assertProgram("'(1 2 3)\n", "(1 2 3)\n")
        self.assertProgram("'()\n", "()\n")

    def test_quote_does_not_evaluate_its_content(self):
        self.assertProgram("(quote (+ 1 2))\n", "(+ 1 2)\n")
        self.assertProgram("'(a (b) \"s\")\n", "(a (b) \"s\")\n")

    def test_quote_of_dotted_data_prints_as_a_pair(self):
        self.assertProgram("'(1 . 2)\n", "(1 . 2)\n")
        self.assertProgram("'(1 2 . 3)\n", "(1 2 . 3)\n")

    # ------------------------------------------------------------------ §4.2 if

    def test_if_evaluates_only_one_branch(self):
        self.assertProgram("(if (> 3 2) 'yes 'no)\n", "yes\n")
        self.assertProgram("(if #f 'bad 'good)\n", "good\n")
        self.assertProgram("(if (null? '()) 1 2)\n", "1\n")
        # 没走到的分支根本不会执行：除以零也不会报错
        self.assertProgram("(if #t 1 (/ 1 0))\n", "1\n")
        self.assertProgram("(if #f (/ 1 0) 2)\n", "2\n")

    def test_if_without_alternative_has_no_value(self):
        self.assertProgram("(if #f 1)\n", "")  # 无值 → 顶层不打印（spec §2）
        self.assertProgram("(if (< 1 2) 'only)\n", "only\n")
        self.assertIsNone(self.run_expr("(if #f 1)"))

    # ---------------------------------------------------------------- §4.3 cond

    def test_cond_picks_the_first_true_clause(self):
        self.assertProgram("(cond ((= 1 2) 'a) ((= 2 2) 'b) (else 'c))\n", "b\n")
        self.assertProgram("(cond (else 'd))\n", "d\n")
        self.assertProgram("(cond ((> 2 3)) (else 42))\n", "42\n")

    def test_cond_without_body_returns_the_test_value(self):
        self.assertProgram("(cond ((> 3 2)))\n", "#t\n")

    def test_cond_without_match_has_no_value(self):
        self.assertProgram("(cond ((> 2 3) 'a))\n", "")

    def test_cond_clause_body_uses_begin_semantics(self):
        self.assertProgram("(cond ((= 1 2) 'a) (else (display 9) 'x))\n", "9x\n")
        # 只走到第一个为真的子句，后面的子句完全不求值
        self.assertProgram("(cond (#t (display 1) 'first) (#t (display 2) 'second))\n", "1first\n")

    # ------------------------------------------------------------- §4.4 and/or

    def test_and_or_short_circuit(self):
        self.assertProgram("(and #f (/ 1 0))\n", "#f\n")  # (/ 1 0) 根本没执行
        self.assertProgram("(or #t (/ 1 0))\n", "#t\n")
        self.assertProgram("(and #f (display 'no))\n", "#f\n")  # 后面不求值 → 没有输出
        self.assertProgram("(or #t (display 'no))\n", "#t\n")

    def test_and_or_identities_and_return_values(self):
        self.assertProgram("(and)\n", "#t\n")
        self.assertProgram("(or)\n", "#f\n")
        self.assertProgram("(and 1 2 3)\n", "3\n")  # 全真 → 最后一个的值
        self.assertProgram("(and 'a #f 'c)\n", "#f\n")  # 遇假 → 立即返回它
        self.assertProgram("(or #f #f 'x)\n", "x\n")  # 遇真 → 立即返回它
        self.assertProgram("(or #f 2 3)\n", "2\n")

    # -------------------------------------------------------------- §4.5 define

    def test_define_prints_the_name_and_binds_it(self):
        self.assertProgram("(define pi 3)\n(+ pi 1)\n", "pi\n4\n")
        # 返回值就是被定义的符号名（spec §4.5：顶层会把它打印出来）
        self.assertEqual(to_write(self.run_expr("(define w 9)")), "w")

    def test_define_function_shorthand_equals_lambda(self):
        self.assertProgram("(define (square x) (* x x))\n(square 7)\n", "square\n49\n")
        self.assertProgram("(define sq (lambda (x) (* x x)))\n(sq 7)\n", "sq\n49\n")

    def test_define_can_rebind_a_name(self):
        self.assertProgram("(define v 1)\n(define v 2)\nv\n", "v\nv\n2\n")

    # -------------------------------------------------------------- §4.6 lambda

    def test_lambda_defers_the_body(self):
        self.assertProgram("((lambda (x) (* x 2)) 5)\n", "10\n")
        # 定义时就求值函数体会立刻除以零；不报错即说明函数体是延迟求值的
        self.assertProgram("(define g (lambda (x) (/ 1 0)))\n", "g\n")

    def test_lambda_body_uses_begin_semantics(self):
        self.assertProgram("((lambda (x) (display x) (* x x)) 4)\n", "416\n")

    def test_closure_remembers_the_defining_environment(self):
        self.assertProgram(
            "(define (make-adder n) (lambda (x) (+ x n)))\n"
            "(define add5 (make-adder 5))\n"
            "(add5 10)\n",
            "make-adder\nadd5\n15\n",
        )

    # ----------------------------------------------------------------- §4.7 let

    def test_let_binds_in_parallel(self):
        self.assertProgram("(let ((x 3) (y 4)) (+ x y))\n", "7\n")
        # 绑定之间互不可见：b 看到的 a 是**外层**的 1，而不是同一 let 里的 2
        self.assertProgram("(define a 1)\n(let ((a 2) (b a)) b)\n", "a\n1\n")

    def test_let_shadows_outer_names_without_leaking(self):
        self.assertProgram("(let ((a 1)) (let ((b (+ a 1))) (* a b)))\n", "2\n")
        self.assertProgram("(define y 1)\n(let ((y 2)) y)\ny\n", "y\n2\n1\n")

    def test_let_duplicate_names_keep_the_last_binding(self):
        # spec 没有禁止同名绑定（验收用例 010 里就写了），后写的覆盖先写的
        self.assertProgram("(let ((x 1) (x 2)) x)\n", "2\n")

    def test_let_body_uses_begin_semantics(self):
        self.assertProgram("(let ((x 2)) (display x) (* x x))\n", "24\n")

    # -------------------------------------------------------------- §4.8 begin

    def test_begin_evaluates_in_order_and_returns_the_last(self):
        self.assertProgram("(begin (define z 1) (+ z 41))\n", "42\n")
        self.assertProgram("(begin 1 2 3)\n", "3\n")
        self.assertNoValue("(begin)\n")
        # begin 里的 define 写进当前环境，后面照样能看见
        self.assertProgram("(begin (define b 7))\nb\n", "b\n7\n")


class TestSpecBuiltinsAndLists(SpecTestBase):
    """§5 内置过程表格逐行 + §6 点对链 + §8 打印表格（另含 §7 的阶乘例子）。"""

    # ---------------------------------------------------------------- §5 算术

    def test_arithmetic_plus(self):
        self.assertProgram("(+ 1 2 3)\n", "6\n")
        self.assertProgram("(+ 7)\n", "7\n")
        self.assertProgram("(+)\n", "0\n")  # 可变参数的恒等值

    def test_arithmetic_minus(self):
        self.assertProgram("(- 10 4 1)\n", "5\n")  # 可变参数
        self.assertProgram("(- 5)\n", "-5\n")  # 单参数取反

    def test_arithmetic_times(self):
        self.assertProgram("(* 2 3 4)\n", "24\n")
        self.assertProgram("(* 9)\n", "9\n")
        self.assertProgram("(*)\n", "1\n")

    def test_division_uses_integer_quotient(self):
        # spec §5/§11：整数相除得整数商，**不是** 3.5
        self.assertProgram("(/ 7 2)\n", "3\n")
        self.assertProgram("(/ -7 2)\n", "-3\n")  # 负数商向零截断
        self.assertProgram("(/ 2)\n", "0.5\n")  # 单参数求倒数（浮点）

    def test_modulo_quotient_expt_abs(self):
        self.assertProgram("(modulo 17 5)\n", "2\n")
        self.assertProgram("(quotient 17 5)\n", "3\n")
        self.assertProgram("(quotient -7 2)\n", "-3\n")  # 负数商向零截断
        self.assertProgram("(expt 2 10)\n", "1024\n")
        self.assertProgram("(abs (- 5 9))\n", "4\n")

    def test_arithmetic_supports_floats(self):
        # §8 把浮点列为一种可打印的值，所以浮点要能参与运算
        self.assertProgram("0.5\n", "0.5\n")
        self.assertProgram("(+ 1 2.5)\n", "3.5\n")

    # ---------------------------------------------------------------- §5 比较

    def test_comparison_is_chained(self):
        self.assertProgram("(< 2 3 4)\n", "#t\n")  # 相邻两两都成立才为真
        self.assertProgram("(< 2 3 2)\n", "#f\n")
        self.assertProgram("(= 2 2 2)\n", "#t\n")
        self.assertProgram("(= 2 2 3)\n", "#f\n")
        self.assertProgram("(> 3 2 1)\n", "#t\n")
        self.assertProgram("(> 3 2 2)\n", "#f\n")
        self.assertProgram("(<= 1 1 2)\n", "#t\n")
        self.assertProgram("(>= 2 2 1)\n", "#t\n")
        self.assertProgram("(< 'a 'b 'c)\n", "#t\n")  # 支持符号
        self.assertProgram("(< 'a 'c 'b)\n", "#f\n")

    # ---------------------------------------------------------------- §5 布尔

    def test_not_only_false_is_false(self):
        self.assertProgram("(not #f)\n", "#t\n")
        self.assertProgram("(not #t)\n", "#f\n")
        # 只有 #f 是假：0、'()、"" 都为真，所以 not 返回 #f
        self.assertProgram("(not 0)\n", "#f\n")
        self.assertProgram("(not '())\n", "#f\n")
        self.assertProgram("(not \"\")\n", "#f\n")
        self.assertProgram("(not 'x)\n", "#f\n")

    # ---------------------------------------------------------------- §5 列表

    def test_list_table_rows(self):
        self.assertProgram("(cons 1 2)\n", "(1 . 2)\n")
        self.assertProgram("(car '(1 2 3))\n", "1\n")
        self.assertProgram("(cdr '(1 2 3))\n", "(2 3)\n")
        self.assertProgram("(list 1 2 3)\n", "(1 2 3)\n")
        self.assertProgram("(list)\n", "()\n")
        self.assertProgram("(length '(a b c d))\n", "4\n")
        self.assertProgram("(length '())\n", "0\n")
        self.assertProgram("(append '(1 2) '(3 4))\n", "(1 2 3 4)\n")

    def test_list_predicate_rows(self):
        self.assertProgram("(null? '())\n", "#t\n")
        self.assertProgram("(null? '(1))\n", "#f\n")
        self.assertProgram("(pair? '(1 2))\n", "#t\n")
        self.assertProgram("(pair? '())\n", "#f\n")
        self.assertProgram("(list? '(1 2))\n", "#t\n")
        self.assertProgram("(list? (cons 1 2))\n", "#f\n")  # 点对不是真列表

    # ---------------------------------------------------------------- §5 谓词

    def test_type_predicate_rows(self):
        self.assertProgram("(number? 5)\n", "#t\n")
        self.assertProgram("(number? 'x)\n", "#f\n")
        self.assertProgram("(boolean? #t)\n", "#t\n")
        self.assertProgram("(boolean? 0)\n", "#f\n")  # 0 不是布尔
        self.assertProgram("(symbol? 'x)\n", "#t\n")
        self.assertProgram("(symbol? \"x\")\n", "#f\n")
        self.assertProgram("(string? \"s\")\n", "#t\n")
        self.assertProgram("(string? 's)\n", "#f\n")
        self.assertProgram("(procedure? car)\n", "#t\n")
        self.assertProgram("(procedure? (lambda (x) x))\n", "#t\n")
        self.assertProgram("(procedure? 1)\n", "#f\n")

    def test_type_predicates_keep_types_apart(self):
        # 各类型互斥（实现上 bool/int、Symbol/str 都不混同）
        self.assertProgram("(number? #t)\n", "#f\n")
        self.assertProgram("(string? 'x)\n", "#f\n")
        self.assertProgram("(symbol? \"x\")\n", "#f\n")

    def test_numeric_predicate_rows(self):
        self.assertProgram("(zero? 0)\n", "#t\n")
        self.assertProgram("(zero? 1)\n", "#f\n")
        self.assertProgram("(even? 8)\n", "#t\n")
        self.assertProgram("(even? 7)\n", "#f\n")
        self.assertProgram("(odd? 7)\n", "#t\n")
        self.assertProgram("(odd? 8)\n", "#f\n")

    def test_eq_compares_atoms_by_value(self):
        self.assertProgram("(eq? 'a 'a)\n", "#t\n")
        self.assertProgram("(eq? 'a 'b)\n", "#f\n")
        self.assertProgram("(eq? 2 2)\n", "#t\n")  # 数字按值
        self.assertProgram("(eq? #t #t)\n", "#t\n")
        self.assertProgram("(eq? #t #f)\n", "#f\n")
        self.assertProgram("(eq? #t 1)\n", "#f\n")  # 类型不同，不因为 1 是真值就相等

    def test_eq_on_compound_data_uses_identity(self):
        self.assertProgram("(eq? '() '())\n", "#t\n")
        self.assertProgram("(eq? '(1) '(1))\n", "#f\n")  # 两个结构相同的不同对象
        self.assertProgram("(define xs '(1 2))\n(eq? xs xs)\n", "xs\n#t\n")  # 同一对象

    def test_equal_compares_structure(self):
        self.assertProgram("(equal? '(1 2 3) (list 1 2 3))\n", "#t\n")
        self.assertProgram("(equal? (list 1 (list 2 3)) '(1 (2 3)))\n", "#t\n")  # 逐层比较
        self.assertProgram("(equal? '(1 2) '(1 2 3))\n", "#f\n")
        self.assertProgram("(equal? #t 1)\n", "#f\n")
        self.assertProgram("(equal? 'a \"a\")\n", "#f\n")  # 先比类型

    # ---------------------------------------------------------------- §5 输出

    def test_display_prints_without_quotes_or_newline(self):
        self.assertProgram("(display 42)\n", "42")  # 不换行：整段程序只有这两个字符
        self.assertProgram('(display "hello")\n(newline)\n', "hello\n")  # 字符串不带引号
        self.assertProgram("(newline)\n", "\n")

    def test_display_shares_the_top_level_stream(self):
        self.assertProgram("(display 1) (newline) (* 2 3)\n", "1\n6\n")

    # ------------------------------------------------- §6 列表就是点对链

    def test_list_notation_is_shorthand_for_a_pair_chain(self):
        # spec §6：(1 2 3) 就是 (1 . (2 . (3 . ())))，() 是链的终点
        self.assertProgram("'(1 . (2 . (3 . ())))\n", "(1 2 3)\n")
        self.assertProgram("(equal? '(1 . (2 . (3 . ()))) '(1 2 3))\n", "#t\n")
        self.assertProgram("(cdr (cdr '(1 2 3)))\n", "(3)\n")
        self.assertProgram("(cdr (cdr (cdr '(1 2 3))))\n", "()\n")

    def test_cons_builds_chains_and_pairs(self):
        self.assertProgram("(cons 1 '(2 3))\n", "(1 2 3)\n")  # 把 1 接到链头
        self.assertProgram("(cons 1 '())\n", "(1)\n")
        self.assertProgram("(cons 1 2)\n", "(1 . 2)\n")  # 第二项不是链 → 点对

    def test_quoted_and_list_built_forms_agree(self):
        # spec §6：两者结果相同，只是写法不同（数据 vs 函数调用）
        self.assertProgram("'(1 2 3)\n(list 1 2 3)\n", "(1 2 3)\n(1 2 3)\n")
        self.assertProgram("(equal? '(1 2 3) (list 1 2 3))\n", "#t\n")

    def test_recursion_example_from_spec(self):
        # spec §7 的阶乘例子：只用 §5 的算术与比较
        self.assertProgram(
            "(define (fact n) (if (= n 0) 1 (* n (fact (- n 1)))))\n(fact 3)\n",
            "fact\n6\n",
        )

    # ---------------------------------------------------------------- §8 打印

    def test_printing_table_for_simple_values(self):
        self.assertProgram("42\n", "42\n")  # 整数
        self.assertProgram("0.5\n", "0.5\n")  # 浮点
        self.assertProgram("#t\n", "#t\n")
        self.assertProgram("#f\n", "#f\n")
        self.assertProgram("'foo\n", "foo\n")  # 符号
        self.assertProgram('"hello"\n', '"hello"\n')  # 字符串带引号
        self.assertProgram("car\n", "#<procedure>\n")  # spec 说不依赖确切格式，这里按实现断言

    def test_printing_table_for_compound_values(self):
        self.assertProgram("'(1 2 3)\n", "(1 2 3)\n")  # 真列表
        self.assertProgram("(cons 1 2)\n", "(1 . 2)\n")  # 点对
        self.assertProgram("'()\n", "()\n")  # 空表
        self.assertProgram("'(1 (2 3) \"s\")\n", "(1 (2 3) \"s\")\n")  # 嵌套结构与字符串
        self.assertProgram("'(a \"b\" #t 1.5)\n", "(a \"b\" #t 1.5)\n")

    def test_string_printing_escapes_control_characters(self):
        self.assertProgram('"a\\nb\\tc"\n', '"a\\nb\\tc"\n')  # 打印成 \n \t 转义形式
        self.assertProgram('(display "a\\nb\\tc")\n(newline)\n', "a\nb\tc\n")  # display 输出真实字符

    def test_display_omits_quotes_inside_lists(self):
        self.assertProgram('(display (list 1 "a"))\n(newline)\n', "(1 a)\n")
        self.assertProgram("(display '(1 2 3))\n(newline)\n", "(1 2 3)\n")


class TestSpecEvalRulesAndErrors(SpecTestBase):
    """§9 求值规则（应用序 / 词法作用域 / 真假）与错误类别（§11）。"""

    # -------------------------------------------------------- §9 应用序求值

    def test_operator_and_operands_are_evaluated_left_to_right(self):
        # spec §5 开头：内置过程的实参先全部求值，再调用；§9：应用序求值
        self.assertProgram("((begin (display 'o) list) (begin (display 'a) 1))\n", "oa(1)\n")
        self.assertProgram("((begin (display 'f) car) '(1 2))\n", "f1\n")

    def test_builtin_arguments_really_are_evaluated(self):
        # 和特殊形式相反：传进内置过程的表达式都会被求值
        self.assertProgram("(list (+ 1 1) (- 3 1))\n", "(2 2)\n")
        self.assertProgram("(list 1 (/ 3 2) 3)\n", "(1 1 3)\n")

    # -------------------------------------------------- §9 词法作用域与闭包

    def test_scope_is_lexical_not_dynamic(self):
        # get 看到的是**定义处**的 x（outer），而不是调用处的 inner
        self.assertProgram(
            "(define x 'outer)\n(define (get) x)\n(let ((x 'inner)) (get))\n",
            "x\nget\nouter\n",
        )

    def test_define_makes_its_name_visible_inside_the_body(self):
        self.assertProgram(
            "(define (count-down n) (if (= n 0) 'done (count-down (- n 1))))\n(count-down 3)\n",
            "count-down\ndone\n",
        )

    # ------------------------------------------------------- §9 只有 #f 为假

    def test_only_false_is_false(self):
        self.assertProgram("(if 0 'yes 'no)\n", "yes\n")
        self.assertProgram("(if '() 'yes 'no)\n", "yes\n")
        self.assertProgram("(if \"\" 'yes 'no)\n", "yes\n")
        self.assertProgram("(if #f 'yes 'no)\n", "no\n")
        # and / or 用同一套真假规则
        self.assertProgram("(and 0 'truthy)\n", "truthy\n")
        self.assertProgram("(or #f 0)\n", "0\n")

    # ------------------------------------------------- 错误类别（spec §11）

    def assertSchemeError(self, program, error_type, needle=None):
        """整段程序必须抛指定类别的 SchemeError；给出 needle 时消息里要含它。"""
        with self.assertRaises(error_type) as context:
            self.run_program(program)
        if needle is not None:
            self.assertIn(needle, str(context.exception))
        return context.exception

    def test_wrong_operand_order_is_an_error(self):
        # §1/§11：写成 (1 + 2) 时，第一个元素不是过程
        self.assertSchemeError("(1 + 2)\n", SchemeTypeError, "1")

    def test_data_in_operator_position_is_an_error(self):
        # §11：忘了 quote，解释器就会试着把 1 当过程调用
        self.assertSchemeError("(car (1 2 3))\n", SchemeTypeError, "1")
        self.assertSchemeError("()\n", SchemeSyntaxError)

    def test_unbound_name_is_an_error(self):
        self.assertSchemeError("nope\n", SchemeNameError, "nope")
        self.assertSchemeError("(define f (lambda (x) y))\n(f 1)\n", SchemeNameError, "y")

    def test_type_mismatch_is_an_error(self):
        self.assertSchemeError("(+ 1 #t)\n", SchemeTypeError, "+")
        self.assertSchemeError("(car '())\n", SchemeTypeError, "car")
        self.assertSchemeError("(length 5)\n", SchemeError)
        self.assertSchemeError("(car 5)\n", SchemeError)

    def test_wrong_argument_count_is_an_error(self):
        self.assertSchemeError("(car)\n", SchemeArityError, "car")
        self.assertSchemeError("(car '(1) '(2))\n", SchemeArityError, "car")
        # 自己定义的函数同样按参数个数报错
        self.assertSchemeError("(define (square x) (* x x))\n(square 1 2)\n", SchemeArityError, "square")

    def test_division_by_zero_is_a_scheme_error_not_a_python_one(self):
        for program in ("(/ 1 0)\n", "(quotient 1 0)\n", "(modulo 1 0)\n"):
            error = self.assertSchemeError(program, SchemeError)
            self.assertNotIsInstance(error, ZeroDivisionError)

    def test_malformed_special_forms_are_syntax_errors(self):
        self.assertSchemeError("(define x)\n", SchemeSyntaxError)
        self.assertSchemeError("(if #t)\n", SchemeSyntaxError)
        self.assertSchemeError("(lambda (x . rest) x)\n", SchemeSyntaxError)  # §10 不在范围内
        self.assertSchemeError("(lambda (x x) x)\n", SchemeSyntaxError)  # 参数名重复
        self.assertSchemeError("(let (x 1) x)\n", SchemeSyntaxError)

    def test_unbalanced_parentheses_are_syntax_errors(self):
        self.assertSchemeError("(+ 1 2\n", SchemeSyntaxError)
        self.assertSchemeError("(+ 1 2))\n", SchemeSyntaxError)

    def test_evaluation_stops_at_the_first_bad_expression(self):
        # 出错之前的结果已经打印，出错那一刻就停（后面的表达式不再求值）
        stream = io_stream.StringIO()
        with contextlib.redirect_stdout(stream):
            with self.assertRaises(SchemeNameError):
                main.run_source("(display 1) (newline) nope\n(display 2)\n", make_global_env())
        self.assertEqual(stream.getvalue(), "1\n")


class TestSpecCLIConventions(SpecTestBase):
    """§2 CLI 约定（本段：错误路径 + 成功路径）。

    stdin 与"多文件共享全局环境"留给下一段。
    """

    def run_cli(self, *sources):
        """把源码写进临时 .scm 文件，按 CLI 的方式运行入口，返回 (退出码, stdout, stderr)。"""
        out, err = io_stream.StringIO(), io_stream.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for index, source in enumerate(sources):
                path = os.path.join(tmp, f"program{index}.scm")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(source)
                paths.append(path)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main.main(paths)
        return code, out.getvalue(), err.getvalue()

    def assertOneLineError(self, err, needle=None):
        """§11：错误只写 stderr 一行、以 `error: ` 开头，不能出现 Python traceback。"""
        self.assertTrue(err.startswith("error: "), msg=f"stderr={err!r}")
        self.assertEqual(err.count("\n"), 1, msg=f"stderr 应当只有一行：{err!r}")
        self.assertNotIn("Traceback", err, msg=f"stderr 不应含 traceback：{err!r}")
        if needle is not None:
            self.assertIn(needle, err)

    # ------------------------------------------------------------ 成功路径

    def test_success_path_is_clean(self):
        code, out, err = self.run_cli("(+ 1 2)\n(* 2 3)\n")
        self.assertEqual(code, 0)  # 正常结束
        self.assertEqual(out, "3\n6\n")  # 每个顶层结果独占一行
        self.assertEqual(err, "")  # 成功时 stderr 必须为空

    def test_empty_program_succeeds_silently(self):
        self.assertEqual(self.run_cli("; 只有注释\n"), (0, "", ""))

    def test_display_and_newline_do_not_add_extra_lines(self):
        # display/newline 返回 None → 不产生额外结果行；(newline) 自己提供换行
        code, out, err = self.run_cli("(display 1)\n(newline)\n(* 2 3)\n")
        self.assertEqual((code, out, err), (0, "1\n6\n", ""))

    def test_none_results_are_not_printed(self):
        code, out, err = self.run_cli("(define x 1)\n(if #f 'nope)\n(begin)\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "x\n")  # define 返回符号名；另外两个是无值 → 不打印
        self.assertEqual(err, "")

    # ------------------------------------------------------------ 错误路径

    def test_error_path_uses_exit_code_1_and_one_stderr_line(self):
        code, out, err = self.run_cli("(car '())\n")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")  # stdout 保持干净，评分器逐字节比对才不会被污染
        self.assertOneLineError(err, "car")

    def test_results_before_the_error_are_kept_on_stdout(self):
        code, out, err = self.run_cli("(+ 1 2)\n(display 3)\n(newline)\n(undefined-name)\n(+ 4 5)\n")
        self.assertEqual(code, 1)
        self.assertEqual(out, "3\n3\n")  # 出错行之后不再求值，所以没有 9
        self.assertOneLineError(err, "undefined-name")

    def test_every_user_error_is_a_single_clean_line(self):
        programs = (
            "(1 + 2)\n",  # §1 语序写错
            "(+ 1 #t)\n",  # 类型不符
            "(car)\n",  # 参数个数不符
            "(/ 1 0)\n",  # 除零
            "no-such-name\n",  # 未绑定名字
            "(+ 1 2\n",  # 括号不配对
        )
        for program in programs:
            with self.subTest(program=program):
                code, out, err = self.run_cli(program)
                self.assertEqual(code, 1, msg=f"{program!r} 的 stderr={err!r}")
                self.assertEqual(out, "", msg=f"{program!r} 不应写 stdout")
                self.assertOneLineError(err)

    def test_runaway_recursion_is_reported_as_one_line(self):
        # spec §10 不要求尾调用优化：失控递归也要按 §11 的格式报错，而不是抛 Python traceback
        code, out, err = self.run_cli("(define (loop n) (+ 1 (loop (+ n 1))))\n(loop 0)\n")
        self.assertEqual(code, 1)
        self.assertEqual(out, "loop\n")  # 出错前的 define 结果照常打印
        self.assertOneLineError(err, "递归")

    # ------------------------------------------------- stdin（无文件参数时）

    def run_cli_stdin(self, source):
        """没有文件参数时入口从 stdin 读程序；这里用 StringIO 顶替 sys.stdin（spec §2）。"""
        out, err = io_stream.StringIO(), io_stream.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with mock.patch("sys.stdin", io_stream.StringIO(source)):
                code = main.main([])
        return code, out.getvalue(), err.getvalue()

    def test_no_arguments_reads_stdin(self):
        code, out, err = self.run_cli_stdin("(display 1) (newline)\n(+ 1 2)\n")
        self.assertEqual((code, out, err), (0, "1\n3\n", ""))

    def test_stdin_program_can_define_and_use_names(self):
        self.assertEqual(self.run_cli_stdin("(define x 41)\n(+ x 1)\n"), (0, "x\n42\n", ""))

    def test_empty_stdin_succeeds_silently(self):
        self.assertEqual(self.run_cli_stdin(""), (0, "", ""))

    def test_stdin_error_path_matches_the_file_path(self):
        code, out, err = self.run_cli_stdin("(+ 1 2)\n(car '())\n")
        self.assertEqual(code, 1)
        self.assertEqual(out, "3\n")  # 出错前的结果照常打印
        self.assertOneLineError(err, "car")

    def test_files_take_priority_over_stdin(self):
        # spec §2：给了文件就读文件，stdin 完全不参与
        with mock.patch("sys.stdin", io_stream.StringIO("(+ 100 100)\n")):
            self.assertEqual(self.run_cli("(+ 1 2)\n"), (0, "3\n", ""))

    # -------------------------------------------- 多文件共享同一个全局环境

    def test_files_share_one_global_environment(self):
        self.assertEqual(self.run_cli("(define x 41)", "(+ x 1)"), (0, "x\n42\n", ""))

    def test_files_are_evaluated_in_order(self):
        code, out, err = self.run_cli("(define x 1)\n", "(define y (+ x 1))\n", "(+ x y)\n")
        self.assertEqual((code, out, err), (0, "x\ny\n3\n", ""))

    def test_later_file_can_redefine_what_an_earlier_one_defined(self):
        self.assertEqual(
            self.run_cli("(define x 1)\n", "(define x 2)\n", "x\n"),
            (0, "x\nx\n2\n", ""),
        )

    def test_error_in_one_file_stops_the_following_files(self):
        code, out, err = self.run_cli("(+ 1 2)\n", "(car '())\n", "(display 'never)\n")
        self.assertEqual(code, 1)
        self.assertEqual(out, "3\n")  # 出错之后的文件不再求值
        self.assertOneLineError(err, "car")


if __name__ == "__main__":
    unittest.main()
