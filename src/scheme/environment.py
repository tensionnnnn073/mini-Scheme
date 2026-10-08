"""环境：变量绑定表 + 指向外层环境的指针（词法作用域的关键，spec §9）。

一个 Environment 就是 {名字: 值} 加上一个 parent；查名字先查自己、再沿
parent 链上溯到全局环境。这正是 lambda 能"看见定义处变量"的原因，
也是 define 的函数体能查到自身名字（递归）的原因。

本语言没有 set!（spec §10），所以只提供查询与定义两个操作。

公开接口：
    Environment(parent=None)   一层作用域（省略 parent 就是全局环境）
    lookup(name)               沿 parent 链查名字，找不到抛 SchemeNameError
    define(name, value)        在当前（最内层）环境绑定名字

名字在环境内部统一用纯字符串当键，外部既可以传 Symbol 也可以传 str，
这样内置过程库可以直接用 `"+"` 这样的字面量来安装。
"""
from __future__ import annotations

from .datatypes import Symbol
from .errors import SchemeNameError


class Environment:
    """一层作用域：{名字: 值} 的映射，加上指向外层作用域的 parent。"""

    __slots__ = ("bindings", "parent")

    def __init__(self, parent: "Environment | None" = None) -> None:
        self.bindings: dict = {}
        self.parent: "Environment | None" = parent

    def define(self, name: object, value: object) -> None:
        """在当前（最内层）环境里把 name 绑定到 value（spec §4.5 define）。"""
        self.bindings[_name_text(name)] = value

    def lookup(self, name: object) -> object:
        """沿 parent 链查 name 的值；查不到抛 SchemeNameError（spec §9）。"""
        text = _name_text(name)
        env: "Environment | None" = self
        while env is not None:
            if text in env.bindings:
                return env.bindings[text]
            env = env.parent
        raise SchemeNameError(f"未绑定的名字：{text}")

    def __repr__(self) -> str:
        depth = 0
        env: "Environment | None" = self
        while env is not None:
            depth += 1
            env = env.parent
        return f"<Environment 层内绑定 {len(self.bindings)} 个，作用域深度 {depth}>"


def _name_text(name: object) -> str:
    """把 Symbol 或字符串统一成环境里的键；其它类型说明调用方用错了名字。"""
    if isinstance(name, Symbol):
        return name.name
    if isinstance(name, str):
        return name
    raise SchemeNameError(f"非法的名字：{name!r}")
