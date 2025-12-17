简要回答
好的，我看到了测试失败。

### 错误分析
`FAILED tests/providers/test_io.py::test_provider_registry_namespace_resolution - AttributeError: 'Task' object has no attribute '__name__'.`

这个错误发生在 `test_provider_registry_namespace_resolution` 测试中。原因是 `@cs.task` 装饰器返回的是一个 `Task`类的实例，这个实例将任务的名称存储在 `.name` 属性中，而不是 Python 函数默认的 `.__name__` 属性。测试代码中的断言 `factory.__name__` 应该改为 `factory.name`。

这是一个测试用例本身的小错误，我将立即修复它。

## [WIP] fix(tests): 修正 Provider 注册表测试中的属性断言

### 用户需求
修复 `test_provider_registry_namespace_resolution` 测试，使其正确地从 `Task` 对象中获取名称。

### 评论
测试代码错误地使用了 `__name__` 来访问 `Task` 对象的名称，而正确的属性是 `.name`。

### 目标
1.  修改 `tests/providers/test_io.py` 中的断言。
2.  重新运行测试以确认修复。

### 基本原理
直接修改测试代码以匹配 `Task` 类的公共 API。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/provider-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复测试用例
将 `factory.__name__` 修正为 `factory.name`。

~~~~~act
patch_file
tests/providers/test_io.py
~~~~~
~~~~~python
    # Access "read.text" -> should return factory
    factory = ns.text
    assert factory.__name__ == "read_text" # Task name from @task
~~~~~
~~~~~python
    # Access "read.text" -> should return factory
    factory = ns.text
    assert factory.name == "read_text" # Task name from @task
~~~~~

### 下一步建议
测试通过后，我们将执行路线图的下一步：**废弃旧的 `cs.file` 并更新代码库**。这包括删除旧文件并全局替换引用。
