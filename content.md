啊，一个低级错误。感谢您的纠正。我过分专注于测试逻辑，却忽略了最基本的导入问题。

`NameError` 表明 `ShallowHasher` 没有被导入到测试文件中。我将立即修正这个问题。这仍然是在 TDD 的 "Red" 阶段，因为即使修复了导入，我们预期的 `AssertionError` 依旧会发生。

我将生成一个计划来添加正确的 `import` 语句。

## [WIP] fix(tests): Add missing import for ShallowHasher

### 用户需求
修复 `test_hashing.py` 中由于缺少 `ShallowHasher` 导入而导致的 `NameError`，以便让测试能够真正地因为我们预期的断言失败而失败。

### 评论
这是一个简单的修复，旨在纠正上一个计划中的疏漏。修复导入问题后，我们就能进入真正的“红色”阶段，即测试因为核心的哈希冲突逻辑而失败。

### 目标
1.  在 `tests/engine/graph/test_hashing.py` 文件顶部添加 `from cascade.graph.hashing import ShallowHasher`。

### 基本原理
测试用例 `test_hashing_distinguishes_nested_lazy_results` 引用了 `ShallowHasher` 类，但该类并未在该文件中导入，导致 Python 解释器无法找到其定义，从而抛出 `NameError`。添加正确的导入语句将解决此问题。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/tests
#ai/instruct
#task/domain/testing #task/object/hashing-bug #task/action/reproduction
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Add Missing Import

我们将为 `test_hashing.py` 添加 `ShallowHasher` 的导入语句。

~~~~~act
patch_file
tests/engine/graph/test_hashing.py
~~~~~
~~~~~python
from cascade import task
from cascade.graph.hashing import StructuralHasher


@task
~~~~~
~~~~~python
from cascade import task
from cascade.graph.hashing import StructuralHasher, ShallowHasher


@task
~~~~~

### 下一步建议
现在导入问题已经修复。请再次运行 `pytest tests/engine/graph/test_hashing.py`。

这一次，我们预期会看到测试因为 `AssertionError` 而失败，这将正式确认我们的诊断是正确的，并为下一步的修复工作铺平道路。
