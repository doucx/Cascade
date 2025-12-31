好的，我们来处理 `cascade-graph` 包。这个包的测试主要集中在图的构建、哈希、序列化和编译逻辑上。

经过分析，绝大多数测试（如 `test_build.py`, `test_hashing.py`, `test_serialize.py`）只依赖于 `build_graph` 或序列化工具，验证的是纯粹的图变换逻辑，属于**单元测试**。而 `test_static_integrity.py` 启动了完整的 `Engine` 并在 `asyncio` 环境下运行，验证的是运行时的约束检查，属于**集成测试**。

## [WIP] refactor(tests): 为 cascade-graph 分离单元测试与集成测试

### 用户需求

在 `cascade-graph` 包内，将现有的测试文件按照“单元测试”和“集成测试”的逻辑进行重新组织。

### 评论

`cascade-graph` 是系统的核心逻辑组件。将其复杂的图构建和编译器测试归类为单元测试，可以确保在不启动重量级运行时（如消息总线、执行器）的情况下，依然能快速验证图结构的正确性。

### 目标

1.  在 `packages/cascade-graph/tests/` 目录下创建 `unit/` 和 `integration/` 目录。
2.  **迁移至 Integration**:
    *   `test_static_integrity.py`: 因为它使用了 `Engine.run()` 来验证运行时对非法图结构的拦截。
3.  **迁移至 Unit**:
    *   `test_build.py`: 验证 `build_graph` 的拓扑结构生成。
    *   `test_compiler.py`: 验证从图到蓝图（Blueprint）的编译转换。
    *   `test_execution_mode.py`: 验证节点元数据的提取。
    *   `test_hashing.py`: 验证图结构的哈希指纹逻辑。
    *   `test_purity_model.py`: 验证纯函数任务的去重逻辑。
    *   `test_serialize.py`: 验证图的 JSON 序列化与反序列化。

### 基本原理

*   **单元测试分类准则**: 凡是仅通过输入 `LazyResult` 并断言生成的 `Graph` 或 `Blueprint` 对象的测试，均视为单元测试。
*   **集成测试分类准则**: 凡是需要实例化 `Engine`、`Solver` 或涉及 `await engine.run()` 的测试，均视为集成测试。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建测试子目录

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-graph/tests/unit packages/cascade-graph/tests/integration
~~~~~

#### Acts 2: 迁移集成测试

将涉及运行时行为的测试移动到 `integration`。

~~~~~act
move_file
packages/cascade-graph/tests/test_static_integrity.py
packages/cascade-graph/tests/integration/test_static_integrity.py
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_static_integrity.stitcher.yaml
packages/cascade-graph/tests/integration/test_static_integrity.stitcher.yaml
~~~~~

#### Acts 3: 迁移单元测试

将所有纯逻辑验证的测试移动到 `unit`。

~~~~~act
move_file
packages/cascade-graph/tests/test_build.py
packages/cascade-graph/tests/unit/test_build.py
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_build.stitcher.yaml
packages/cascade-graph/tests/unit/test_build.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_compiler.py
packages/cascade-graph/tests/unit/test_compiler.py
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_compiler.stitcher.yaml
packages/cascade-graph/tests/unit/test_compiler.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_execution_mode.py
packages/cascade-graph/tests/unit/test_execution_mode.py
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_execution_mode.stitcher.yaml
packages/cascade-graph/tests/unit/test_execution_mode.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_hashing.py
packages/cascade-graph/tests/unit/test_hashing.py
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_hashing.stitcher.yaml
packages/cascade-graph/tests/unit/test_hashing.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_purity_model.py
packages/cascade-graph/tests/unit/test_purity_model.py
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_purity_model.stitcher.yaml
packages/cascade-graph/tests/unit/test_purity_model.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_serialize.py
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~
~~~~~act
move_file
packages/cascade-graph/tests/test_serialize.stitcher.yaml
packages/cascade-graph/tests/unit/test_serialize.stitcher.yaml
~~~~~

### 下一步建议

`cascade-graph` 的测试已经整理完毕。

现在我们只剩下最后一个包含复杂测试的包了：`cascade-engine`。该包的测试非常多且重要，因为它包含了各种适配器（Cache, State）、执行策略和并发控制的验证。我将接着为您分析并整理 `cascade-engine`。
