好的，我们开始执行任务：分离集成测试和单元测试。

我将从 `cascade-spec` 包开始，按照您的要求创建 `unit` 和 `integration` 目录，并迁移现有的测试文件。

## [WIP] refactor(tests): 为 cascade-spec 分离单元与集成测试

### 用户需求

在 `cascade-spec` 包内，将测试文件根据其性质（单元测试或集成测试）分离到各自独立的目录中。

### 评论

这是一个非常标准的最佳实践。通过分离单元测试和集成测试，我们可以：
1.  **提高反馈速度**: 单元测试通常运行得更快，可以在开发过程中提供快速反馈。
2.  **提升CI效率**: 可以在CI流水线中分阶段运行测试，例如，只在单元测试通过后才触发更耗时的集成测试。
3.  **增强代码清晰度**: 测试的意图变得更加明确，维护者可以清楚地知道一个测试文件是在验证隔离的组件还是端到端的流程。

### 目标

1.  在 `packages/cascade-spec/tests/` 目录下创建 `unit/` 和 `integration/` 两个新目录。
2.  识别 `tests/spec/` 目录下的测试文件类型：
    *   依赖 `cascade.run()` 或 `Engine` 的测试（如 `test_resource.py`, `test_routing.py`）将被归类为**集成测试**。
    *   仅测试数据模型、装饰器或独立功能的测试（如 `test_ir_models.py`, `test_task.py`）将被归类为**单元测试**。
3.  将这些测试文件及其关联的 `.stitcher.yaml` 文件移动到对应的 `unit/` 或 `integration/` 目录中。
4.  删除空的 `packages/cascade-spec/tests/spec/` 目录。

### 基本原理

我将通过分析每个测试文件的内容来确定其分类。那些启动了完整 Cascade 运行时（`cs.run`）的测试显然是集成测试，因为它们涉及求解器、执行器和事件总线等多个组件的协作。而那些只实例化数据类或调用纯函数的测试则是单元测试。迁移将使用 `move_file` 操作完成，最后清理旧的目录结构。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建新的测试目录结构

首先，在 `packages/cascade-spec/tests/` 目录下创建 `unit` 和 `integration` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-spec/tests/unit packages/cascade-spec/tests/integration
~~~~~

#### Acts 2: 迁移单元测试

这些测试验证的是独立的组件或数据模型，不依赖于完整的运行时引擎。

~~~~~act
move_file
packages/cascade-spec/tests/spec/test_async.py
packages/cascade-spec/tests/unit/test_async.py
~~~~~
~~~~~act
move_file
packages/cascade-spec/tests/spec/test_constraint.py
packages/cascade-spec/tests/unit/test_constraint.py
~~~~~
~~~~~act
move_file
packages/cascade-spec/tests/spec/test_constraint.stitcher.yaml
packages/cascade-spec/tests/unit/test_constraint.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-spec/tests/spec/test_input_context.py
packages/cascade-spec/tests/unit/test_input_context.py
~~~~~
~~~~~act
move_file
packages/cascade-spec/tests/spec/test_input_context.stitcher.yaml
packages/cascade-spec/tests/unit/test_input_context.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-spec/tests/spec/test_ir_models.py
packages/cascade-spec/tests/unit/test_ir_models.py
~~~~~
~~~~~act
move_file
packages/cascade-spec/tests/spec/test_task.py
packages/cascade-spec/tests/unit/test_task.py
~~~~~

#### Acts 3: 迁移集成测试

这些测试依赖于 `cs.run()` 或 `cs.Engine`，验证的是多个组件协同工作的端到端行为。

~~~~~act
move_file
packages/cascade-spec/tests/spec/test_resource.py
packages/cascade-spec/tests/integration/test_resource.py
~~~~~
~~~~~act
move_file
packages/cascade-spec/tests/spec/test_resource.stitcher.yaml
packages/cascade-spec/tests/integration/test_resource.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-spec/tests/spec/test_routing.py
packages/cascade-spec/tests/integration/test_routing.py
~~~~~

#### Acts 4: 清理旧的目录

现在 `spec` 目录已经是空的了，我们可以安全地删除它。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-spec/tests/spec
~~~~~

### 下一步建议

`cascade-spec` 包的测试结构已经重构完毕。接下来，我将分析 `cascade-application` 包的 `tests` 目录，并应用同样的逻辑来分离其单元测试和集成测试。如果您同意，我将继续处理下一个包。
