"""环境模块的单元测试（Phase 2，spec §9）。

覆盖：同层绑定与查询、沿 parent 链上溯、内层遮蔽、内层不向外泄漏、
名字既能用 Symbol 也能用字符串、多层链、查不到时抛 SchemeNameError。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from scheme.datatypes import Symbol  # noqa: E402
from scheme.environment import Environment  # noqa: E402
from scheme.errors import SchemeNameError  # noqa: E402


class EnvironmentTests(unittest.TestCase):
    """Environment 的绑定与查找语义。"""

    def test_define_and_lookup_in_same_scope(self):
        env = Environment()
        env.define("x", 1)
        self.assertEqual(env.lookup("x"), 1)

    def test_define_same_name_twice_overwrites(self):
        env = Environment()
        env.define("x", 1)
        env.define("x", 2)
        self.assertEqual(env.lookup("x"), 2)

    def test_name_may_be_symbol_or_string(self):
        env = Environment()
        env.define(Symbol("x"), 1)
        self.assertEqual(env.lookup(Symbol("x")), 1)
        self.assertEqual(env.lookup("x"), 1)

    def test_lookup_walks_up_to_parent(self):
        outer = Environment()
        outer.define("x", 1)
        inner = Environment(outer)
        self.assertEqual(inner.lookup("x"), 1)

    def test_inner_binding_shadows_outer(self):
        outer = Environment()
        outer.define("x", "outer")
        inner = Environment(outer)
        inner.define("x", "inner")
        self.assertEqual(inner.lookup("x"), "inner")
        self.assertEqual(outer.lookup("x"), "outer")

    def test_inner_binding_does_not_leak_outward(self):
        outer = Environment()
        inner = Environment(outer)
        inner.define("y", 2)
        self.assertEqual(inner.lookup("y"), 2)
        with self.assertRaises(SchemeNameError):
            outer.lookup("y")

    def test_lookup_unknown_name_raises(self):
        env = Environment()
        with self.assertRaises(SchemeNameError):
            env.lookup("nope")

    def test_lookup_in_deep_chain(self):
        env = Environment()
        env.define("root", 1)
        for _ in range(10):
            env = Environment(env)
        self.assertEqual(env.lookup("root"), 1)

    def test_invalid_name_type_raises(self):
        env = Environment()
        with self.assertRaises(SchemeNameError):
            env.define(123, 1)


if __name__ == "__main__":
    unittest.main()
