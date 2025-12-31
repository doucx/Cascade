好的，我们现在开始处理 `cascade-engine` 包。

`cascade-engine` 是核心运行时的所在地，其测试非常丰富，涵盖了从底层的事件总线、虚拟机，到中间层的适配器（缓存、状态、求解器、执行器），再到最高层的引擎调度逻辑。

## [WIP] refactor(tests): 为 cascade-engine 分离单元与集成测试

### 用户需求

对 `cascade-engine` 包进行测试结构重构，将测试文件按照 **Unit (单元测试)** 和 **Integration (集成测试)** 进行归类整合。

### 评论

`cascade-engine` 的测试量较大。目前它们分散在 `adapters/` 和 `runtime/` 等功能目录下。
在重构过程中，我将遵循以下原则：
1.  **单元测试**: 验证组件的孤立逻辑。例如，`InMemoryCacheBackend` 的存取逻辑、`NativeSolver` 的静态求解逻辑、`VirtualMachine` 的指令执行逻辑等。这些测试不启动 `Engine.run()`。
2.  **集成测试**: 验证组件间的协作。任何依赖 `Engine.run()` 或 `cs.run()`，通过端到端流程来验证功能的测试（如重试策略、并发限制、控制流跳转）都归为集成测试。

为了保持目录整洁，我将扁平化原本嵌套在 `adapters/` 下的测试。

### 目标

1.  在 `packages/cascade-engine/tests/` 下创建 `unit/` 和 `integration/` 目录。
2.  **归类为 Unit (单元测试)**:
    *   缓存/状态适配器：`test_in_memory.py`, `test_redis_cache.py`, `test_in_memory_state.py`, `test_redis_state.py`。
    *   求解器/执行器：`test_native.py`, `test_csp.py`, `test_local.py`。
    *   运行时核心组件：`test_bus.py`, `test_flow_manager.py`, `test_vm.py`, `test_vm_integration.py`, `test_vm_mutual.py`。
3.  **归类为 Integration (集成测试)**:
    *   基于文件系统的缓存：`test_file_existence.py` (使用 `cs.run`)。
    *   引擎调度逻辑：`test_engine_core.py`, `test_control_flow.py`, `test_engine_concurrency.py`, `test_engine_constraints.py`, `test_explicit_control_flow.py`, `test_flow_primitives.py`, `test_input_execution.py`, `test_map.py`, `test_map_policies.py`, `test_map_reduce_integration.py`, `test_retry.py`, `test_router_pruning.py`。
    *   原有的 `integration/` 目录内容。
4.  保留 `conftest.py` 在 `tests/` 根目录，以便两个子目录共享 fixture。
5.  清理旧的 `adapters/` 和 `runtime/` 目录。

### 基本原理

通过分析测试代码：
*   如果测试直接操作类实例（如 `backend.set()`, `solver.resolve()`, `vm.execute()`）并使用简单的 `asyncio.run`，则为单元测试。
*   如果测试构建了一个完整的 `Engine` 实例或调用 `cs.run(workflow)`，则为集成测试。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-structure #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建目录结构

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-engine/tests/unit packages/cascade-engine/tests/integration
~~~~~

#### Acts 2: 迁移单元测试 (Unit Tests)

我们将适配器测试扁平化并重命名，以保持目录结构清晰。

~~~~~act
move_file
packages/cascade-engine/tests/adapters/cache/test_in_memory.py
packages/cascade-engine/tests/unit/test_cache_in_memory.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/cache/test_in_memory.stitcher.yaml
packages/cascade-engine/tests/unit/test_cache_in_memory.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/cache/test_redis_cache.py
packages/cascade-engine/tests/unit/test_cache_redis.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/cache/test_redis_cache.stitcher.yaml
packages/cascade-engine/tests/unit/test_cache_redis.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/executors/test_local.py
packages/cascade-engine/tests/unit/test_executor_local.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/executors/test_local.stitcher.yaml
packages/cascade-engine/tests/unit/test_executor_local.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/solvers/test_csp.py
packages/cascade-engine/tests/unit/test_solver_csp.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/solvers/test_csp.stitcher.yaml
packages/cascade-engine/tests/unit/test_solver_csp.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/solvers/test_native.py
packages/cascade-engine/tests/unit/test_solver_native.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/state/test_in_memory_state.py
packages/cascade-engine/tests/unit/test_state_in_memory.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/state/test_in_memory_state.stitcher.yaml
packages/cascade-engine/tests/unit/test_state_in_memory.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/state/test_redis_state.py
packages/cascade-engine/tests/unit/test_state_redis.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/state/test_redis_state.stitcher.yaml
packages/cascade-engine/tests/unit/test_state_redis.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_bus.py
packages/cascade-engine/tests/unit/test_bus.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_bus.stitcher.yaml
packages/cascade-engine/tests/unit/test_bus.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_flow_manager.py
packages/cascade-engine/tests/unit/test_flow_manager.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_flow_manager.stitcher.yaml
packages/cascade-engine/tests/unit/test_flow_manager.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_vm.py
packages/cascade-engine/tests/unit/test_vm.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_vm.stitcher.yaml
packages/cascade-engine/tests/unit/test_vm.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_vm_integration.py
packages/cascade-engine/tests/unit/test_vm_builder.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_vm_integration.stitcher.yaml
packages/cascade-engine/tests/unit/test_vm_builder.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_vm_mutual.py
packages/cascade-engine/tests/unit/test_vm_mutual.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_vm_mutual.stitcher.yaml
packages/cascade-engine/tests/unit/test_vm_mutual.stitcher.yaml
~~~~~

#### Acts 3: 迁移集成测试 (Integration Tests)

我们将所有涉及 `Engine` 运行的测试移动到 `integration` 目录，并统一前缀。

~~~~~act
move_file
packages/cascade-engine/tests/adapters/caching/test_file_existence.py
packages/cascade-engine/tests/integration/test_file_existence_cache.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/adapters/caching/test_file_existence.stitcher.yaml
packages/cascade-engine/tests/integration/test_file_existence_cache.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/integration/test_compiler_integration.py
packages/cascade-engine/tests/integration/test_compiler.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_control_flow.py
packages/cascade-engine/tests/integration/test_engine_control_flow.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_control_flow.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_control_flow.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_engine_concurrency.py
packages/cascade-engine/tests/integration/test_engine_concurrency.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_engine_concurrency.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_concurrency.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_engine_constraints.py
packages/cascade-engine/tests/integration/test_engine_constraints.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_engine_constraints.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_constraints.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_engine_core.py
packages/cascade-engine/tests/integration/test_engine_core.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_engine_core.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_core.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_explicit_control_flow.py
packages/cascade-engine/tests/integration/test_engine_explicit_control_flow.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_explicit_control_flow.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_explicit_control_flow.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_flow_primitives.py
packages/cascade-engine/tests/integration/test_engine_flow_primitives.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_input_execution.py
packages/cascade-engine/tests/integration/test_engine_inputs.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_input_execution.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_inputs.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_map.py
packages/cascade-engine/tests/integration/test_engine_map.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_map.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_map.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_map_policies.py
packages/cascade-engine/tests/integration/test_engine_map_policies.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_map_policies.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_map_policies.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_map_reduce_integration.py
packages/cascade-engine/tests/integration/test_engine_map_reduce.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_map_reduce_integration.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_map_reduce.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_retry.py
packages/cascade-engine/tests/integration/test_engine_retry.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_retry.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_retry.stitcher.yaml
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_router_pruning.py
packages/cascade-engine/tests/integration/test_engine_router_pruning.py
~~~~~
~~~~~act
move_file
packages/cascade-engine/tests/runtime/test_router_pruning.stitcher.yaml
packages/cascade-engine/tests/integration/test_engine_router_pruning.stitcher.yaml
~~~~~

#### Acts 4: 清理旧目录

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-engine/tests/adapters packages/cascade-engine/tests/runtime
~~~~~

### 下一步建议

`cascade-engine` 的测试迁移非常成功，现在测试结构已经非常清晰：`unit` 验证原子逻辑，`integration` 验证引擎调度逻辑。

下一个包是 `cascade-graph`。我注意到这个包目前的测试都在 `packages/cascade-graph/tests/` 根目录下。我将对其进行分析并继续执行迁移。
