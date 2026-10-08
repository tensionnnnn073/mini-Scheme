"""列表内置过程（spec §5 的"列表"各行）。

清单：cons、car、cdr、list、length、append、null?、pair?、list?。

必须遵守的语义（Phase 6 验收点，spec §6）：
- 列表就是点对链，一切列表数据（quote 的、cons 的、list 的）用同一种表示；
- `(cons 1 2)` = `(1 . 2)`（点对），`(cons 1 '(2 3))` = `(1 2 3)`；
- `pair?` 对非空点对为真、`()` 为假；`list?` 只对真列表（链尾是空表）为真，
  `(list? (cons 1 2))` = #f。

注意：`map` / `filter` **不内置**，验收测试要求用语言本身定义（spec §10）。

公开产物：
    PROCEDURES     (名字, 实现, 最少参数, 最多参数) 表；max_args=None 表示不限
    install(env)   把表里的过程装进初始环境（由 builtins.install_builtins 调用）

参数类型不符一律抛 SchemeTypeError（spec §11），不让 Python 原生异常冒泡到入口。
"""
from __future__ import annotations

from ..datatypes import NIL, Pair, PrimitiveProcedure, iter_list, scheme_list
from ..errors import SchemeTypeError
from ..printer import to_write


def _describe(value: object) -> str:
    """把值写成给人看的文本（只用于错误信息，不参与正常输出）。"""
    return to_write(value)


def _require_pair(name: str, value: object) -> None:
    """校验参数是点对（car / cdr 需要；空表与普通值都算类型不符，spec §6）。"""
    if not isinstance(value, Pair):
        raise SchemeTypeError(f"{name}：参数必须是点对（非空列表），实际收到 {_describe(value)}")


def _true_list(name: str, value: object) -> "list":
    """展开真列表成元素序列；链尾不是空表就报错，并带上过程名与实参（spec §6）。"""
    try:
        return iter_list(value)
    except SchemeTypeError as error:
        raise SchemeTypeError(f"{name}：{error}，实际收到 {_describe(value)}") from error


def _cons(args: "list") -> object:
    """`(cons 1 '(2 3))` = (1 2 3)；`(cons 1 2)` = (1 . 2)（spec §6）。"""
    return Pair(args[0], args[1])


def _car(args: "list") -> object:
    """`(car '(1 2 3))` = 1（spec §6）。"""
    _require_pair("car", args[0])
    return args[0].car


def _cdr(args: "list") -> object:
    """`(cdr '(1 2 3))` = (2 3)（spec §6）。"""
    _require_pair("cdr", args[0])
    return args[0].cdr


def _list(args: "list") -> object:
    """`(list 1 2 3)` = (1 2 3)，`(list)` = ()，与 `'(1 2 3)` 表示一致（spec §6）。"""
    return scheme_list(args)


def _length(args: "list") -> int:
    """`(length '(a b c d))` = 4；只接受真列表（spec §5）。"""
    return len(_true_list("length", args[0]))


def _append(args: "list") -> object:
    """`(append '(1 2) '(3 4))` = (1 2 3 4)（spec §5）。

    与 Scheme 一致：除最后一个参数外都必须是真列表，最后一个可以是任何值，
    所以 `(append)` = ()、`(append '(1) 2)` = (1 . 2)；结果是一条新链，不改动实参。
    """
    if not args:
        return NIL
    result: object = args[-1]
    for value in reversed(args[:-1]):
        for item in reversed(_true_list("append", value)):
            result = Pair(item, result)
    return result


def _null(args: "list") -> bool:
    """`(null? '())` = #t；只有空表单例算空表（spec §5/§6）。"""
    return args[0] is NIL


def _pair(args: "list") -> bool:
    """`(pair? '(1 2))` = #t、`(pair? '())` = #f（spec §5）。"""
    return isinstance(args[0], Pair)


def _is_list(args: "list") -> bool:
    """`(list? '(1 2))` = #t、`(list? (cons 1 2))` = #f（spec §5）。

    只要求判断，不必展开成元素序列，所以这里沿链走一遍（不额外分配内存）。
    """
    current: object = args[0]
    while isinstance(current, Pair):
        current = current.cdr
    return current is NIL


# (名字, 实现, 最少参数, 最多参数)；max_args 为 None 表示参数个数不限（spec §5）。
PROCEDURES = (
    ("cons", _cons, 2, 2),
    ("car", _car, 1, 1),
    ("cdr", _cdr, 1, 1),
    ("list", _list, 0, None),
    ("length", _length, 1, 1),
    ("append", _append, 0, None),
    ("null?", _null, 1, 1),
    ("pair?", _pair, 1, 1),
    ("list?", _is_list, 1, 1),
)


def install(env: object) -> None:
    """把本模块的内置过程装进 env（spec §5）。"""
    for name, impl, min_args, max_args in PROCEDURES:
        env.define(name, PrimitiveProcedure(name, impl, min_args, max_args))
