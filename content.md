分析正确。测试失败是因为我在上一步的重构中错误地移除了 `import aiohttp` 语句，而测试文件中的 Mock Server 实现依然依赖它。

`pytest.importorskip` 仅用于跳过测试，它并不会将模块导入到当前作用域。这是一个典型的错误，我将立即修正。

## [WIP] fix(tests): restore aiohttp import in http integration tests

### 错误分析
测试失败的根本原因是在 `packages/cascade-library/tests/integration/test_http.py` 文件中，我错误地删除了顶部的 `import aiohttp` 语句。

虽然我的意图是迁移核心库到 `httpx`，但我忽略了测试文件本身使用 `aiohttp.web.Application` 和 `pytest-aiohttp` 插件来创建一个模拟服务器。由于 `aiohttp` 没有被导入，导致在测试函数内部调用 `aiohttp.web.Application()` 时出现了 `NameError`。

### 用户需求
修复 `test_http.py` 中的 `NameError`，使测试能够成功运行。

### 评论
这是一个简单的修复，但它凸显了测试基础设施与被测代码分离的重要性。即使我们替换了核心库，测试工具链的依赖也必须得到满足。

### 目标
1.  在 `packages/cascade-library/tests/integration/test_http.py` 文件顶部重新添加 `import aiohttp` 语句。

### 基本原理
测试需要 `aiohttp` 来构建模拟服务器，因此必须在文件作用域内导入它。`pytest.importorskip` 仅是一个条件守卫，不能替代 `import` 语句。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #task/domain/testing #task/object/test-dependencies #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 恢复必要的 aiohttp 导入

我们将 `import aiohttp` 添加回测试文件中，以解决 `NameError`。

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_http.py
~~~~~
~~~~~python.old
import pytest
import cascade as cs
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.runtime.kernel.solvers.native import NativeSolver

# Mark all tests in this module to be skipped if dependencies are not installed
pytest.importorskip("aiohttp") # For the mock server fixture (aiohttp_client)
pytest.importorskip("httpx")   # For the code under test (cascade-library)
~~~~~
~~~~~python.new
import pytest
import cascade as cs
import aiohttp
from cascade.runtime.io.executors.local import LocalExecutor
from cascade.runtime.kernel.solvers.native import NativeSolver

# Mark all tests in this module to be skipped if dependencies are not installed
pytest.importorskip("aiohttp") # For the mock server fixture (aiohttp_client)
pytest.importorskip("httpx")   # For the code under test (cascade-library)
~~~~~

### 下一步建议
现在依赖关系已经正确，请再次运行测试。如果通过，我们可以认为 `httpx` 的迁移已初步完成，并可以进入提交阶段。
