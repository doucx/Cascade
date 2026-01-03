简要回答

收到。分析日志显示 `VM is idle after 4 steps` 且 `main_task` 已运行，但 `final_task` 未运行，导致 `result_event` 超时。这是因为 `standard_bleacher` 目前只处理数据端口 (`PortRole.DATA`) 和资源端口 (`PortRole.RESOURCE`)，而我们在 Phase 2 中引入了控制流端口 (`PortRole.SIGNAL`)（`wait_for_*` 和 `condition`）。`standard_bleacher` 忽略了这些信号端口的输入，导致它们未被“消耗”或未正确作为激发条件处理（尽管 Reactor 已消耗它们，但 Bleacher 内部逻辑可能未正确处理或 `Expander` 端口角色定义与 `Bleacher` 逻辑不匹配）。

## [WIP] fix(vm & test): 增强 Bleacher 以处理 SIGNAL 端口

### 错误分析
1.  **Bleacher 逻辑缺失**: `standard_bleacher` 目前的代码显式只处理 `DATA` 和 `RESOURCE` 类型的端口。它不知道如何处理 `SIGNAL` 类型的端口（`wait_for_...` 和 `condition`）。
2.  **VM 停滞**: 由于 `Reactor` 的 `step` 逻辑是基于“所有输入端口都有 Token”来激发的，`final_task` 的 Bleacher 因为其上游依赖（`main_task` 和 `setup_task`）的数据到达而激发。但如果 `Expander` 生成的端口包含 `SIGNAL` 类型，而 `standard_bleacher` 不处理它们，这实际上不会阻止激发（Reactor 负责检查 Token 存在），但 Bleacher 内部可能没有将这些信号正确纳入 Trace 或处理 Condition 逻辑。
3.  **Condition 逻辑缺失**: 更关键的是，如果 `condition` 端口收到 `False`，Bleacher 应该能够决定“跳过”后续的 Worker 执行。目前的 `standard_bleacher` 只是无脑地收集数据并调用 Worker。

**更正分析**: `standard_bleacher` 的代码显示它遍历 `inputs`。如果 `inputs` 中包含了 `SIGNAL` 端口的 Token，它目前会忽略它们（不放入 `worker_payload`），这本身是对的。但是，`final_task` 依赖于 `main_task` 的结果。`main_task` 运行了 (`Running main task with 10...`)。`setup_task` 应该也运行了。`final_task` 应该在第 5 步或之后运行。测试日志显示 `VM is idle after 4 steps`。这意味着 `final_task` 的 Bleacher 可能没有收集到所有需要的输入，或者 Reactor 认为它还没有准备好。

再仔细看 `main_task` 的配置：`run_if(condition_result).after(setup_result)`。
- `main_task` 运行了，说明 `condition` 和 `after` 机制在物理连接上是通的，且 Reactor 正确地等待了它们。
- 问题出在 `final_task`。它依赖 `main_result` 和 `setup_result`。
- `setup_task` 运行了吗？日志里没有 "Running setup..."。
- 等等，`main_task` 运行了，它依赖 `setup_task` (`.after(setup_result)`)。如果 `setup_task` 没运行，`main_task` 怎么可能运行？
- 啊，`setup_task` 是纯副作用（打印），它的返回值是 `"setup_complete"`。
- **关键线索**: 日志中只有 `Running main task with 10...`。没有 `Running setup...`，没有 `Deciding to run...`。
- 这不仅奇怪，简直是不可能的，除非 `main_task` 的 `.after(setup_result)` 没有生效，或者 `setup_task` 的 Worker 根本没被调用。
- **更可能的解释**: `Reactor` 的 `function_map` 映射有问题，或者 `standard_bleacher` 在处理某些输入组合时崩溃了（但这次没有 traceback，说明没有抛出异常）。

让我们回看 `test_e2e_vm_run.py` 的代码：
```python
    user_tasks = {
        "setup_task": setup_task.func,
        ...
    }
```
`setup_task.func` 是被装饰前的原始函数。
而在 `IRGenerator` 中：
```python
        # 4. Construct NodeIR
        inputs = {}
        # ... map args ...
```
对于 `setup_task`，它没有参数，所以 `inputs` 为空。
对于 `should_run_task`，也为空。

**假设**: `main_task` 能运行是因为它需要的常量 `10` 就位了。它对 `setup_task` 的 `.after` 依赖是通过 `SIGNAL` 端口实现的。如果 `standard_bleacher` 对 `SIGNAL` 端口的处理有问题（比如没有正确声明端口，导致 Reactor 认为不需要等待），那 `main_task` 就会提前运行。

不，`Builder` 明确添加了 `wait_for_...` 端口和通道。如果端口在 `Bleacher` 定义中存在，Reactor 就会等待。

**真正的原因**: `Reactor` 的 `_execute_task` 中：
```python
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node)
            else:
                result_tokens = await self.executor.submit(func, (input_data, node))
```
如果 `func` (即 `adapter`) 不是协程函数，它会被提交到线程池。我们的 `adapter` 是 `async def`，所以它是协程。

**Worker Adapter 的问题**:
```python
        def create_worker_adapter(user_func):
            async def adapter(inputs: Dict[str, Token], node):
                kwargs = inputs["worker_input"].payload
                # ...
```
`setup_task` 没有参数，`kwargs` 是 `{}`。`user_func(**kwargs)` 调用正确。

**日志捕获问题**: `pytest` 捕获 stdout。我们看到了 `Running main task...`。这证明 `main_task` 确实运行了。
为什么没看到 `Running setup...`？
可能是 `setup_task` 和 `should_run_task` 根本没运行？
如果它们没运行，`main_task` 的 `wait_for` 端口怎么会有数据？
除非... `Builder` 在连线时出错了，或者 `Expander` 没加上端口。

**回顾 `Expander`**:
```python
        # Add ports for implicit dependencies (SIGNAL)
        for dep_id in node_ir.dependencies:
            port_name = f"wait_for_{dep_id}"
            bleacher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Token")
```
这是基于 `node_ir.dependencies`。
前端 `generator.py`：
```python
        # Handle Explicit Dependencies (visit them)
        dependency_ids = []
        for dep in lr._dependencies:
            dependency_ids.append(self._visit(dep))
        # ...
        node_ir = NodeIR(..., dependencies=dependency_ids)
```
这看起来是对的。

**让我们看 `final_task`**:
`final_result_lr = final_task(main_result, setup_result)`
它依赖 `main_result` (Arg 0) 和 `setup_result` (Arg 1)。
这意味着 `final_task` 的 Bleacher 需要两个 DATA 输入。

如果 `main_task` 运行了，它会产生输出。
如果 `setup_task` 没运行，它不会产生输出。
`final_task` 等不到 `setup_result`，所以它永远不会运行。
这就是为什么 `final_task` 没运行。

**那为什么 `main_task` 运行了？**
它依赖 `setup_task` (`.after(setup_result)`)。
如果 `setup_task` 没运行，`main_task` 的 `wait_for` 端口应该拿不到 Token。
除非 `setup_task` 根本没有产生 Token，或者 `main_task` 根本没有等待它。

**惊人的发现**: 如果 `setup_task` 的 Bleacher 激发了，但 Worker 没运行（或者运行了但没产生结果），那后续的 Stainer 就不会激发。
但是日志显示 `VM is idle after 4 steps`。
Step 1: Constants & Resources filled.
Step 2: `setup_task` (no inputs), `should_run_task` (no inputs) should fire. `main_task` (waiting for signal) should NOT fire.
Step 3: `setup` & `should_run` finish. Stainer emits. `main_task` becomes ready.
Step 4: `main_task` fires.
Step 5: `main_task` finishes. Stainer emits.
Step 6: `final_task` becomes ready.

如果 `setup_task` 的 stdout 丢失了，那唯一的解释是它运行了但我们没看见？或者它被 Mock 了？
不，我们在测试里用的是真实函数。

**让我们聚焦于 `setup_task` 和 `should_run_task` 为什么可能被跳过。**
它们的 `inputs` 是空的。`Bleacher` 的输入端口也是空的。
Reactor `prime` 之后，它们就应该是 Ready 的。
它们在第一轮 `step` 就应该被激发。

**除非... 代码没有被正确 Patch**。
我刚才提交了 `fix(compiler & test): 修复 IR 参数映射及 E2E 测试适配器`。
请检查 `IRGenerator` 的 `inputs` 映射逻辑。
```python
        for i, val in enumerate(transformed_args):
            if i < len(task_def.args): # setup_task has 0 args. i=0 < 0 is False.
```
这看起来没问题。

**Debug 策略**:
与其猜测，不如增强 `standard_bleacher` 以支持 SIGNAL 端口，并在测试中增加更多断言或日志来定位问题。
而且，`standard_bleacher` 确实**必须**修改。即使目前的 Bug 不是由它直接引起的，如果不处理 `condition` 端口，后续的条件执行逻辑也是错的。
如果 `condition` 端口是 `False`，`standard_bleacher` 必须返回一个特殊的“Skip”信号或者不产生 `worker_input`。
但在物理层，Bleacher 必须产生输出给 Worker，否则 Worker 不会激发，流程就断了。
**v3.0 设计**: Bleacher -> Worker -> Stainer。
如果 Bleacher 决定跳过，它应该如何通知 Worker？
通常做法：Bleacher 发送一个特殊的 `ControlToken(SKIP)` 给 Worker，Worker 看到后直接透传给 Stainer，Stainer 看到后标记 Skip 并路由。
或者：VM 支持动态图，Bleacher 不产生输出，但这样 Stainer 永远不会被激发，下游永远等待。
**简化版**: Bleacher 检查 Condition。如果是 False，它抛出一个 `SkipError`？或者在 Payload 里标记？

目前我们先只解决 **SIGNAL 端口被忽略** 的问题。
`standard_bleacher` 应该把 `SIGNAL` 端口的 Trace 合并进来，这很重要。

**更重要的 Bug**: `test_e2e_vm_run` 中 `setup_task` 和 `should_run_task` 可能被 `Reactor` 认为是 Ready 的，被调度执行了，但是 **Adapter 出错了**。
`create_worker_adapter`：
```python
            async def adapter(inputs: Dict[str, Token], node):
                # Unpack kwargs from the worker_input token
                kwargs = inputs["worker_input"].payload
                # ...
```
对于 `setup_task`，`inputs["worker_input"].payload` 是 `{}`。`user_func(**{})` 是合法的。

**让我们看日志**: `ERROR cascade.vm.reactor:reactor.py:174 Error executing task ...: '0'`。
这是上一次失败的日志（KeyError '0'）。
最新的失败日志里 **没有 ERROR**。
只有 `VM is idle after 4 steps.` 和 stdout `Running main task with 10...`。

这意味着 `setup_task` **成功执行了**，只是没打印出来？
Pytest 的 stdout 捕获有时会很奇怪。
如果 `setup_task` 执行了，那它产生了结果。
那为什么 `final_task` 没执行？
`final_task` 依赖 `main_result` 和 `setup_result`。
`setup_result` 是 `setup_task` 的返回值。
`setup_task` 返回 `"setup_complete"`。

如果 `main_task` 运行了，那 `setup_task` 肯定完成了（因为有 `.after` 依赖）。
所以 `setup_task` 的输出应该在系统里。

问题可能出在 **数据流** 上。
`final_task` 需要 `setup_task` 的数据。
`setup_task` 的结果在 `Stainer` 后会发给 `final_task` 的 `Bleacher`。
`Builder` 连线：
```python
            for arg_name, source_ref in node_ir.inputs.items():
                if isinstance(source_ref, str) and source_ref in subgraphs:
                     # Wire Stainer -> Bleacher
```
这看起来是对的。

**最大的嫌疑**: `standard_stainer`。
它负责把 Worker 的结果发出去。
```python
    # 4.1 The main result
    outputs["output"] = Token(payload=result_payload, tag=tag, trace=trace_payload)
```
它把结果放在 `output` 端口。
`Builder` 把 `output` 连接到下游。

**让我们修改 `standard_bleacher`**。这至少能排除一个明显的逻辑缺失。
同时，我会在 `create_worker_adapter` 里加个 print，看看任务到底有没有被调度。

### 用户需求
1.  修改 `standard_bleacher` 以正确处理 `SIGNAL` 端口（合并 Trace）。
2.  修改 `standard_bleacher` 以支持 `condition` 逻辑：如果 `condition` 端口存在且 Payload 为 False，则注入一个特殊的 Skip 标记到 Worker Input 中（或者目前先只做 Trace 合并，确保不报错）。
3.  在测试中增加调试信息。

### 目标
修复 Bleacher 逻辑，并调试 E2E 测试。

### 基本原理
Bleacher 是三连体中的“感知”器官。它必须感知所有输入。忽略 SIGNAL 输入会导致 Trace 断裂，且无法实现条件逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/std #comp/tests #task/domain/vm #task/action/bug-fix

---

### Script

#### Acts 1: 增强 Standard Bleacher

修改 `standard_bleacher`，使其显式处理 `SIGNAL` 端口，并将 `condition` 的结果纳入考量（目前简化处理，暂不实现 Skip 逻辑，先保证流程通畅）。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        port_def = node.input_ports[port_name]

        if port_def.role == PortRole.DATA:
            worker_payload[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            # It's a resource. We record it to trace.
            held_resources.append(port_name)
        # Observability and Signals are processed for trace but not passed to worker

        trace_payload.update(input_token.trace)
~~~~~
~~~~~python.new
    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        port_def = node.input_ports[port_name]

        if port_def.role == PortRole.DATA:
            worker_payload[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            # It's a resource. We record it to trace.
            held_resources.append(port_name)
        elif port_def.role == PortRole.SIGNAL:
            # Signal (Condition or Wait). We record it to trace but don't pass payload to worker
            # TODO: Implement Condition logic (Skip if False)
            pass

        trace_payload.update(input_token.trace)
~~~~~

#### Acts 2: 在测试中增加调试日志

在 `create_worker_adapter` 中增加打印，以便在测试失败时确认哪些任务被执行了。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_e2e_vm_run.py
~~~~~
~~~~~python.old
    # Helper to adapt user functions to Physics Protocol
    def create_worker_adapter(user_func):
        async def adapter(inputs: Dict[str, Token], node):
            # Unpack kwargs from the worker_input token
            kwargs = inputs["worker_input"].payload
            
            # Call user function
            if asyncio.iscoroutinefunction(user_func):
                result = await user_func(**kwargs)
            else:
                result = user_func(**kwargs)
                
            return {"worker_result": Token(payload=result)}
        return adapter
~~~~~
~~~~~python.new
    # Helper to adapt user functions to Physics Protocol
    def create_worker_adapter(user_func):
        async def adapter(inputs: Dict[str, Token], node):
            # Unpack kwargs from the worker_input token
            kwargs = inputs["worker_input"].payload
            print(f"DEBUG: Executing {user_func.__name__} with {kwargs}")
            
            # Call user function
            if asyncio.iscoroutinefunction(user_func):
                result = await user_func(**kwargs)
            else:
                result = user_func(**kwargs)
            
            print(f"DEBUG: Finished {user_func.__name__} -> {result}")
            return {"worker_result": Token(payload=result)}
        return adapter
~~~~~

### 下一步建议
运行测试并观察输出。如果 `final_task` 仍然没有运行，请仔细检查 `setup_task` 的返回值是否正确传递给了 `final_task` 的 Bleacher。

注意：目前的 `standard_bleacher` 仍然没有实现真正的 Skip 逻辑。如果 `condition_result` 为 False，`main_task` 依然会运行。这在当前的测试用例中（`should_run_task` 返回 True）是可以接受的，但在生产环境中必须修复。我们将在 Phase 3 中完善这一点。
