"""mini-Scheme 解释器主体包（流水线见 README §2）::

    程序文本 --lexer--> 词 --parser--> 表达式 --evaluator--> 值 --printer--> 文本

模块地图：
    errors        错误类型族（统一 SchemeError，只为 stderr 服务）      spec §11
    lexer         程序文本 → 词（token）列表                            spec §3
    parser        词 → 表达式（嵌套数据结构）                            spec §3/§4/§6
    datatypes     运行时数据：符号 / 点对 / 空表 / 过程对象               spec §6/§8
    environment   变量绑定表 + 指向外层环境的指针（词法作用域）           spec §9
    printer       值 → 文本（write / display 两种形式）                  spec §8
    builtins      spec §5 的全部内置过程，装进初始环境
    evaluator     表达式 → 值（evaluate / apply 互相递归，心脏）

入口脚本是同级目录下的 src/main.py（评分器按该路径调用）。
"""

__all__ = [
    "errors",
    "lexer",
    "parser",
    "datatypes",
    "environment",
    "printer",
    "builtins",
    "evaluator",
]
