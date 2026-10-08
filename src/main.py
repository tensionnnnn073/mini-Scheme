#!/usr/bin/env python3
"""mini-Scheme 解释器入口（spec §2 的 CLI 约定）。

用法::

    python3 src/main.py file1.scm [file2.scm ...]   # 求值若干 .scm 文件
    python3 src/main.py                             # 无参数时从标准输入读取

职责：读源程序 → 交给解析器/求值器 → 每个结果独占一行打印；
出错只写 stderr，stdout 保持干净（评分器逐字节比对输出，spec §12）。

流水线由 scheme 包内职责单一的模块协作：
lexer → parser → evaluator（配合 environment / datatypes）→ printer，
内置过程由 builtins 装进初始环境。
"""
from __future__ import annotations

import argparse
import os
import sys

# 保证从任意工作目录调用都能导入 scheme 包（评分器可能在不同 cwd 下调用）。
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from scheme.errors import SchemeError  # noqa: E402  (必须在 sys.path 修正之后导入)
from scheme.evaluator import evaluate, make_global_env  # noqa: E402
from scheme.parser import parse  # noqa: E402
from scheme.printer import to_write  # noqa: E402

# Scheme 的一次调用会展开成数倍 Python 栈帧，默认上限 1000 容易误报 RecursionError；
# spec §10 不要求尾调用优化，这里用提高上限来兜底。
_RECURSION_LIMIT = 20000


def run_source(text: str, env: object) -> None:
    """按顺序求值一段程序里的每个顶层表达式，结果非 None 才独占一行打印（spec §2）。"""
    for expr in parse(text):
        value = evaluate(expr, env)
        if value is not None:
            print(to_write(value))


def main(argv: "list | None" = None) -> int:
    """解析命令行参数、读取源程序、逐个顶层表达式求值并打印；返回退出码。"""
    arg_parser = argparse.ArgumentParser(
        prog="mini-scheme",
        description="mini-Scheme 解释器：按顺序求值每个 .scm 文件中的顶层表达式。",
    )
    arg_parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="一个或多个 .scm 源文件；省略时从标准输入读取",
    )
    args = arg_parser.parse_args(sys.argv[1:] if argv is None else argv)

    sys.setrecursionlimit(max(sys.getrecursionlimit(), _RECURSION_LIMIT))

    try:
        env = make_global_env()  # 所有文件共享同一个全局环境（spec §2）
        if args.files:
            for path in args.files:
                with open(path, "r", encoding="utf-8") as handle:
                    run_source(handle.read(), env)
        else:
            run_source(sys.stdin.read(), env)
    except SchemeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except RecursionError:
        # spec §10 不要求尾调用优化：失控递归会撑满 Python 栈；这里和普通错误一样
        # 只写一行 stderr、退出码 1，不让原生 traceback 破坏 stderr 输出。
        print("error: 递归过深（超过解释器的递归上限）", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
