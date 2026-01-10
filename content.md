好的，整个 Cascade VM 的核心执行策略构建和环境适配已经完成。我们成功解决了 Egress 死锁、`*args` 编译错误，并实现了灵活的后端切换机制。

我将生成一个 `[COMMIT]` 计划，将这些涵盖编译器、运行时和 VM 层的关键变更作为一个完整的逻辑单元提交。

## [COMMIT] feat: 实现 VMExecutionStrategy 并整合环境变量驱动的后端切换

### 用户需求
完成 Cascade VM 实施路线图的关键步骤：构建 `VMExecutionStrategy` 及其配套设施。要求支持通过 `CASCADE_BACKEND` 环境变量在传统图执行器与 VM 物理执行器之间进行切换，并修复在 VM 模式下发现的 Egress 节点逻辑错误及 `*args` 处理异常。

### 评论
这是 Cascade 3.0 演进中的一个里程碑。通过将 VM 策略正式引入 `cascade-runtime` 并提供环境配置支持，我们不仅打通了物理执行路径，还通过 Egress 缓冲和参数绑定优化确保了生产级的稳定性。这为后续大规模使用物理引擎执行复杂工作流奠定了坚实基础。

### 目标
1.  **策略整合**：使 `Engine` 具备感知环境并自动加载 `VMExecutionStrategy` 的能力。
2.  **物理层修复**：纠正 Egress 节点的二分图语义（Data -> Func），消除执行死锁。
3.  **编译器增强**：修复 `Expander` 和 `WiringPolicy` 对 `VAR_POSITIONAL` (`*args`) 参数的错误处理。
4.  **基础设施**：实现 `BridgedComputeService` 以连接 VM 的计算请求与 Runtime 的本地执行器。
5.  **质量保证**：增加 `CodeRegistry` 和 `Engine` 策略选择的单元测试。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/compiler #comp/vm #concept/executor #scope/core #scope/dx #ai/delegate #task/domain/runtime #task/object/vm-integration #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将所有涉及编译器修复、运行时适配和 VM 核心增强的文件添加到暂存区，并创建一个内容详尽的提交记录。

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/control.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
packages/cascade-compiler/src/cascade/compiler/frontend/__init__.py
packages/cascade-runtime/src/cascade/runtime/host/instance.py
packages/cascade-runtime/tests/unit/host/test_engine_init.py
packages/cascade-spec/src/cascade/spec/runtime/strategies.py
packages/cascade-vm/src/cascade/vm/compute/__init__.py
packages/cascade-vm/src/cascade/vm/compute/adapters.py
packages/cascade-vm/src/cascade/vm/registry.py
packages/cascade-vm/tests/unit/test_registry.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm): implement VMExecutionStrategy and environment-driven backend switching

This commit completes a major roadmap item for the Cascade VM integration:

1.  **Execution Strategy**: Integrated `VMExecutionStrategy` into the core `Engine`. The runtime now supports switching between 'graph' (legacy) and 'vm' (physics-based) backends via the `CASCADE_BACKEND` environment variable.
2.  **Egress Architecture Fix**: Resolved a deadlock where Egress nodes were incorrectly expanded as DataNodes. They are now correctly implemented as a (DataNode Buffer -> FuncNode Actor) pair, ensuring results are actively pushed to the system queue.
3.  **Variadic Arguments Support**: Fixed a compiler bug in `Expander` and `ParameterWiringPolicy` that caused `TypeError` when handling `*args`. Positional inputs are now correctly mapped to indexed ports instead of a placeholder 'args' port.
4.  **Bridged Compute Service**: Implemented `BridgedComputeService` to allow the VM to delegate task execution back to the Runtime's `LocalExecutor`, enabling full support for thread pooling and constraints in VM mode.
5.  **Infrastructure & Testing**: 
    - Added collision detection/warnings to `CodeRegistry`.
    - Added unit tests for `CodeRegistry` and `Engine` initialization logic.
    - Updated `ExecutionContext` and `Engine` to support a global `ObjectStore` injection.

This move marks the transition of the Physics Layer from an experimental feature to a fully integrated, selectable execution backend.
~~~~~

### 下一步建议
- **性能评估**：既然现在可以轻松切换后端，建议对复杂工作流进行性能对比测试，验证 VM 在调度开销方面的优势。
- **扩展资源支持**：目前的 VM 环境扫描较为简单，下一步可以增强 `VMExecutionStrategy` 对复杂硬件资源（如 GPU 分数）的感知与调度能力。
