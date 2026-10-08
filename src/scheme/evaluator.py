"""求值器（心脏）：表达式 → 值。

两个互相递归的函数（README §4）：
    evaluate(expr, env)  基本值原样返回；Symbol 查环境；括号表达式先看是否特殊
                         形式（spec §4），否则求值操作符与全部实参后交给 apply
    apply(proc, args)    内置过程直接调用；闭包则新建一层环境，把实参绑到参数名上
                         （外层指向函数定义时的环境），再回到 evaluate 求值函数体

分阶段实现（本文件相关部分均已完成）：
    Phase 2  骨架 + 算术/比较/布尔内置过程（已完成）
    Phase 3  特殊形式 quote / if / cond / and / or / begin（已完成）
    Phase 4  define / lambda / 闭包（已完成）
    Phase 5  let（并行绑定）（已完成）
    Phase 6~8  列表 / 输出 / 谓词由 builtins/lists|io|predicates.py 安装（已完成）
"""
from __future__ import annotations

from .builtins import install_builtins
from .datatypes import Closure, DottedList, PrimitiveProcedure, Symbol, is_truthy, to_data
from .environment import Environment
from .errors import SchemeArityError, SchemeSyntaxError, SchemeTypeError
from .printer import to_write


def make_global_env() -> Environment:
    """建立初始环境：把 spec §5 的全部内置过程装进去。"""
    env = Environment()
    install_builtins(env)
    return env


def evaluate(expr: object, env: Environment) -> object:
    """求值一个表达式并返回它的值（None 表示"无值"，顶层不打印，spec §2）。

    规则（spec §9）：符号去环境里查；括号表达式交给 _evaluate_form；
    数字 / 浮点 / 布尔 / 字符串都是自求值的基本值，原样返回。
    """
    if isinstance(expr, Symbol):
        return env.lookup(expr)
    if isinstance(expr, (list, DottedList)):
        return _evaluate_form(expr, env)
    return expr


def apply(proc: object, args: "list") -> object:
    """调用一个过程（README §4）：内置过程直接执行实现，闭包则绑参数后求值函数体。"""
    if isinstance(proc, PrimitiveProcedure):
        _check_arity(proc, len(args))
        return proc.impl(args)
    if isinstance(proc, Closure):
        frame = _bind_arguments(proc, args)
        return _eval_sequence(proc.body, frame)  # 函数体按 begin 语义，返回最后一个的值
    raise SchemeTypeError(f"不是可调用的过程：{to_write(proc)}")


def _bind_arguments(closure: Closure, args: "list") -> Environment:
    """为一次闭包调用新建一层环境：绑定实参，外层指向**定义时**的环境（spec §4.6/§9）。"""
    if len(args) != len(closure.params):
        raise SchemeArityError(
            f"{closure.name}：参数个数不符（收到 {len(args)} 个，要求 {len(closure.params)} 个）"
        )
    frame = Environment(closure.env)
    for param, value in zip(closure.params, args):
        frame.define(param, value)
    return frame


def _evaluate_form(expr: object, env: Environment) -> object:
    """求值一个括号表达式：先看特殊形式，否则按应用序求值操作符与全部实参（spec §1/§9）。"""
    if isinstance(expr, DottedList):
        raise SchemeSyntaxError("点对写法不能作为表达式求值")
    if not expr:  # `()` 只是数据，不是合法的函数调用
        raise SchemeSyntaxError("空表 () 不能作为表达式求值")
    head = expr[0]
    if isinstance(head, Symbol) and head.name in SPECIAL_FORMS:
        return SPECIAL_FORMS[head.name](expr, env)
    proc = evaluate(head, env)  # 操作符也要求值：它可以来自变量（spec §9）
    args = [evaluate(item, env) for item in expr[1:]]  # 应用序：实参先算完
    return apply(proc, args)


def _check_arity(proc: PrimitiveProcedure, count: int) -> None:
    """参数个数校验：内置过程自己声明 min_args / max_args（spec §5）。"""
    too_few = count < proc.min_args
    too_many = proc.max_args is not None and count > proc.max_args
    if too_few or too_many:
        raise SchemeArityError(
            f"{proc.name}：参数个数不符（收到 {count} 个，要求 {_arity_text(proc)}）"
        )


def _arity_text(proc: PrimitiveProcedure) -> str:
    """把参数个数要求写成给人看的文本（只用于错误信息）。"""
    if proc.max_args is None:
        return f"至少 {proc.min_args} 个"
    if proc.min_args == proc.max_args:
        return f"{proc.min_args} 个"
    return f"{proc.min_args}~{proc.max_args} 个"


# ---------------------------------------------------------------------------
# 特殊形式（spec §4）
#
# 处理函数的统一签名是 (expr, env)，expr 是完整的括号表达式（含表头的名字）。
# 它们各自决定求值顺序，这正是特殊形式与普通函数调用的区别：
# quote 不求值、if/cond 只走一个分支、and/or 会短路、begin 顺序执行。
# define / lambda / let 均已实现（Phase 4/5 完成，分派见文件末尾的 SPECIAL_FORMS）。
# ---------------------------------------------------------------------------

# cond 里 else 关键字的标记：与任何表达式都不相同，用身份（is）判断（spec §4.3）。
_ELSE = object()


def _eval_sequence(expressions: "list", env: Environment) -> object:
    """按 begin 语义从左到右依次求值，返回最后一个的值；空序列返回 None（spec §4.8）。"""
    result: object = None
    for item in expressions:
        result = evaluate(item, env)
    return result


def _special_quote(expr: "list", env: Environment) -> object:
    """`(quote 数据)` / `'数据`：原样交出数据，不求值（spec §4.1）。

    读入期的结构（Python list / DottedList）先经 to_data 变成与 cons 一致的
    运行时表示（点对链），这样 `'(1 2 3)` 与 `(list 1 2 3)` 结果同形（spec §6）。
    """
    if len(expr) != 2:
        raise SchemeSyntaxError("quote：写法必须是 (quote 数据)")
    return to_data(expr[1])


def _special_if(expr: "list", env: Environment) -> object:
    """`(if 测试 真分支 假分支?)`：先求测试，只走其中一个分支（spec §4.2）。"""
    if len(expr) not in (3, 4):
        raise SchemeSyntaxError("if：写法必须是 (if 测试 真分支 假分支?)")
    if is_truthy(evaluate(expr[1], env)):
        return evaluate(expr[2], env)
    if len(expr) == 4:
        return evaluate(expr[3], env)
    return None  # 省略假分支且测试为假 → 无值，顶层不打印（spec §2）


def _cond_clause(clause: object) -> "tuple":
    """把一个 cond 子句拆成 (测试表达式 或 _ELSE, 体表达式列表)（spec §4.3）。"""
    if not isinstance(clause, list) or not clause:
        raise SchemeSyntaxError("cond：每个子句必须是非空表 (测试 表达式...)")
    test = clause[0]
    if isinstance(test, Symbol) and test.name == "else":
        return _ELSE, clause[1:]
    return test, clause[1:]


def _special_cond(expr: "list", env: Environment) -> object:
    """`(cond 子句...)`：从上到下找第一个为真的子句（spec §4.3）。

    命中后按 begin 语义求值子句体并返回最后一个；子句没有体就返回测试值本身；
    全部不匹配返回 None。
    """
    for clause in expr[1:]:
        test, body = _cond_clause(clause)
        if test is _ELSE:
            return _eval_sequence(body, env) if body else True
        value = evaluate(test, env)
        if is_truthy(value):
            return _eval_sequence(body, env) if body else value
    return None  # 全部不匹配 → 无值


def _special_and(expr: "list", env: Environment) -> object:
    """`(and e1 e2 ...)`：短路求值；遇假立刻返回它，全真返回最后一个（spec §4.4）。"""
    result: object = True  # (and) → #t
    for item in expr[1:]:
        result = evaluate(item, env)
        if not is_truthy(result):
            return result  # 后面的表达式根本不会执行
    return result


def _special_or(expr: "list", env: Environment) -> object:
    """`(or e1 e2 ...)`：短路求值；遇真立刻返回它，全假返回 #f（spec §4.4）。"""
    for item in expr[1:]:
        result = evaluate(item, env)
        if is_truthy(result):
            return result  # 后面的表达式根本不会执行
    return False  # (or) → #f、全部为假 → #f


def _special_begin(expr: "list", env: Environment) -> object:
    """`(begin e1 e2 ...)`：从左到右依次求值，返回最后一个的值（spec §4.8）。"""
    return _eval_sequence(expr[1:], env)


def _parse_params(params_expr: object) -> "list":
    """把参数表写法变成参数名列表；不合法的写法当场报错（spec §4.6/§10）。"""
    if isinstance(params_expr, DottedList):
        raise SchemeSyntaxError("lambda：不支持可变参数 (参数 . 其余)（spec §10）")
    if not isinstance(params_expr, list):
        raise SchemeSyntaxError("lambda：参数表必须写成 (参数...)")
    params: "list" = []
    seen = set()
    for item in params_expr:
        if not isinstance(item, Symbol):
            raise SchemeSyntaxError("lambda：参数名必须是符号")
        if item.name in seen:  # 重名会导致绑定互相覆盖，属于写法错误
            raise SchemeSyntaxError(f"lambda：参数名重复：{item.name}")
        seen.add(item.name)
        params.append(item)
    return params


def _make_closure(name: str, params_expr: object, body: "list", env: Environment) -> Closure:
    """造一个闭包：只记住参数名、函数体和**定义时**的环境，函数体此时不求值（spec §4.6）。"""
    return Closure(_parse_params(params_expr), list(body), env, name)


def _special_lambda(expr: "list", env: Environment) -> object:
    """`(lambda (参数...) 体...)`：产出一个记住定义处环境的闭包（spec §4.6）。"""
    if len(expr) < 3:
        raise SchemeSyntaxError("lambda：写法必须是 (lambda (参数...) 体...)")
    return _make_closure("lambda", expr[1], expr[2:], env)


def _special_define(expr: "list", env: Environment) -> object:
    """`(define 名 值)` / `(define (函数名 参数...) 体...)`：绑定并返回符号名（spec §4.5）。

    先求值右边的表达式，再在当前环境绑定；函数简写等价于
    `(define 函数名 (lambda (参数...) 体...))`。返回的符号名会被顶层打印出来。
    """
    if len(expr) < 3:
        raise SchemeSyntaxError(
            "define：写法必须是 (define 名字 值) 或 (define (名字 参数...) 体...)"
        )
    target = expr[1]
    if isinstance(target, Symbol):  # (define 名字 值)
        if len(expr) != 3:
            raise SchemeSyntaxError("define：变量定义只能带一个值表达式")
        value = evaluate(expr[2], env)
        if isinstance(value, Closure) and value.name == "lambda":
            value.name = target.name  # 只影响错误信息：让 (define f (lambda ...)) 报错时报 f
        env.define(target, value)
        return target
    if isinstance(target, list):  # (define (名字 参数...) 体...)：定义函数的简写
        if not target or not isinstance(target[0], Symbol):
            raise SchemeSyntaxError("define：函数简写的表头必须形如 (名字 参数...)")
        name = target[0]
        value = _make_closure(name.name, target[1:], expr[2:], env)
        env.define(name, value)
        return name
    raise SchemeSyntaxError("define：第一个操作数必须是名字或 (名字 参数...)")


def _parse_bindings(bindings_expr: object) -> "list":
    """把 let 的绑定串变成 [(名字, 表达式)]；写法不对当场报错（spec §4.7）。

    允许同一个名字出现多次（spec 没有禁止，验收用例里就有这种写法）：绑定按书写顺序
    依次写入新这一层环境，所以后写的覆盖先写的。绑定表达式仍全部在外层环境求值。
    """
    if not isinstance(bindings_expr, list):  # 含 (let (x 1) ...) 与点对写法
        raise SchemeSyntaxError("let：绑定串必须写成 ((名字 表达式)...)")
    bindings: "list" = []
    for clause in bindings_expr:
        if not isinstance(clause, list) or len(clause) != 2:
            raise SchemeSyntaxError("let：每个绑定必须写成 (名字 表达式)")
        name = clause[0]
        if not isinstance(name, Symbol):
            raise SchemeSyntaxError("let：绑定的名字必须是符号")
        bindings.append((name, clause[1]))
    return bindings


def _special_let(expr: "list", env: Environment) -> object:
    """`(let ((名 表达式)...) 体...)`：并行绑定后在**新环境**里求值体（spec §4.7）。

    求值顺序是关键：先把所有绑定表达式在**外层**环境里求值完（绑定之间互不可见，
    所以 `(let ((x 1) (y x)) ...)` 里的 x 取的是外层的值），再新建一层环境同时绑定，
    最后按 begin 语义求值函数体。绑定串里出现同名时，后写的覆盖先写的（见 _parse_bindings）。
    """
    if len(expr) < 3:
        raise SchemeSyntaxError("let：写法必须是 (let ((名字 表达式)...) 体...)")
    bindings = _parse_bindings(expr[1])
    values = [(name, evaluate(value_expr, env)) for name, value_expr in bindings]
    frame = Environment(env)  # 新一层作用域：里面的绑定不会影响外层（spec §9）
    for name, value in values:
        frame.define(name, value)
    return _eval_sequence(expr[2:], frame)


# 特殊形式分派表：名字 → 处理函数(expr, env)（spec §4）。
# _evaluate_form 先查这张表再当函数调用处理，所以特殊形式不会被同名变量遮蔽。
SPECIAL_FORMS: dict = {
    "quote": _special_quote,
    "if": _special_if,
    "cond": _special_cond,
    "and": _special_and,
    "or": _special_or,
    "begin": _special_begin,
    "define": _special_define,
    "lambda": _special_lambda,
    "let": _special_let,
}
