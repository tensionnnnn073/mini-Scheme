"""入口 src/main.py 的错误约定（spec §2/§11）：结果走 stdout，错误走 stderr。

- 用户程序错误（SchemeError 族）→ stderr 一行，退出码 1，stdout 保持干净；
- 解释器自身撑满 Python 栈（极端递归）→ 同样只写 stderr，不让 traceback 冒泡；
- 多个 .scm 文件共享同一个全局环境（spec §2）。

运行（仓库根目录）：python -m unittest discover -s tests -v
"""
import contextlib
import io as io_stream
import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import main  # noqa: E402


class EntryPointTests(unittest.TestCase):
    """把源码写进临时 .scm 文件，按 CLI 的方式运行入口。"""

    def run_cli(self, *sources):
        """返回 (退出码, stdout, stderr)，其中输出流用 StringIO 抓取。"""
        out, err = io_stream.StringIO(), io_stream.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for index, source in enumerate(sources):
                path = os.path.join(tmp, f"program{index}.scm")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(source)
                paths.append(path)
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = main.main(paths)
        return code, out.getvalue(), err.getvalue()

    def test_results_are_printed_one_per_line_on_stdout(self):
        code, out, err = self.run_cli("(+ 1 2)\n(display 3)\n(newline)\n(* 2 3)")
        self.assertEqual(code, 0)
        self.assertEqual(out, "3\n3\n6\n")  # 顶层结果各占一行；display 不产生额外行
        self.assertEqual(err, "")

    def test_user_error_goes_to_stderr_with_exit_code_1(self):
        code, out, err = self.run_cli("(+ 1 2)\n(car '())")
        self.assertEqual(code, 1)
        self.assertEqual(out, "3\n")  # 出错之前的结果照常打印
        self.assertTrue(err.startswith("error: "))
        self.assertIn("car", err)

    def test_deep_recursion_reports_an_error_instead_of_a_python_traceback(self):
        code, out, err = self.run_cli("(define (loop n) (+ 1 (loop (+ n 1))))\n(loop 0)")
        self.assertEqual(code, 1)
        self.assertEqual(out, "loop\n")
        self.assertTrue(err.startswith("error: "))
        self.assertNotIn("Traceback", err)

    def test_files_share_one_global_environment(self):
        code, out, err = self.run_cli("(define x 41)", "(+ x 1)")
        self.assertEqual((code, out, err), (0, "x\n42\n", ""))


if __name__ == "__main__":
    unittest.main()
