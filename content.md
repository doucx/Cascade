Excellent, let's proceed with the `cascade-application` package.

Based on my analysis, the test file `test_app_tools.py` instantiates and uses the `CascadeApp` class. Since `CascadeApp` internally sets up an `Engine`, `Solver`, and `Executor`, these tests are verifying the integration of multiple components. Therefore, they qualify as integration tests.

I will now generate the plan to restructure the tests for this package.

## [WIP] refactor(tests): 为 cascade-application 分离测试

### 用户需求

在 `cascade-application` 包内，继续执行将测试文件分离到 `unit/` 和 `integration/` 目录的任务。

### 评论

`cascade-application` is the user-facing entry point, so its tests inherently lean towards integration. Creating the distinct directories now establishes a clear structure for future tests, ensuring that any new, isolated unit tests for helpers or internal logic will have a proper home.

### 目标

1.  在 `packages/cascade-application/tests/` 目录下创建 `unit/` 和 `integration/` 目录。
2.  将 `test_app_tools.py` 及其 `.stitcher.yaml` 文件归类为集成测试并移动到 `integration/` 目录。

### 基本原理

`test_app_tools.py` directly tests the `CascadeApp` class's `dry_run` functionality. This process involves graph building, plan resolution via a solver, and formatted output generation, making it a clear integration test. There are currently no unit tests in this package, but the directory structure will be created to accommodate them in the future.

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建新的测试目录结构

为 `cascade-application` 包创建 `unit` 和 `integration` 测试目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-application/tests/unit packages/cascade-application/tests/integration
~~~~~

#### Acts 2: 迁移集成测试文件

将 `test_app_tools.py` 和其 stitcher YAML 文件移动到 `integration` 目录中。

~~~~~act
move_file
packages/cascade-application/tests/test_app_tools.py
packages/cascade-application/tests/integration/test_app_tools.py
~~~~~
~~~~~act
move_file
packages/cascade-application/tests/test_app_tools.stitcher.yaml
packages/cascade-application/tests/integration/test_app_tools.stitcher.yaml
~~~~~

### 下一步建议

我们已经成功重构了 `cascade-application` 的测试目录。下一个包含测试的包是 `cascade-sdk`。我将分析其 `tests` 目录，并为您生成相应的迁移计划。
