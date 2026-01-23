简要回答
好的，我们已经完成了计算适配层 (BridgedComputeService) 的核心重构，解决了包括依赖注入失效、参数绑定冲突以及系统上下文缺失在内的多个关键架构问题。测试结果显示，失败用例已从 40 个减少至 35 个，且 `test_engine_inputs.py` 和 `test_signal_provider.py` 等关键路径已恢复正常。

## [COMMIT] refactor(vm): 修复计算适配层断裂 (Adapter Gap)

### 用户需求
修复 `BridgedComputeService` 无法正确处理 `Inject` 对象、`params_context` 系统参数以及复杂函数签名绑定的问题。

### 评论
这是一个重大的架构修复。通过打通 `ExecutionContext` 到 VM 适配层的链路，并引入基于 `inspect.Signature` 的智能绑定机制，我们使 VM 能够真正理解并注入 Cascade 的运行时资源。这解决了之前在 SQL 集成、信号处理和参数传递中出现的各类 `AttributeError` 和 `TypeError`。

### 目标
1.  **基础设施贯通**: 在 `ExecutionContext` 中引入 `resource_container`，并确保其从 `Engine` 传递至 `BridgedComputeService`。
2.  **智能参数绑定**: 实现完整的 Python 参数绑定状态机，支持 `POSITIONAL_ONLY`、`VAR_POSITIONAL` (*args) 和 `VAR_KEYWORD` (**kwargs)。
3.  **依赖注入支持**: 在适配层实现 `_resolve_resource` 逻辑，支持按需解析 `Inject` 声明并管理任务级资源的生命周期。
4.  **系统上下文感知**: 自动识别并注入 `params_context` 到任务函数中。

### 基本原理
修复的核心在于将适配层从“哑调用器”升级为“语义感知调用器”。它现在会预先分析目标函数的签名，根据参数名称、类型和位置，结合从 VM 传入的物理输入和从引擎持有的逻辑资源，计算出最终的调用参数。

### 标签
#intent/refine #flow/done #priority/high #comp/vm #comp/runtime #comp/spec #concept/di #scope/core #ai/brainstorm #task/domain/compute #task/object/adapter-gap #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有涉及基础设施贯通和适配层重构的修改提交到 Git。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/runtime/strategies.py
packages/cascade-vm/src/cascade/vm/compute/adapters.py
packages/cascade-runtime/src/cascade/runtime/host/instance.py
packages/cascade-runtime/src/cascade/runtime/strategies/vm.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(vm): bridge the "Adapter Gap" in BridgedComputeService

This commit fixes a critical disconnect between the VM's physics engine and the Python runtime's logical requirements (DI, params_context, complex signatures).

Key Changes:
- Extended ExecutionContext to carry the ResourceContainer.
- Injected the ResourceContainer from Engine through VMExecutionStrategy into BridgedComputeService.
- Implemented a robust `_bind_execution_arguments` using `inspect.Signature` that supports all Python parameter kinds including *args and **kwargs.
- Added automatic resolution of `Inject` objects and `params_context` within the adapter layer.
- Added ExitStack management to handle the lifecycle of task-scoped resources (e.g., ephemeral DB connections).

These changes fix 5 major integration test failures related to SQL execution, parameter injection, and signal handling.
~~~~~

### 下一步建议
- **修复变长参数冲突**: 当前 `test_format_provider_with_positional_args` 仍然失败并提示 `multiple values for argument 'template'`，这通常是因为编译器生成的 IR 将第一个位置参数同时标记为了索引 `"0"` 和名称 `"template"`。建议下一步调查 `IRGenerator` 在处理标准库 Helper 时的输入生成逻辑。
- **清理其他测试失败**: 剩下的 35 个失败中，有相当一部分与 `__pulse__` 端口缺失有关，这涉及到 `Builder` 的 `PulseExpansionPolicy` 逻辑，建议随后进行专项修复。
