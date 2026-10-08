"""算术与比较内置过程（spec §5 的"算术""比较""布尔 not"三行）。

必须遵守的语义（Phase 2 验收点）：
- 可变参数恒等式：`(+)` = 0，`(*)` = 1，`(- 5)` = -5；
- 整数相除取整数商且负数向零截断：`(/ 7 2)` = 3，`(/ -7 2)` = -3（注意 Python `//` 是向下取整）；
- 单参数 `/` 求倒数，结果是浮点：`(/ 2)` = 0.5；
- `modulo` / `quotient` 只接受整数：`(modulo 17 5)` = 2，`(quotient -7 2)` = -3；
- `expt`：`(expt 2 10)` = 1024；`abs`：`(abs (- 5 9))` = 4；
- 比较是链式的（相邻两两都成立才为真）且支持数字与符号：`(< 2 3 4)` = #t。

公开产物：
    PROCEDURES     (名字, 实现, 最少参数, 最多参数) 表；max_args=None 表示不限
    install(env)   把表里的过程装进初始环境（由 builtins.install_builtins 调用）

除零、参数类型不符、参数个数不符、结果不是实数等情况一律抛 SchemeError 的
子类，不让 Python 原生异常冒泡到入口（spec §11）。
"""
from __future__ import annotations

import operator
from typing import Callable

from ..datatypes import PrimitiveProcedure, Symbol, is_truthy
from ..errors import SchemeError, SchemeTypeError
from ..printer import to_write


def _describe(value: object) -> str:
    """把值写成给人看的文本（只用于错误信息，不参与正常输出）。"""
    return to_write(value)


def _require_numbers(name: str, args: "list") -> None:
    """校验全部实参都是数字；布尔**不算**数字（Python 里 True == 1，spec §11）。"""
    for value in args:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemeTypeError(f"{name}：参数必须是数字，实际收到 {_describe(value)}")


def _require_integers(name: str, args: "list") -> None:
    """校验全部实参都是整数（浮点与布尔都不算，spec §5 的 modulo / quotient）。"""
    for value in args:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SchemeTypeError(f"{name}：参数必须是整数，实际收到 {_describe(value)}")


def _require_orderable(name: str, args: "list") -> None:
    """比较的参数要么全是数字、要么全是符号（spec §5：比较支持数字与符号）。"""
    if all(isinstance(value, Symbol) for value in args):
        return
    _require_numbers(name, args)


def _add(args: "list") -> object:
    """`(+)` = 0，`(+ 1 2 3)` = 6；只要有一个浮点，结果就是浮点。"""
    _require_numbers("+", args)
    total: object = 0
    for value in args:
        total = total + value
    return total


def _subtract(args: "list") -> object:
    """`(- 5)` = -5（单参数取反），`(- 10 4 1)` = 5（从左到右）。"""
    _require_numbers("-", args)
    if len(args) == 1:
        return -args[0]
    result: object = args[0]
    for value in args[1:]:
        result = result - value
    return result


def _multiply(args: "list") -> object:
    """`(*)` = 1，`(* 2 3 4)` = 24。"""
    _require_numbers("*", args)
    product: object = 1
    for value in args:
        product = product * value
    return product


def _divide(args: "list") -> object:
    """`(/ 2)` = 0.5（单参数求倒数，浮点），`(/ 7 2)` = 3、`(/ -7 2)` = -3（spec §5）。"""
    _require_numbers("/", args)
    if len(args) == 1:
        return _true_divide(1, args[0])
    result: object = args[0]
    for value in args[1:]:
        result = _divide_pair(result, value)
    return result


def _divide_pair(left: object, right: object) -> object:
    """两数相除：都是整数时取整数商（向零截断），否则用浮点除法。"""
    if isinstance(left, int) and isinstance(right, int):
        return _truncating_quotient(left, right)
    return _true_divide(left, right)


def _true_divide(left: object, right: object) -> float:
    """浮点除法；除数为零时抛 SchemeError（不让 Python 的 ZeroDivisionError 冒泡）。"""
    if right == 0:
        raise SchemeError("除法出错：除数为零")
    return left / right


def _truncating_quotient(left: int, right: int) -> int:
    """整数商，负数商向零截断：Python 的 `//` 是向下取整，所以要自己算（spec §5）。"""
    if right == 0:
        raise SchemeError("整除出错：除数为零")
    quotient = abs(left) // abs(right)
    if (left < 0) != (right < 0):
        quotient = -quotient
    return quotient


def _modulo(args: "list") -> object:
    """`(modulo 17 5)` = 2；语义与 Python 的 `%` 一致（spec §5）。"""
    _require_integers("modulo", args)
    left, right = args
    if right == 0:
        raise SchemeError("modulo：除数为零")
    return left % right


def _quotient(args: "list") -> object:
    """`(quotient 17 5)` = 3，`(quotient -7 2)` = -3（负数商向零截断）。"""
    _require_integers("quotient", args)
    left, right = args
    return _truncating_quotient(left, right)


def _expt(args: "list") -> object:
    """`(expt 2 10)` = 1024，`(expt 2 -1)` = 0.5（spec §5）。"""
    _require_numbers("expt", args)
    base, power = args
    try:
        result = base ** power
    except (OverflowError, ValueError, ZeroDivisionError) as error:
        raise SchemeError(
            f"expt：无法计算 {_describe(base)} 的 {_describe(power)} 次方"
        ) from error
    if isinstance(result, complex):  # 例如 (expt -8 0.5)：mini-Scheme 没有复数
        raise SchemeError("expt：结果不是实数")
    return result


def _abs(args: "list") -> object:
    """`(abs (- 5 9))` = 4。"""
    _require_numbers("abs", args)
    return abs(args[0])


def _not(args: "list") -> bool:
    """`(not #f)` = #t，`(not 0)` = #f（只有 #f 是假，spec §5/§9）。"""
    return not is_truthy(args[0])


def _comparison(name: str, compare: Callable[[object, object], bool]) -> Callable[[list], bool]:
    """造一个链式比较过程：相邻两两都成立才为真（spec §5）。"""

    def compare_chain(args: "list") -> bool:
        """相邻两两比较都成立才为真；实参类型由 _require_orderable 校验（spec §5）。"""
        _require_orderable(name, args)
        for left, right in zip(args, args[1:]):
            if not compare(left, right):
                return False
        return True

    compare_chain.__name__ = f"compare_{name}"
    return compare_chain


# (名字, 实现, 最少参数, 最多参数)；max_args 为 None 表示参数个数不限（spec §5）。
PROCEDURES = (
    ("+", _add, 0, None),
    ("-", _subtract, 1, None),
    ("*", _multiply, 0, None),
    ("/", _divide, 1, None),
    ("modulo", _modulo, 2, 2),
    ("quotient", _quotient, 2, 2),
    ("expt", _expt, 2, 2),
    ("abs", _abs, 1, 1),
    ("=", _comparison("=", operator.eq), 1, None),
    ("<", _comparison("<", operator.lt), 1, None),
    (">", _comparison(">", operator.gt), 1, None),
    ("<=", _comparison("<=", operator.le), 1, None),
    (">=", _comparison(">=", operator.ge), 1, None),
    ("not", _not, 1, 1),
)


def install(env: object) -> None:
    """把本模块的内置过程装进 env（spec §5）。"""
    for name, impl, min_args, max_args in PROCEDURES:
        env.define(name, PrimitiveProcedure(name, impl, min_args, max_args))
