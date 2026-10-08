"""运行时数据表示与列表工具。

mini-Scheme 的值只有这几种（spec §8）：整数 int / 浮点 float / 布尔 bool /
字符串 str / 符号 Symbol / 空表 / 点对 / 过程。

关键设计约定
- Symbol 是独立类型，**不能**继承 str，否则 `(equal? 'a "a")` 会判成相等（spec §11）；
- 布尔与数字在判定时必须先区分（Python 里 `True == 1` 且 bool 是 int 子类），
  否则 `(equal? #t 1)` 会判成相等（spec §11）；
- 列表是点对链 `(1 . (2 . (3 . ())))`，空表是全局唯一单例，
  保证 `'(1 2 3)` 与 `(list 1 2 3)` 表示一致、`(eq? '() '())` 为真（spec §5/§6）。

公开接口：
    Symbol(name)                          符号，按名字比较/排序（Phase 1）
    Pair(car, cdr)                        点对（Phase 1）
    NIL                                   空表单例（Phase 1）
    DottedList(items, tail)               (a . b) 的读入期结构，只用于读入（Phase 1）
    to_data(expr)                         源程序结构 → 运行时数据（quote 用，Phase 1）
    scheme_list(items) / iter_list(pair)  点对链工具（Phase 1）
    PrimitiveProcedure(name, impl, min_args, max_args)  内置过程（Phase 2）
    is_truthy(value)                      只有 #f 是假（spec §4.4/§9）（Phase 2）
    Closure(params, body, env, name)      用户函数（闭包）：参数名 + 函数体 + 定义时环境（Phase 4）
"""
from __future__ import annotations

from typing import Callable

from .errors import SchemeTypeError


class Symbol:
    """符号（spec §3）：表示名字；按名字比较与排序，与字符串是不同类型。

    与字符串分开是刻意的：Python 里如果让符号继承 str，`(equal? 'a "a")`
    就会判成相等（spec §11）。比较运算符供 spec §5 的链式比较在符号上使用。
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Symbol) and self.name == other.name

    def __hash__(self) -> int:
        return hash(("scheme-symbol", self.name))

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Symbol):
            return NotImplemented
        return self.name < other.name

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Symbol):
            return NotImplemented
        return self.name <= other.name

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Symbol):
            return NotImplemented
        return self.name > other.name

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Symbol):
            return NotImplemented
        return self.name >= other.name

    def __repr__(self) -> str:
        return f"Symbol({self.name!r})"

    def __str__(self) -> str:
        return self.name


class Pair:
    """点对（spec §6）：car 是头，cdr 是尾（另一个点对，或空表 NIL）。

    这里刻意**不定义** __eq__：Python 的默认行为就是"同一性"比较，正好对应
    `eq?` 对复合数据的语义（spec §11）；结构相等是 equal? 的事（Phase 8）。
    """

    __slots__ = ("car", "cdr")

    def __init__(self, car: object, cdr: object) -> None:
        self.car = car
        self.cdr = cdr

    def __repr__(self) -> str:
        return f"Pair({self.car!r}, {self.cdr!r})"


class _EmptyList:
    """空表（spec §6 里点对链的终点）。整个解释器只有 NIL 这一个实例。"""

    __slots__ = ()

    def __repr__(self) -> str:
        return "()"

    def __str__(self) -> str:
        return "()"


# 空表单例：让 `'(1 2 3)` 与 `(list 1 2 3)` 表示一致、并保证 (eq? '() '()) 为真。
# 注意它是"真值"（spec §9：只有 #f 是假），所以这里不定义 __bool__。
NIL = _EmptyList()


class DottedList:
    """点对写法 `(a b . c)` 的读入期结构，只在 parser 与 to_data 之间传递。

    items 是点号前面的元素，tail 是点号后面的那个表达式。它不是运行时数据，
    求值时（quote）会由 to_data 变成真正的点对链。
    """

    __slots__ = ("items", "tail")

    def __init__(self, items: "list", tail: object) -> None:
        self.items = list(items)
        self.tail = tail

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, DottedList)
            and self.items == other.items
            and self.tail == other.tail
        )

    def __repr__(self) -> str:
        return f"DottedList({self.items!r}, {self.tail!r})"


def to_data(expr: object) -> object:
    """把源程序结构转成运行时数据（quote 的语义，spec §4.1/§6）。

    `(1 2 3)` 这一层括号结构在这里变成点对链，产物与 `(list 1 2 3)` 完全一致；
    数字 / 浮点 / 布尔 / 字符串 / 符号原样返回。
    """
    if isinstance(expr, list):
        return scheme_list([to_data(item) for item in expr])
    if isinstance(expr, DottedList):
        return _chain([to_data(item) for item in expr.items], to_data(expr.tail))
    return expr


def scheme_list(items: "list") -> object:
    """把 Python 可迭代对象装成点对链（链尾是 NIL）。"""
    return _chain(list(items), NIL)


def _chain(items: "list", tail: object) -> object:
    """把 items 依次 cons 到 tail 前面，得到 (items... . tail)。"""
    result = tail
    for item in reversed(items):
        result = Pair(item, result)
    return result


def iter_list(pair: object) -> "list":
    """把真列表展开成 Python 列表；链尾不是 NIL（非真列表）时抛 SchemeTypeError。"""
    items = []
    current = pair
    while isinstance(current, Pair):
        items.append(current.car)
        current = current.cdr
    if current is not NIL:
        raise SchemeTypeError("不是真列表：无法展开成元素序列")
    return items


class PrimitiveProcedure:
    """内置过程（spec §5）：名字 + Python 实现 + 允许的参数个数。

    impl 接收一个 Python 列表（已经求值好的实参）并返回 Scheme 值；
    参数个数的校验统一交给 evaluator.apply（max_args 为 None 表示不限），
    这样每个内置过程只需要关心自己的类型检查与语义。
    """

    __slots__ = ("name", "impl", "min_args", "max_args")

    def __init__(
        self,
        name: str,
        impl: Callable[[list], object],
        min_args: int = 0,
        max_args: "int | None" = None,
    ) -> None:
        self.name = name
        self.impl = impl
        self.min_args = min_args
        self.max_args = max_args

    def __repr__(self) -> str:
        return f"PrimitiveProcedure({self.name!r})"


class Closure:
    """用户定义的函数（spec §4.6/§4.7）：参数名 + 函数体 + **定义时**的环境。

    保存定义时的环境就是"闭包"的全部秘密（spec §9）：函数体里出现的外层变量会在
    **调用**时沿 env 这条链去找，所以看到的是定义处的绑定，而不是调用处的。
    name 只用于错误信息（匿名 lambda 的名字就是 "lambda"）。
    """

    __slots__ = ("params", "body", "env", "name")

    def __init__(self, params: "list", body: "list", env: object, name: str = "lambda") -> None:
        self.params = list(params)  # 参数名（Symbol 列表，个数固定，spec §10）
        self.body = list(body)  # 函数体表达式列表，按 begin 语义求值
        self.env = env  # 定义时的环境：闭包捕获的就是它
        self.name = name

    def __repr__(self) -> str:
        names = " ".join(param.name for param in self.params)
        return f"Closure({self.name}, ({names}))"


def is_truthy(value: object) -> bool:
    """mini-Scheme 的真假判定：只有 #f 是假（spec §4.4/§9）。

    注意 `0`、`()`、`""` 都是真；`None` 表示"无值"（spec §2），不当假处理。
    """
    return value is not False
