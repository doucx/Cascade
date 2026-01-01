你的观察非常敏锐。`test_compiler.py` 出现死锁的原因在于它是一个**过度 Mock 的“ वायरिंग”（布线）测试**，但在架构重构后，Mock 的边界与实际执行的代码脱节了：

1.  **Mock 路径过时**: 该测试试图 patch `cascade.vm.VirtualMachine.execute`。然而，在新的 `VMExecutionStrategy` 中，我们已经废弃了 `VirtualMachine` 类，转而使用 `Reactor`。
2.  **静默 Reactor 死锁**: 由于 `VirtualMachine.execute` 没被用到，`VMExecutionStrategy.execute` 会运行**真实**的逻辑。它调用了被 Mock 的 `Frontend` 和 `Backend`。由于 `Backend.compile` 被 Mock 返回了一个空的、无节点的拓扑，实体的 `Reactor` 启动后发现没有任何 `dirty_nodes` 可供执行，于是进入了无限期的 `await self._activity_signal.wait()` 状态。
3.  **Future 永不完成**: 由于 `Reactor` 没有任何节点可以触发 `Emitter` 逻辑，`VMExecutionStrategy` 中等待结果的 `result_future` 永远不会被 `set_result`，从而导致了外部的 `await asyncio.wait_for` 超时（在测试中由于没有设置整体超时，表现为死锁）。

我们将遵循 `d3-principle-python-testing-mock-intent` 原则，将 `test_compiler.py` 的职责定位为验证 `Engine` 是否正确地将任务委派给了新的 `VMExecutionStrategy`。既然 `VMExecutionStrategy` 本身的集成测试已经通过，我们在这里只需确保“布线”正确。

## [WIP] test(engine): 修复 test_compiler.py 中的死锁并对齐新策略

### 用户需求
修复 `test_compiler.py` 因过时的 Mock 路径导致的死锁问题。

### 评论
该测试的目的是验证 `Engine` 在 `use_vm=True` 时的集成逻辑。通过将 Mock 点上移到 `VMExecutionStrategy.execute`，我们可以清晰地验证 `Engine` 的路由决策，而不会陷入底层物理引擎的异步细节中。

### 目标
1.  更新 `test_compiler.py`，使用 `VMExecutionStrategy.execute` 作为 Mock 目标。
2.  移除不再使用的 `Optimizer` 相关的 Mock 逻辑（因为 `VMExecutionStrategy` 已经将其内化或简化）。
3.  验证 `Engine` 能够正确地将目标 workflow 传递给策略对象。

### 基本原理
当一个组件（`Engine`）将复杂的子任务委派给另一个策略对象（`VMExecutionStrategy`）时，集成测试应侧重于验证委派行为本身。底层的全链路逻辑应由策略对象的专用集成测试负责。

### 标签
#intent/tooling #flow/ready #priority/high #comp/engine #comp/tests #scope/dx #ai/refine #task/domain/testing #task/object/compiler-test #task/action/fix #task/state/end

---

### Script

#### Acts 1: 重构 `test_compiler.py` 以对齐新架构

我们将移除过时的 `VirtualMachine` 引用，改为对 `VMExecutionStrategy` 进行断言。

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_compiler.py
~~~~~
~~~~~python.old
    # 3. Patch the entire pipeline to verify wiring without running real logic
    # We want to ensure data flows: Frontend -> Optimizer -> Backend -> VM
    with patch("cascade.compiler.frontend.Frontend.compile") as mock_front, patch(
        "cascade.compiler.optimizer.Optimizer.optimize"
    ) as mock_opt, patch(
        "cascade.compiler.backend.Backend.compile"
    ) as mock_back, patch("cascade.vm.VirtualMachine.execute") as mock_vm_exec:
        # Setup Mocks
        mock_ir = MagicMock(spec=GraphIR)
        # Mock CompilationResult
        mock_comp_result = MagicMock()
        mock_comp_result.ir = mock_ir
        mock_comp_result.symbol_table = {}

        mock_front.return_value = mock_comp_result

        mock_plan = [["node_1"]]
        mock_opt.return_value = mock_plan

        mock_bp = MagicMock()
        mock_back.return_value = mock_bp

        mock_vm_exec.return_value = 11

        # 4. Act
        result = await engine.run(workflow, use_vm=True)

        # 5. Assert
        assert result == 11

        mock_front.assert_called_once_with(workflow)
        mock_opt.assert_called_once_with(mock_ir)
        mock_back.assert_called_once_with(mock_ir, mock_plan)
        mock_vm_exec.assert_called_once()
        # Verify VM received the blueprint
        assert mock_vm_exec.call_args[0][0] == mock_bp
~~~~~
~~~~~python.new
    # 3. Patch the VM Strategy to verify the Engine delegates correctly
    with patch(
        "cascade.runtime.strategies.vm.VMExecutionStrategy.execute"
    ) as mock_vm_exec:
        # Setup Mock behavior
        mock_vm_exec.return_value = 11

        # 4. Act
        result = await engine.run(workflow, use_vm=True)

        # 5. Assert: Verify the Engine routed the request to the VM strategy
        assert result == 11

        mock_vm_exec.assert_called_once()
        
        # Verify arguments passed to the strategy
        _, kwargs = mock_vm_exec.call_args
        assert kwargs["target"] == workflow
        assert kwargs["run_id"] is not None
        assert kwargs["params"] == {}
~~~~~

### 下一步建议
现在你可以安全地运行所有测试。这次修改确保了测试套件的健壮性，并且不再依赖已经消失的 `VirtualMachine` 类或内部的 `Optimizer` 逻辑。建议运行：
`pytest packages/cascade-engine/tests/integration/`
来验证整个 `Engine` 适配层是否工作正常。
