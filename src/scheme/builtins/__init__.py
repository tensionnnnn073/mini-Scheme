"""内置过程库（spec §5）：把全部内置过程安装进初始环境。

按 spec §5 的分类拆成四个子模块，各自提供 `install(env)`：
    arithmetic   + - * / modulo quotient expt abs 与链式比较 = < > <= >=
    predicates   not、类型谓词、数值谓词、eq? / equal?
    lists        cons car cdr list length append null? pair? list?
    io           display newline

公开接口：
    install_builtins(env)   按下面的顺序依次调用各子模块的 install

Phase 2 加入 arithmetic，Phase 6 加入 lists，Phase 7 加入 io，Phase 8 加入 predicates：
spec §5 的全部内置过程都已接入。
"""
from __future__ import annotations

from . import arithmetic, io, lists, predicates

# 各子模块按 spec §5 的分类分别安装（顺序不影响结果，只为便于阅读）。
_MODULES = (arithmetic, lists, io, predicates)


def install_builtins(env: object) -> None:
    """把所有已实现的内置过程装进初始环境（spec §5）。"""
    for module in _MODULES:
        module.install(env)
