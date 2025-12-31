## [WIP] refactor(tests): 为 cascade-sdk 分离测试并整合目录

### 用户需求

对 `cascade-sdk` 包进行测试结构重构。将现有的分散在 `examples/`、`tools/` 和 `integration/` 目录下的测试文件，按照 **Unit (单元测试)** 和 **Integration (集成测试)** 的标准进行重新归类和整合。

### 评论

`cascade-sdk` 目前的测试结构是基于“功能模块”（如 `tools`, `examples`）而非“测试类型”划分的，这导致了混合的测试策略。
通过这次重构，我们将明确区分：
1.  **单元测试**: 仅验证逻辑转换、图形构建或纯函数行为（例如 Lisp 转译、Graphviz 可视化生成）。
2.  **集成测试**: 涉及运行时引擎启动、CLI 调用或端到端流程执行（例如 LLM 模式运行、CLI 命令执行）。

注意：`cascade-sdk/tests/integration` 目录已经存在，我们将保留并利用它。

### 目标

1.  在 `packages/cascade-sdk/tests/` 下创建 `unit/` 目录。
2.  **迁移至 Integration**:
    *   `examples/test_llm_pattern.py`: 涉及完整的子流程和引擎执行。
    *   `tools/test_cli.py`: 涉及 CLI 运行器和引擎调用。
3.  **迁移至 Unit**:
    *   `tools/test_lisp.py`: 纯粹的图结构到 Lisp 字符串的转译逻辑。
    *   `tools/test_visualize.py`: 纯粹的图结构到 DOT 字符串的转换逻辑。
4.  保留现有的 `integration/` 目录内容（`test_auto_gathering.py`, `test_state_backends.py` 等）。
5.  清理空的 `examples/` 和 `tools/` 目录。

### 基本原理

通过分析测试代码的依赖关系：
*   依赖 `cs.run()`, `cs.Engine`, `Typer.CliRunner` 的测试被归类为集成测试。
*   依赖 `build_graph()` 但只检查静态输出（字符串、结构）的测试被归类为单元测试。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 Unit 目录

`integration` 目录已存在，只需创建 `unit` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-sdk/tests/unit
~~~~~

#### Acts 2: 迁移集成测试

将 `examples` 和 `tools` 中涉及运行时执行的测试移动到 `integration` 目录。

~~~~~act
move_file
packages/cascade-sdk/tests/examples/test_llm_pattern.py
packages/cascade-sdk/tests/integration/test_llm_pattern.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/examples/test_llm_pattern.stitcher.yaml
packages/cascade-sdk/tests/integration/test_llm_pattern.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_cli.py
packages/cascade-sdk/tests/integration/test_cli.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_cli.stitcher.yaml
packages/cascade-sdk/tests/integration/test_cli.stitcher.yaml
~~~~~

#### Acts 3: 迁移单元测试

将 `tools` 中仅涉及逻辑转换和静态图分析的测试移动到 `unit` 目录。

~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_lisp.py
packages/cascade-sdk/tests/unit/test_lisp.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_lisp.stitcher.yaml
packages/cascade-sdk/tests/unit/test_lisp.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_visualize.py
packages/cascade-sdk/tests/unit/test_visualize.py
~~~~~
~~~~~act
move_file
packages/cascade-sdk/tests/tools/test_visualize.stitcher.yaml
packages/cascade-sdk/tests/unit/test_visualize.stitcher.yaml
~~~~~

#### Acts 4: 清理旧目录

删除不再需要的分类目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-sdk/tests/examples packages/cascade-sdk/tests/tools
~~~~~

### 下一步建议

`cascade-sdk` 的重构已完成。至此，主要的几个包 (`cascade-spec`, `cascade-application`, `cascade-sdk`) 的测试结构都已统一为 `unit/` 和 `integration/`。

建议您可以检查一下是否还有其他包需要类似的整理，或者运行测试以确保迁移没有破坏任何路径依赖。
