好的，我们将继续迁移剩余的集成测试。

`test_resource_contention.py` 和 `test_source_node_execution.py` 是理想的迁移目标，因为它们都遵循了手动构建 `function_map` 的旧模式。

## [WIP] refactor(vm): 完成集成测试向 from_assembly 的迁移

### 用户需求
迁移 `test_resource_contention.py` 和 `test_source_node_execution.py`，使其使用 `EventDrivenRunner.from_assembly`，以消除手动构建 `func_map` 的冗余代码。

### 评论
此计划将完成对 VM 集成测试的重构。通过统一使用 `from_assembly` 工厂方法，我们确保了所有核心端到端测试都隐式地通过了 `Linker` 的完整性校验，从而提高了整个测试套件的可靠性和可维护性。

### 目标
1.  重构 `test_resource_contention.py` 以使用 `from_assembly`，并移除其手动 `function_map` 构建逻辑。
2.  重构 `test_source_node_execution.py` 以使用 `from_assembly`，同样移除其 `function_map` 构建逻辑。
3.  从这两个文件中移除不再需要的标准库 IC 导入。

### 基本原理
与上一步相同，我们的目标是利用 `EventDrivenRunner.from_assembly` 封装的链接和校验逻辑，来简化测试设置并增强其健壮性。这使得测试代码更专注于业务逻辑的验证，而不是底层的接线细节。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #concept/linking #scope/dx #ai/instruct #task/domain/vm #task/object/linker #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 重构 `test_resource_contention.py`

首先，移除 `test_resource_contention.py` 中不再需要的手动导入。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
from cascade.vm.registry import CodeRegistry

# Standard IC imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.spec.physical.object import Ref
~~~~~
~~~~~python.new
from cascade.vm.registry import CodeRegistry
from cascade.spec.physical.object import Ref
~~~~~

接下来，使用 `from_assembly` 替换手动的 `function_map` 构建和 `Runner` 实例化。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    # --- PART B: EXECUTION ASSERTION ---

    # Function Map and Debug Wrapper
    import functools

    print("\n--- Physical Field Event Log (Manual + Observed) ---")

    def debug_wrapper(func, name):
        import inspect

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapped(*args, **kwargs):
                print(f"[MAN-START] {name}")
                try:
                    result = await func(*args, **kwargs)
                    print(f"[MAN-END  ] {name}")
                    return result
                except Exception as e:
                    print(f"[MAN-ERROR] {name}: {e}")
                    raise

            return async_wrapped
        else:

            @functools.wraps(func)
            def sync_wrapped(*args, **kwargs):
                print(f"[MAN-START] {name}")
                try:
                    result = func(*args, **kwargs)
                    print(f"[MAN-END  ] {name}")
                    return result
                except Exception as e:
                    print(f"[MAN-ERROR] {name}: {e}")
                    raise

            return sync_wrapped

    func_map = {}
    for node_id, node in physical_graph.nodes.items():
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = mock_worker
        elif "allocator" in node_id:
            func_map[node_id] = debug_wrapper(discrete_allocator, node.name)
        elif "reclaimer" in node_id:
            func_map[node_id] = debug_wrapper(discrete_reclaimer, node.name)
        elif node_id.startswith("req."):
            func_map[node_id] = debug_wrapper(resource_requestor, node.name)
        elif "observability" in node_id:
            func_map[node_id] = standard_observer

    code_registry = CodeRegistry()
    runner = EventDrivenRunner(physical_graph, func_map, code_registry)
    runner.prime()

    await runner.start_loop()
~~~~~
~~~~~python.new
    # --- PART B: EXECUTION ASSERTION ---
    print("\n--- Physical Field Event Log (Observed) ---")

    code_registry = CodeRegistry()
    runner = EventDrivenRunner.from_assembly(assembly, code_registry)
    runner.prime()

    await runner.start_loop()
~~~~~

#### Acts 2: 重构 `test_source_node_execution.py`

同样，先移除 `test_source_node_execution.py` 中冗余的导入。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
from cascade.vm.registry import CodeRegistry
from cascade.runtime.services.observability.events import TaskExecutionFinished

# Standard library function imports
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher


@task
def source_task():
~~~~~
~~~~~python.new
from cascade.vm.registry import CodeRegistry
from cascade.runtime.services.observability.events import TaskExecutionFinished


@task
def source_task():
~~~~~

然后，用 `from_assembly` 替换其 `function_map` 构建逻辑。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
    worker_node_id = f"{node_ir.current_node_instance_hash}.worker"
    canonical_hash = assembly.symbol_table[worker_node_id]
    code_registry.register(canonical_hash, source_task.func)

    # 3. Build the function map for the Reactor
    func_map = {}
    for node_id, node in physical_graph.nodes.items():
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            # All user workers are now handled by the dispatcher
            func_map[node_id] = standard_dispatcher
        elif "observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Setup and run the VM using the new Harness
    runner = EventDrivenRunner(physical_graph, func_map, code_registry)
    runner.prime()

    # 5. Execute
    await runner.start_loop()
~~~~~
~~~~~python.new
    worker_node_id = f"{node_ir.current_node_instance_hash}.worker"
    canonical_hash = assembly.symbol_table[worker_node_id]
    code_registry.register(canonical_hash, source_task.func)

    # 3. Setup and run the VM using the new Harness
    runner = EventDrivenRunner.from_assembly(assembly, code_registry)
    runner.prime()

    # 4. Execute
    await runner.start_loop()
~~~~~

### 下一步建议
我们已经成功地将所有相关的集成测试迁移到了新的 `from_assembly` 模式，完成了这项重构任务。

根据我们的战略分析，下一个最关键的任务是**实现双通道出口 (Dual-Channel Egress)**，以解决错误 Token 掉入虚空导致系统意外静止的问题。这需要我们：
1.  确保 `Stainer` 能正确地将异常路由到 `output_error` 端口。
2.  增强 `ControlFlowWiringPolicy`，使其能为图的根节点同时连接 `output_default` 和 `output_error` 到不同的 `Egress` 节点。

如果你同意，我将开始制定实现这一目标的计划。
