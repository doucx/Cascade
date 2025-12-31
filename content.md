好的，我们继续处理 `cascade-library` 包。

分析 `cascade-library` 中的测试文件：
*   所有这些文件（`test_config.py`, `test_file.py`, `test_http.py` 等）都执行了 `cs.run()` 或显式创建了 `cs.Engine` 实例来运行 Provider 逻辑。
*   Provider 的本质是与外部系统（文件系统、网络、数据库、Shell）交互，因此验证它们的测试天然属于**集成测试**。
*   虽然 `test_io.py` 和 `test_sql.py` 中包含少量验证注册表逻辑或对象属性的单元测试，但其主体仍然是集成测试。

我将把它们统一迁移到 `integration/` 目录下，并创建空的 `unit/` 目录以备后用。

## [WIP] refactor(tests): 为 cascade-library 分离测试

### 用户需求

在 `cascade-library` 包内，将现有的 Provider 测试迁移到 `integration/` 目录，并建立标准的测试目录结构。

### 评论

`cascade-library` 包含了 Cascade 的标准库（Providers）。由于 Provider 的核心职责是执行实际的 I/O 操作或调用运行时引擎进行计算，这些测试几乎全部依赖于 `cascade-engine` 的完整流程。将它们归类为集成测试是非常准确的。

### 目标

1.  在 `packages/cascade-library/tests/` 目录下创建 `unit/` 和 `integration/` 目录。
2.  将所有现有的测试文件及其 `.stitcher.yaml` 配置文件移动到 `integration/` 目录。

### 基本原理

Provider 测试验证的是“任务定义”与“引擎执行器”之间的协作，以及与真实或模拟的外部资源（如 SQLite 内存库、Moto S3 模拟、aiohttp 模拟服务器）的交互。这种跨组件、跨边界的验证符合集成测试的定义。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建新的测试目录结构

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-library/tests/unit packages/cascade-library/tests/integration
~~~~~

#### Acts 2: 迁移所有测试文件到 Integration

我们将批量移动现有的测试文件。

~~~~~act
run_command
~~~~~
~~~~~bash
mv packages/cascade-library/tests/*.py packages/cascade-library/tests/integration/
mv packages/cascade-library/tests/*.stitcher.yaml packages/cascade-library/tests/integration/
~~~~~

### 下一步建议

`cascade-library` 的测试迁移已完成。

目前已重构的包包括：
- `cascade-spec`
- `cascade-application`
- `cascade-sdk`
- `cascade-library`

接下来的包是 **`cascade-engine`**。由于这个包是核心引擎，其测试可能包含大量的单元测试（验证求解器算法、事件总线逻辑等）和集成测试。我将对其进行深度分析。如果您准备好了，请指示我开始。
