"""输出内置过程（spec §5 的"输出"两行）。

- `display`：打印一个值，字符串不带引号、不换行，**返回 None**（顶层不打印）；
- `newline`：输出一个换行，**返回 None**。

输出必须写进标准输出（与顶层结果的打印共用同一个流），保证与评分器
逐字节比对的顺序一致；顶层结果用 write 形式，display 用 display 形式（printer 模块）。

公开产物：
    install(env, out=None)   把 display / newline 装进 env；out 省略时写 sys.stdout
                             （测试可以传 StringIO 抓输出）

参数个数不符抛 SchemeArityError（由 PrimitiveProcedure 统一检查，spec §11）。
"""
from __future__ import annotations

import sys
from typing import Callable

from ..datatypes import PrimitiveProcedure
from ..printer import to_display


def _display_to(stream: object) -> Callable[[list], None]:
    """造一个写到 stream 的 display：不换行、字符串不带引号、返回 None（spec §5）。"""

    def display(args: "list") -> None:
        """打印一个值写到安装时固定的流：字符串不带引号、不换行、返回 None（spec §5）。"""
        stream.write(to_display(args[0]))
        return None

    display.__name__ = "display"
    return display


def _newline_to(stream: object) -> Callable[[list], None]:
    """造一个写到 stream 的 newline：输出一个换行、返回 None（spec §5）。"""

    def newline(args: "list") -> None:
        """输出一个换行并返回 None（spec §5）。"""
        stream.write("\n")
        return None

    newline.__name__ = "newline"
    return newline


def install(env: object, out: object = None) -> None:
    """把 display / newline 装进 env；out 省略时写标准输出（spec §2/§5）。

    输出流在安装时固定下来（每个过程闭包捕获自己的 stream）：CLI 用默认的 sys.stdout，
    与顶层结果的打印共用同一个流，所以顺序与评分器逐字节比对一致；测试传入 StringIO
    即可抓取输出。表里的每一项仍是 (名字, 实现, 最少参数, 最多参数)，与其它子模块一致。
    """
    stream = sys.stdout if out is None else out
    procedures = (
        ("display", _display_to(stream), 1, 1),
        ("newline", _newline_to(stream), 0, 0),
    )
    for name, impl, min_args, max_args in procedures:
        env.define(name, PrimitiveProcedure(name, impl, min_args, max_args))
