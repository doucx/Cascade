这一阶段出现了大量的 `NameError: name 'Param' is not defined`，这表明在核心代码（极有可能是 `src/cascade/graph/build.py`）中，虽然我移除了 `Param` 的导入，但代码中仍然存在对 `Param` 的引用（可能是类型注解或其他未清理的逻辑）。由于 `build_graph` 是几乎所有测试的必经之路，这解释了为何几乎所有测试都失败了。

我将读取相关文件来诊断问题，并检查 `test_sql.py` 和 `test_cli.py` 的具体失败原因。

按照 D3 协议，D1 是唯一事实来源，我不能虚构内容。

Plan:
1.  读取 `src/cascade/graph/build.py`，确认是否残留 `Param` 引用。
2.  读取 `src/cascade/graph/serialize.py`，确认其状态。
3.  读取 `src/cascade/spec/common.py`，确认 `Param` 类是否存在。
4.  基于读取结果修复 `NameError`。
5.  读取 `tests/providers/test_sql.py` 和 `tests/tools/test_cli.py`，修复断言错误。

~~~~~act
read_file
src/cascade/graph/build.py
~~~~~
~~~~~act
read_file
src/cascade/graph/serialize.py
~~~~~
~~~~~act
read_file
src/cascade/spec/common.py
~~~~~
~~~~~act
read_file
tests/tools/test_cli.py
~~~~~
