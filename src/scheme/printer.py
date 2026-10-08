"""打印：值 → 文本。spec §8。

两种形式（差别只在字符串）：
    to_write(value)     write 形式：字符串带引号并转义（\\n \\t \\" \\\\），顶层结果用它
    to_display(value)   display 形式：字符串不带引号（spec §5 display）

其它约定：
- 真列表打印 `(1 2 3)`，点对打印 `(1 . 2)`，空表打印 `()`；
- 浮点打印成 `0.5` / `3.14` 这种最简形式（Phase 2 验收：`(/ 2)` 的输出必须是 `0.5`）；
- 过程打印 `#<procedure>`（Phase 2 加入内置过程，Phase 4 再加入闭包；
  验收测试不依赖确切格式，spec §8）。
"""
from __future__ import annotations

from .datatypes import NIL, Closure, Pair, PrimitiveProcedure, Symbol
from .errors import SchemeTypeError


def to_write(value: object) -> str:
    """write 形式：字符串带引号并转义，用于顶层结果的打印（spec §8）。"""
    return _to_text(value, write_form=True)


def to_display(value: object) -> str:
    """display 形式：字符串不带引号（嵌套字符串同样跟随，spec §5）。"""
    return _to_text(value, write_form=False)


def _to_text(value: object, write_form: bool) -> str:
    """把任意值转成文本；write_form 决定字符串是否带引号（嵌套字符串同样跟随）。"""
    if value is None:
        # None 不是 Scheme 值，它表示"无值"（spec §2）；顶层不会打印它，
        # 万一 display 收到它，这里输出空串以免崩溃。
        return ""
    if isinstance(value, bool):  # 必须在 int 之前判定：Python 里 bool 是 int 的子类
        return "#t" if value else "#f"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _float_text(value)
    if isinstance(value, Symbol):  # 符号与字符串是不同类型（spec §11）
        return value.name
    if value is NIL:  # 空表：() 是"真值"，但打印成 ()
        return "()"
    if isinstance(value, Pair):  # 列表/点对（spec §6）
        return _pair_text(value, write_form)
    if isinstance(value, str):
        return _string_text(value) if write_form else value
    if isinstance(value, (PrimitiveProcedure, Closure)):  # 过程（spec §8：格式不敏感）
        return "#<procedure>"
    raise SchemeTypeError(f"无法打印的值：{value!r}")


def _float_text(value: float) -> str:
    """浮点的打印形式：`0.5` / `3.14` / `-0.5`（Python 的最短往返表示）。"""
    return repr(value)


def _string_text(text: str) -> str:
    """字符串的 write 形式：带引号，并转义反斜杠、双引号、换行与制表符。"""
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return '"' + escaped + '"'


def _pair_text(pair: Pair, write_form: bool) -> str:
    """点对链的文本形式：真列表 `(1 2 3)`、点对 `(1 . 2)`、`(1 2 . 3)`。"""
    parts = []
    current: object = pair
    while isinstance(current, Pair):
        parts.append(_to_text(current.car, write_form))
        current = current.cdr
    if current is not NIL:  # 链尾不是空表 → 点对（spec §6）
        parts.append(".")
        parts.append(_to_text(current, write_form))
    return "(" + " ".join(parts) + ")"
