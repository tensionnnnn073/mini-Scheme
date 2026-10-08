"""错误类型族：所有用户可见的错误都统一成 SchemeError 的子类。

约定（spec §11）：
- 解释器内部不让 Python 原生异常（TypeError / ZeroDivisionError /
  RecursionError）直接冒泡，一律转译成这里的类型；
- 入口 src/main.py 只把这些错误写到 stderr，stdout 必须保持干净，
  否则会破坏评分器逐字节比对输出。

词法/语法/求值/内置过程都已在各自出错处抛出对应子类。
"""


class SchemeError(Exception):
    """mini-Scheme 错误的基类（用户程序里的错误）。"""


class SchemeSyntaxError(SchemeError):
    """词法/语法错误：括号不配对、字符串未闭合、非法字符等。"""


class SchemeNameError(SchemeError):
    """未绑定的名字：变量在环境里查不到（spec §9）。"""


class SchemeTypeError(SchemeError):
    """类型不符：例如把 #t 当数字、对非点对调用 car。"""


class SchemeArityError(SchemeError):
    """参数个数不符：内置过程或闭包收到的实参个数不对。"""
