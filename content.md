船长，这是重构后的一个小尾巴。

由于我们将 `ProviderRegistry` 和相关类（包括 `ProviderNamespace`）移到了 `cascade.providers.registry` 模块中，而 `cascade.providers` 现在只是一个纯粹的命名空间包（为了支持插件），它不再直接包含这些类的定义。

尽管我们在 `__init__.py` 中重新导出了一些核心对象，但我确实漏掉了 `ProviderNamespace`，而且从架构整洁的角度来看，测试代码直接从定义它的地方导入这个内部类会更稳健。

我们来快速修复这个测试文件的导入路径。

## [WIP] fix(tests): 修正 test_io.py 中 ProviderNamespace 的导入路径

### 用户需求
`tests/cascade-py/providers/test_io.py` 失败，因为它试图从 `cascade.providers` 导入 `ProviderNamespace`，但该类已在架构重构中移动到了 `cascade.providers.registry`。

### 评论
这是架构重构的常见后续效应。当我们将实现细节从 `__init__.py` 移出以支持命名空间包时，依赖于旧路径的测试代码需要同步更新。直接从 `registry` 子模块导入明确了依赖关系，也符合新的代码组织结构。

### 目标
1.  修改 `tests/cascade-py/providers/test_io.py`，将 `ProviderNamespace` 的导入源指向正确的 `cascade.providers.registry`。

### 基本原理
`cascade.providers` 现在是一个纯命名空间，用于挂载各种插件。核心的注册表逻辑和辅助类（如 `ProviderNamespace`）物理上位于 `cascade.providers.registry` 模块中。更新导入路径以反映这一物理事实。

### 标签
#intent/fix #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正测试导入

~~~~~act
patch_file
tests/cascade-py/providers/test_io.py
~~~~~
~~~~~python
    # If not installed, we can manually register for this unit test.

    from cascade.providers import registry, ProviderNamespace
    from cascade.providers.io import ReadTextProvider

    # Manual registration to ensure test isolation
~~~~~
~~~~~python
    # If not installed, we can manually register for this unit test.

    from cascade.providers.registry import registry, ProviderNamespace
    from cascade.providers.io import ReadTextProvider

    # Manual registration to ensure test isolation
~~~~~

### 下一步建议
这应该修复了最后一个 `ImportError`。

请执行：
1.  `pytest`

现在，所有测试（包括 IPFS、S3、IO 以及所有核心逻辑）应该都能通过了。一旦看到全绿，我们就可以自信地提交了。
