简要回答

收到。分析显示测试失败有两个原因：一是 `IRGenerator` 生成的位置参数键 `"0"` 与 `Bleacher` 期望的参数名 `"x"` 不匹配；二是测试代码直接将用户函数映射给 `Reactor`，导致签名不匹配。我将生成计划修复这两个问题。

## [WIP] fix(compiler & test): 修复 IR 参数映射及 E2E 测试适配器

### 错误分析
1.  **Bleacher KeyError**: `IRGenerator` 将位置参数转换为字符串索引（如 `"0"`），而 `Expander` 基于 `TaskDef` 创建的端口使用参数名（如 `"x"`）。导致 `Bleacher` 在运行时无法根据键 `"0"` 找到端口定义。
2.  **Worker Signature Mismatch**: E2E 测试直接将用户定义的 Python 函数（如 `def main(x):`) 注册到 `Reactor`。但 `Reactor` 期望的是物理层协议签名的函数 (`func(inputs, node)`)。

### 用户需求
1.  修改 `IRGenerator`，使其将位置参数正确映射为 `TaskDef` 中定义的参数名。
2.  修改 `test_e2e_vm_run.py`，引入一个 `GenericWorkerAdapter`，负责将物理层的 Token 输入解包传递给用户函数，并将结果打包回 Token。

### 评论
这次修复涉及编译器前端的核心逻辑修正和测试代码的完善。参数名映射的修正将确保 `NodeIR` 与物理层端口定义的一致性。测试适配器的引入则是模拟未来 `Executor` 或 `WorkerWrapper` 的职责，对于通过 E2E 测试至关重要。

### 目标
1.  更新 `cascade-compiler/frontend/generator.py`，实现位置参数到参数名的映射。
2.  更新 `cascade-vm/tests/integration/test_e2e_vm_run.py`，实现并使用函数适配器。

### 基本原理
*   **一致性**: 逻辑层 (`NodeIR.inputs`) 的键必须与物理层 (`BleachNode.input_ports`) 的键保持一致。
*   **协议适配**: 物理引擎 (`Reactor`) 不应直接感知用户函数的签名，中间必须有一层适配器（在真实系统中是 `Executor` 的职责，测试中需手动模拟）来处理 `Token` <-> `kwargs` 的转换。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #comp/tests #scope/core #ai/instruct #task/domain/compiler #task/object/ir-generator #task/action/bug-fix

---

### Script

#### Acts 1: 修复 IRGenerator 的参数映射逻辑

我们将修改 `IRGenerator`，使其利用 `TaskDef` 中的参数定义，将位置参数列表映射为键值对字典。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        # 4. Construct NodeIR
        # Flatten args and kwargs into a single 'inputs' dictionary
        inputs = {}
        for i, val in enumerate(transformed_args):
            inputs[str(i)] = val
        for k, val in transformed_kwargs.items():
            inputs[k] = val
~~~~~
~~~~~python.new
        # 4. Construct NodeIR
        # Flatten args and kwargs into a single 'inputs' dictionary
        inputs = {}
        for i, val in enumerate(transformed_args):
            # Map positional args to their names defined in TaskDef
            if i < len(task_def.args):
                arg_name = task_def.args[i].name
                inputs[arg_name] = val
            else:
                # Fallback for varargs or mismatches
                inputs[str(i)] = val

        for k, val in transformed_kwargs.items():
            inputs[k] = val
~~~~~

#### Acts 2: 修复 E2E 测试中的 Worker 适配器

我们需要在测试中定义一个适配器，并使用它来包装用户函数。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_e2e_vm_run.py
~~~~~
~~~~~python.old
    # Create the function map: map physical node IDs to actual callables
    user_tasks = {
        "setup_task": setup_task.func,
        "should_run_task": should_run_task.func,
        "main_task": main_task.func,
        "final_task": final_task.func,
    }
    
    function_map: Dict[str, Callable] = {}
    for node_ir in graph_ir.nodes:
        if node_ir.name in user_tasks:
            # Map the worker node to the user's Python function
            worker_id = f"{node_ir.id}.worker"
            function_map[worker_id] = user_tasks[node_ir.name]

    for node_id in physical_graph.nodes:
~~~~~
~~~~~python.new
    # Create the function map: map physical node IDs to actual callables
    from cascade.spec.physics import Token
    
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

    user_tasks = {
        "setup_task": setup_task.func,
        "should_run_task": should_run_task.func,
        "main_task": main_task.func,
        "final_task": final_task.func,
    }
    
    function_map: Dict[str, Callable] = {}
    for node_ir in graph_ir.nodes:
        if node_ir.name in user_tasks:
            # Map the worker node to the ADAPTED user function
            worker_id = f"{node_ir.id}.worker"
            user_func = user_tasks[node_ir.name]
            function_map[worker_id] = create_worker_adapter(user_func)

    for node_id in physical_graph.nodes:
~~~~~

### 下一步建议
应用这些修复后，请再次运行 `test_e2e_vm_run.py`。我有信心这两个修改能够解决当前的 `TimeoutError` 和 `KeyError`，使我们的全链路测试通过。
