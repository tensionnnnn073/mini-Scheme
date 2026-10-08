"""谓词内置过程（spec §5 的"谓词"各行）。

清单：number?、boolean?、symbol?、string?、procedure?、zero?、even?、odd?、
eq?、equal?。（`not` 已由 arithmetic 提供——spec §5 把它归在"布尔"行，这里不重复注册。）

必须遵守的语义（Phase 8 验收点）：
- 类型谓词要小心 Python 的类型关系：`bool` 是 `int` 的子类，所以 `(number? #t)` = #f；
  `Symbol` 是 `str` 的子类，所以 `(string? 'x)` = #f、`(symbol? "x")` = #f（spec §11）；
- `zero?` / `even?` / `odd?` 的参数必须是数，否则抛 SchemeTypeError；
- `eq?` 对符号/数字/布尔按值比较，对复合数据按**同一性**：
  `(eq? '() '())` = #t（靠空表单例）、`(eq? '(1) '(1))` = #f；
- `equal?` 是结构相等，且**先比类型再比值**：
  `(equal? #t 1)` = #f、`(equal? 'a "a")` = #f、`(equal? '(1 2 3) (list 1 2 3))` = #t。

公开产物：
    PROCEDURES     (名字, 实现, 最少参数, 最多参数) 表；max_args=None 表示不限
    install(env)   把表里的过程装进初始环境（由 builtins.install_builtins 调用）
"""
from __future__ import annotations

from ..datatypes import NIL, Closure, Pair, PrimitiveProcedure, Symbol
from ..errors import SchemeTypeError
from ..printer import to_write


def _describe(value: object) -> str:
    """把值写成给人看的文本（只用于错误信息，不参与正常输出）。"""
    return to_write(value)


def _is_number(value: object) -> bool:
    """是不是数字：布尔不算（Python 里 True == 1，spec §11）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_string(value: object) -> bool:
    """是不是字符串：符号是 str 的子类，必须排除（spec §11）。"""
    return isinstance(value, str) and not isinstance(value, Symbol)


def _require_number(name: str, value: object) -> object:
    """数值谓词的参数必须是数，否则抛 SchemeTypeError（spec §5）。"""
    if not _is_number(value):
        raise SchemeTypeError(f"{name}：参数必须是数字，实际收到 {_describe(value)}")
    return value


def _number(args: "list") -> bool:
    """`(number? 5)` = #t、`(number? 'x)` = #f、`(number? #t)` = #f（spec §5）。"""
    return _is_number(args[0])


def _boolean(args: "list") -> bool:
    """`(boolean? #t)` = #t、`(boolean? 0)` = #f（spec §5）。"""
    return isinstance(args[0], bool)


def _symbol(args: "list") -> bool:
    """`(symbol? 'x)` = #t、`(symbol? "x")` = #f（spec §5）。"""
    return isinstance(args[0], Symbol)


def _string(args: "list") -> bool:
    """`(string? "s")` = #t、`(string? 's)` = #f（符号是字符串的子类，spec §11）。"""
    return _is_string(args[0])


def _procedure(args: "list") -> bool:
    """`(procedure? car)` = #t、`(procedure? (lambda (x) x))` = #t、`(procedure? 1)` = #f。"""
    return isinstance(args[0], (PrimitiveProcedure, Closure))


def _zero(args: "list") -> bool:
    """`(zero? 0)` = #t（含 0.0）；参数必须是数（spec §5）。"""
    return _require_number("zero?", args[0]) == 0


def _even(args: "list") -> bool:
    """`(even? 8)` = #t；参数必须是数（spec §5）。"""
    return _require_number("even?", args[0]) % 2 == 0


def _odd(args: "list") -> bool:
    """`(odd? 7)` = #t；参数必须是数（spec §5）。"""
    return _require_number("odd?", args[0]) % 2 != 0


def _eq(args: "list") -> bool:
    """`(eq? '() '())` = #t、`(eq? '(1) '(1))` = #f（spec §5/§11）。

    符号、数字、布尔按值比较（布尔与数字算不同类型，所以 `(eq? #t 1)` = #f）；
    其余复合数据（点对、字符串、过程）按同一性比较。
    """
    left, right = args
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if _is_number(left) and _is_number(right):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left == right
    return left is right  # 空表（单例）、点对、字符串、过程：同一性


def _equal(args: "list") -> bool:
    """`(equal? '(1 2 3) (list 1 2 3))` = #t、`(equal? #t 1)` = #f（spec §5/§11）。"""
    return _equal_values(args[0], args[1])


def _equal_values(left: object, right: object) -> bool:
    """结构相等：先比类型再比值，点对链逐层比较（spec §11 的两条排错提示）。"""
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right  # 布尔只与布尔相等：#t 与 1 不同
    if _is_number(left) and _is_number(right):
        return type(left) is type(right) and left == right  # 1 与 1.0 类型不同 → #f
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left == right
    if _is_string(left) and _is_string(right):  # 符号分支已排除 'a 与 "a" 相等
        return left == right
    if isinstance(left, Pair) and isinstance(right, Pair):
        return _equal_values(left.car, right.car) and _equal_values(left.cdr, right.cdr)
    if left is NIL or right is NIL:
        return left is NIL and right is NIL
    return left is right  # 过程等：同一性


# (名字, 实现, 最少参数, 最多参数)；max_args 为 None 表示参数个数不限（spec §5）。
PROCEDURES = (
    ("number?", _number, 1, 1),
    ("boolean?", _boolean, 1, 1),
    ("symbol?", _symbol, 1, 1),
    ("string?", _string, 1, 1),
    ("procedure?", _procedure, 1, 1),
    ("zero?", _zero, 1, 1),
    ("even?", _even, 1, 1),
    ("odd?", _odd, 1, 1),
    ("eq?", _eq, 2, 2),
    ("equal?", _equal, 2, 2),
)


def install(env: object) -> None:
    """把本模块的内置过程装进 env（spec §5）。"""
    for name, impl, min_args, max_args in PROCEDURES:
        env.define(name, PrimitiveProcedure(name, impl, min_args, max_args))
