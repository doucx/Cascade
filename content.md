## [WIP] fix: 修复依赖注入测试用例中的类型断言错误

### 错误分析
**`tests/test_di_and_resources.py` 失败**:
*   **现象**: `AssertionError: assert False where False = isinstance('mock_db_url', MagicMock)`
*   **原因**: 测试任务 `task_using_resource` 硬编码断言了注入对象必须是 `MagicMock` 类型，且代码逻辑访问了 `conn.url`。但在 `test_resource_override` 测试用例中，我们定义的 `mock_db_connection` 资源仅仅产出了一个字符串 `"mock_db_url"`。这不仅违反了类型断言，也会导致后续访问 `.url` 属性时出错。
*   **解决方案**: 修改测试用例中的 `mock_db_connection`，使其产出一个符合“契约”的对象（即一个带有 `url` 属性的 `MagicMock`），而不仅仅是一个字符串。

### 用户需求
修复测试用例逻辑，使所有测试通过。

### 评论
这是一个典型的测试逻辑错误：Mock 对象没有正确模拟真实对象的行为（接口）。修复它将验证 DI 系统能否正确地用 Mock 对象替换真实对象。

### 目标
1.  修改 `tests/test_di_and_resources.py` 中的 `mock_db_connection` 实现。

### 基本原理
依赖注入的核心优势之一就是可以用 Mock 对象替换真实依赖。但 Mock 对象必须遵循与真实对象相同的接口（鸭子类型）。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests
#concept/dependency-injection
#scope/core
#task/domain/core #task/object/test-case #task/action/fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修正测试用例中的 Mock 资源

我们将修改 `test_resource_override` 函数内部定义的 `mock_db_connection`，使其产出一个 `MagicMock` 对象，而不是字符串。

~~~~~act
patch_file
tests/test_di_and_resources.py
~~~~~
~~~~~python
    @cs.resource
    def mock_db_connection():
        print("SETUP: mock_db_connection")
        yield "mock_db_url"
        print("TEARDOWN: mock_db_connection")

    engine = cs.Engine()
~~~~~
~~~~~python
    @cs.resource
    def mock_db_connection():
        print("SETUP: mock_db_connection")
        m = MagicMock()
        m.url = "mock_db_url"
        yield m
        print("TEARDOWN: mock_db_connection")

    engine = cs.Engine()
~~~~~

### 下一步建议
运行 `pytest`。如果通过，我们将继续按计划增强可观测性，添加资源相关的事件。
