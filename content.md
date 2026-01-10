[简要回答]
好的，我将执行两个关键修复：首先，在 `VMExecutionStrategy` 中引入对 `asyncio.Task` 的显式管理，以修复协程传递错误并防止任务泄漏；其次，增强 `Expander` 以根据 `NodeIR` 的实际输入动态生成物理端口，解决变长参数 (`*args`) 的连接问题。

## [WIP] fix: 修复 VM 策略的异步等待与 Expander 的变长参数映射

### 错误分析
1.  **VM 策略崩溃**: `VMExecutionStrategy._run_and_harvest` 中使用 `asyncio.wait([queue.get(), ...])` 触发了 Python 3.11+ 的 `TypeError`。这是因为 `wait` 不再接受隐式协程，必须显式包装为 `Task`。此外，简单的包装会导致在循环中产生悬挂的 `get()` 任务。
2.  **Wiring 失败**: 对于 `gather` 操作生成的 `NodeIR`（如 `inputs={'0': ref, '1': ref}`），编译器后端的 `Expander` 仅基于函数签名（`*args`）生成了名为 `args` 的端口，导致 `WiringHarness` 无法连接到名为 `0` 和 `1` 的端口。

### 用户需求
1.  **恢复 E2E 测试**: 使 `VMExecutionStrategy` 能够通过所有基础集成测试。
2.  **支持变长参数**: 确保 `Expander` 能正确处理 `list` 或 `gather` 产生的动态输入端口。

### 评论
这两个修复是正交的，但必须同时应用才能解除当前的阻塞状态。`VMStrategy` 的修复引入了更严谨的异步任务管理模式，这是一项长期有益的改进。

### 目标
1.  修改 `cascade-runtime/.../vm.py`，实现一个基于持久化 `egress_task` 的事件循环。
2.  修改 `cascade-compiler/.../expander.py`，使其扫描 `node_ir.inputs` 并为未定义的端口动态生成物理定义。

### 基本原理
1.  **Task复用**: 在 `_run_and_harvest` 循环中，如果 `egress_task` 未完成（例如是因为 `machine_task` 先结束了，或者只是 spurious wakeup），我们应该在下一次迭代中继续等待同一个任务，而不是创建一个新的。这避免了竞争和资源泄漏。
2.  **动态端口**: 物理层必须是逻辑层的全息投影。如果逻辑层（IR）说“我有输入 '0'”，物理层（Expander）就必须创建一个名为 '0' 的物理端口，无论函数签名如何定义。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #comp/compiler #concept/executor #concept/topology #task/domain/core #task/object/vm-strategy #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `VMExecutionStrategy` 的异步等待逻辑

我们将重构 `_run_and_harvest` 方法，使用一个持久的变量 `egress_task` 来管理队列读取任务，确保其生命周期被正确管理。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # Reverse map for quick lookup: Egress ID -> UUID
        egress_to_uuid = {v: k for k, v in target_map.items()}

        while pending_uuids:
            # Wait for either a result OR the machine stopping unexpectedly
            done, pending = await asyncio.wait(
                [harness.egress_queue.get(), machine_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            if machine_task in done:
                # Machine stopped before we got all results
                # Check if it raised an exception
                try:
                    machine_task.result()
                except Exception as e:
                    raise RuntimeError(f"Machine crashed during execution: {e}") from e
                
                # If machine finished cleanly but we are still waiting, it's a deadlock or logic error
                # OR, the task failed and didn't produce an output at the Egress.
                # (Failed tasks route to error ports, which might not be wired to Egress in this version)
                # TODO: Handle error propagation via Egress
                raise RuntimeError(
                    f"Machine stopped prematurely. Pending targets: {pending_uuids}"
                )

            # Handle Egress Result
            # We must drain all ready items from the queue
            if not harness.egress_queue.empty():
                # Note: We already consumed one item via `wait`, we need to retrieve it.
                # `asyncio.wait` with queue.get() doesn't return the item, it returns the coroutine object.
                # We need to await the coroutine to get the item.
                # But `done` contains the Task/Future.
                
                for task in done:
                    if task is machine_task: continue
                    
                    egress_id, token = await task
                    
                    if egress_id in egress_to_uuid:
                        uuid = egress_to_uuid[egress_id]
                        
                        # 3. Dereference Result
                        # The payload is a Ref.
                        val = token.payload
                        if isinstance(val, Ref):
                            val = context.object_store.get(val)
                        
                        # 4. Check for Error (Exception Propagation)
                        if isinstance(val, Exception):
                            raise val
                        
                        collected_results[uuid] = val
                        if uuid in pending_uuids:
                            pending_uuids.remove(uuid)
~~~~~
~~~~~python.new
        # Reverse map for quick lookup: Egress ID -> UUID
        egress_to_uuid = {v: k for k, v in target_map.items()}

        # Task management: We hold the egress reading task across loop iterations
        # if it hasn't completed yet.
        egress_task: Optional[asyncio.Task] = None

        try:
            while pending_uuids:
                if egress_task is None:
                    egress_task = asyncio.create_task(harness.egress_queue.get())

                # Wait for either a result OR the machine stopping
                done, pending = await asyncio.wait(
                    [egress_task, machine_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                if machine_task in done:
                    # Machine stopped before we got all results
                    try:
                        machine_task.result()
                    except Exception as e:
                        raise RuntimeError(f"Machine crashed during execution: {e}") from e
                    
                    raise RuntimeError(
                        f"Machine stopped prematurely. Pending targets: {pending_uuids}"
                    )

                if egress_task in done:
                    # We have a result token
                    egress_id, token = await egress_task
                    egress_task = None  # Reset for next iteration

                    if egress_id in egress_to_uuid:
                        uuid = egress_to_uuid[egress_id]
                        
                        # 3. Dereference Result
                        val = token.payload
                        if isinstance(val, Ref):
                            val = context.object_store.get(val)
                        
                        # 4. Check for Error (Exception Propagation)
                        if isinstance(val, Exception):
                            raise val
                        
                        collected_results[uuid] = val
                        if uuid in pending_uuids:
                            pending_uuids.remove(uuid)
        finally:
            # Cleanup: Cancel pending egress read if we are exiting (e.g. on error)
            if egress_task and not egress_task.done():
                egress_task.cancel()
                try:
                    await egress_task
                except asyncio.CancelledError:
                    pass
~~~~~

#### Acts 2: 增强 `Expander` 支持变长参数

修改 `Expander.expand_node`，在构建 `bleacher_inputs` 后，扫描 `node_ir.inputs`。对于任何尚未定义的端口（通常是数字键，代表变长参数），自动生成一个物理端口定义。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {
            arg.name: PortDef(arg.name, PortRole.DATA, "Any")
            for arg in node_ir.task.args
        }
        # Add ports for resources
        for res_name in node_ir.constraints.keys():
~~~~~
~~~~~python.new
        # F_pre: The Bleacher
        # Inputs = Task Args + Resource Constraints
        bleacher_inputs = {
            arg.name: PortDef(arg.name, PortRole.DATA, "Any")
            for arg in node_ir.task.args
        }

        # [HFEA Fix]: Variadic Args Support
        # Check for inputs in NodeIR that don't have a corresponding port definition.
        # This handles *args (which manifest as '0', '1', etc. in inputs) and other dynamic bindings.
        for input_key in node_ir.inputs.keys():
            if input_key not in bleacher_inputs:
                # Create a dynamic port definition for this input
                bleacher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")

        # Add ports for resources
        for res_name in node_ir.constraints.keys():
~~~~~

### 下一步建议

执行完上述计划后，请立即重新运行 `test_vm_e2e.py`。
如果测试通过，说明我们已经成功地建立了 `VMExecutionStrategy` 的最小可行版本。
接下来可以继续推进路线图中关于“复杂数据流测试”和“错误传播”的验证。
