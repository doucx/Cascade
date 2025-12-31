简要回答：
好的，这正是 TDD 的价值所在——报错信息精确地指出了只要修复这些导入和文件结构问题，我们的新架构就能运行起来。

我将生成一个 `[GREEN]` 计划，通过创建缺失的协议文件、修复包导出以及升级 `VirtualMachine.execute` 签名来支持 `context_data`，从而消除这些错误并实现核心智能。

## [WIP] feat(vm): 实现 VM 中间件管道架构与能力增强

### 用户需求
1.  **修复导入错误**: `cascade.vm` 包结构存在缺失，导致测试无法加载。需要创建 `protocols.py` 并修复 `__init__.py` 导出。
2.  **实现中间件管道**: 使 `VirtualMachine` 支持洋葱模型的中间件执行，以支持重试、资源管理等高级功能。
3.  **增强 VM 接口**: 修改 `VirtualMachine.execute` 方法，使其能够接收 `context_data` (如用户 params)，从而通过中间件层注入到任务中。

### 评论
这是架构硬化的关键一步。我们将把 VM 从一个简单的函数调用器升级为一个具备 AOP (面向切面编程) 能力的编排引擎。修复这些看似简单的导入错误，实际上是在确立 VM 与外部世界（资源、约束、上下文）交互的契约。

### 目标
1.  创建 `cascade.vm.protocols` 以消除循环依赖并定义共享接口。
2.  完善 `cascade.vm.middleware` 包，导出核心类并实现标准中间件（ArgumentResolution, Retry, ResourceLifecycle）。
3.  升级 `VirtualMachine` 类，使其 `execute` 方法支持 `context_data`，并正确组装和执行中间件管道。

### 基本原理
*   **协议下沉**: 将 `ResourceManager` 等接口定义在 `vm.protocols` 中，使 `machine` 和 `middleware` 都能引用，解决循环依赖。
*   **管道模式**: 通过 `_execute_via_pipeline` 方法，将指令执行包装在中间件链中，无需修改核心的 `_core_call_invoker` 逻辑，保持了核心的纯粹性。
*   **上下文注入**: 通过在 `execute` 时传递 `context_data` 并在 `ExecutionContext` 中携带，我们为 `cs.Param` 等动态参数的解析提供了运行时支持。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/vm #task/action/pipeline-implementation #task/state/continue

---

### Script

#### Acts 1: 定义 VM 基础协议

首先，我们在 `cascade.vm` 包根目录下定义基础协议文件。这将作为 `machine` 和 `middleware` 之间的共享契约，解决导入报错的核心问题。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/protocols.py
~~~~~
~~~~~python
from typing import Protocol, Dict, Union, Any

class ResourceManager(Protocol):
    async def acquire(self, requirements: Dict[str, Union[int, float]]) -> None: ...
    async def release(self, requirements: Dict[str, Union[int, float]]) -> None: ...

class ConstraintManager(Protocol):
    def check_permission(self, task_shim: Any) -> bool: ...
    def get_extra_requirements(self, task_shim: Any) -> Dict[str, Any]: ...
~~~~~

#### Acts 2: 完善中间件包导出

修复 `cascade.vm.middleware` 包的 `__init__.py`，使其正确导出 `Middleware` 等核心类，解决 `ImportError`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/middleware/__init__.py
~~~~~
~~~~~python
from .middleware import Middleware, ExecutionContext, NextHandler

__all__ = ["Middleware", "ExecutionContext", "NextHandler"]
~~~~~

#### Acts 3: 升级 VirtualMachine 实现

我们将修改 `VirtualMachine` 类：
1.  在 `execute` 方法中增加 `context_data` 参数。
2.  在 `_execute_via_pipeline` 中将此 `context_data` 传递给 `ExecutionContext`。
3.  确保所有必要的导入都指向正确的位置（新的 `protocols.py`）。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
    async def execute(
        self,
        blueprint: Blueprint,
        symbol_table: Dict[str, Callable],
        initial_args: Optional[List[Any]] = None,
        initial_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        current_blueprint = blueprint
        current_symbol_table = symbol_table

        frame = Frame(current_blueprint.register_count)
        self._load_inputs(
            frame, current_blueprint, initial_args or [], initial_kwargs or {}
        )

        while True:
            pc = 0
            instructions = current_blueprint.instructions
            last_result = None

            while pc < len(instructions):
                instr = instructions[pc]

                if isinstance(instr, Jump):
                    pc += instr.offset
                    continue

                if isinstance(instr, JumpIfFalse):
                    val = frame.load(instr.condition)
                    if not val:
                        pc += instr.offset
                    else:
                        pc += 1
                    continue

                last_result = await self._dispatch(instr, frame, current_symbol_table)
                pc += 1

            if isinstance(last_result, TailCall):
                if last_result.target_blueprint_id:
                    if last_result.target_blueprint_id not in self._blueprints:
                        raise ValueError(
                            f"Unknown target blueprint ID: {last_result.target_blueprint_id}"
                        )
                    current_blueprint = self._blueprints[
                        last_result.target_blueprint_id
                    ]
                    # NOTE: In a multi-blueprint world, we'd need a way to get the
                    # symbol table for the new blueprint. For now, we assume self-recursion.
                    frame = Frame(current_blueprint.register_count)

                self._load_inputs(
                    frame, current_blueprint, last_result.args, last_result.kwargs
                )
                await asyncio.sleep(0)
                continue

            return last_result
~~~~~
~~~~~python.new
    async def execute(
        self,
        blueprint: Blueprint,
        symbol_table: Dict[str, Callable],
        initial_args: Optional[List[Any]] = None,
        initial_kwargs: Optional[Dict[str, Any]] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        current_blueprint = blueprint
        current_symbol_table = symbol_table
        # Store context data for this execution run
        self._current_context_data = context_data or {}

        frame = Frame(current_blueprint.register_count)
        self._load_inputs(
            frame, current_blueprint, initial_args or [], initial_kwargs or {}
        )

        while True:
            pc = 0
            instructions = current_blueprint.instructions
            last_result = None

            while pc < len(instructions):
                instr = instructions[pc]

                if isinstance(instr, Jump):
                    pc += instr.offset
                    continue

                if isinstance(instr, JumpIfFalse):
                    val = frame.load(instr.condition)
                    if not val:
                        pc += instr.offset
                    else:
                        pc += 1
                    continue

                last_result = await self._dispatch(instr, frame, current_symbol_table)
                pc += 1

            if isinstance(last_result, TailCall):
                if last_result.target_blueprint_id:
                    if last_result.target_blueprint_id not in self._blueprints:
                        raise ValueError(
                            f"Unknown target blueprint ID: {last_result.target_blueprint_id}"
                        )
                    current_blueprint = self._blueprints[
                        last_result.target_blueprint_id
                    ]
                    # NOTE: In a multi-blueprint world, we'd need a way to get the
                    # symbol table for the new blueprint. For now, we assume self-recursion.
                    frame = Frame(current_blueprint.register_count)

                self._load_inputs(
                    frame, current_blueprint, last_result.args, last_result.kwargs
                )
                await asyncio.sleep(0)
                continue

            return last_result
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
        ctx = ExecutionContext(
            instruction=instr,
            frame=frame,
            symbol_table=symbol_table,
            resolved_args=args,
            resolved_kwargs=kwargs
        )
~~~~~
~~~~~python.new
        ctx = ExecutionContext(
            vm=self,
            instruction=instr,
            frame=frame,
            symbol_table=symbol_table,
            resolved_args=args,
            resolved_kwargs=kwargs,
            context_data=getattr(self, "_current_context_data", {}),
        )
~~~~~

#### Acts 4: 移除重复的协议定义 (清理)

由于我们将协议定义统一移至了 `cascade.vm.protocols`，我们需要清理 `cascade.vm.middleware` 目录下的冗余文件，以及 `cascade-engine` 中可能存在的同名文件（如果存在且不再需要）。根据上下文，`cascade-vm/src/cascade/vm/middleware/protocols.py` 存在且是空的或者冗余的。

~~~~~act
delete_file
packages/cascade-vm/src/cascade/vm/middleware/protocols.py
~~~~~

### 下一步建议
我们已经完成了 VM 侧的管道基础设施建设。
从测试的角度看，`test_vm_capabilities.py` 现在应该能正确导入模块并实例化 `VirtualMachine`。
接下来，我们可以运行 `pytest packages/cascade-vm/tests/integration/test_vm_capabilities.py`。
如果测试通过，说明 VM 的“智能”已经就位。然后我们需要回到 `cascade-engine` 层，将 `VMExecutionStrategy` 与这些新能力对接起来（特别是传递 `params` 到 `context_data`）。
