简要回答：
非常好的战略判断。直接切换引擎（Flip the Switch）作为“并行测试”是验证新架构成熟度的最直接方式。

为了避免因显而易见的功能缺失导致测试全军覆没，我将在切换前补齐最后一块关键拼图：**可观测性 (Observability)**。旧引擎通过 `NodeProcessor` 发出丰富的生命周期事件（Started, Finished, Retry），目前的 VM 还是“哑巴”。如果不补齐这一点，所有依赖日志和事件断言的测试都会失败。

本计划将：
1.  实现 `ObservabilityMiddleware`，将事件发射逻辑下沉到 VM 管道中。
2.  在 `VMExecutionStrategy` 中装配此中间件。
3.  将 `Engine.run` 的默认策略切换为 `VM`。

这是“阶段三”真正的开始：让 VM 接管原本由 Engine 胶水代码负责的核心职责。

## [WIP] feat: Implement ObservabilityMiddleware and Flip the Switch

### 用户需求
1.  将 `cascade-engine` 的默认执行路径切换到基于 VM 的新架构。
2.  确保新架构能够发出与旧架构对齐的生命周期事件 (`TaskStarted`, `TaskFinished` 等)，以通过现有的集成测试。

### 评论
这是我们走向“新政权”的决定性时刻。如果不通过中间件实现可观测性，VM 就是一个无法调试的黑盒。通过 `ObservabilityMiddleware`，我们证明了管道架构不仅能处理计算，也能处理副作用和元数据，这是架构完备性的重要标志。

### 目标
1.  **实现 `ObservabilityMiddleware`**: 负责在指令执行前后发出标准的 Cascade 事件。
2.  **装配策略**: 在 `VMExecutionStrategy` 中注入 `MessageBus` 和 `run_id`，并配置新的中间件。
3.  **切换默认值**: 修改 `Engine.run`，默认启用 `use_vm=True`。

### 基本原理
*   **洋葱模型**: 可观测性中间件应置于管道的最外层（或接近最外层），以捕获包括重试、资源获取在内的完整耗时。
*   **上下文注入**: `run_id` 是运行时动态生成的，必须在每次 `execute` 调用时传递给中间件。

### 标签
#intent/build #flow/ready #priority/critical #comp/runtime #comp/vm #concept/middleware #scope/core #ai/instruct #task/domain/observability #task/object/middleware #task/action/switch

---

### Script

#### Acts 1: 实现 `ObservabilityMiddleware`

我们在 `cascade.vm.middleware.observability` 中实现此中间件。它需要依赖 `cascade.runtime.events` 中的事件定义。注意这里有一个跨包依赖（vm 依赖 runtime definition），这在 Monorepo 架构中通过接口解耦通常是可以接受的，或者我们使用 Protocol。鉴于 Event dataclass 是单纯的数据结构，直接引用是可以的。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/middleware/observability.py
~~~~~
~~~~~python
import time
from typing import Any
from cascade.vm.middleware import Middleware, ExecutionContext, NextHandler
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
)

class ObservabilityMiddleware(Middleware):
    def __init__(self, bus: MessageBus, run_id: str):
        self.bus = bus
        self.run_id = run_id

    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        instr = ctx.instruction
        # Only observe Call/MapCall instructions that represent tasks
        # Jumps are handled by VM loop and are invisible to users
        # Currently Middleware only wraps Call/MapCall dispatch
        
        task_id = getattr(instr, "structure_hash", "unknown")
        task_name = getattr(instr, "task_name", "unknown")

        self.bus.publish(
            TaskExecutionStarted(
                run_id=self.run_id,
                task_id=task_id,
                task_name=task_name
            )
        )

        start_time = time.time()
        status = "Succeeded"
        error_msg = None
        
        try:
            result = await next_handler()
            return result
        except Exception as e:
            status = "Failed"
            error_msg = str(e)
            raise e
        finally:
            duration = time.time() - start_time
            self.bus.publish(
                TaskExecutionFinished(
                    run_id=self.run_id,
                    task_id=task_id,
                    task_name=task_name,
                    status=status,
                    duration=duration,
                    error=error_msg
                )
            )
~~~~~

#### Acts 2: 更新 `VMExecutionStrategy` 进行装配

我们需要更新策略类，使其接收 `bus` 对象（之前不需要），并在构建管道时加入 `ObservabilityMiddleware`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
from cascade.runtime.constraints.manager import ConstraintManager

# New Compiler Stack
from cascade.compiler.frontend import Frontend
from cascade.compiler.optimizer import Optimizer
from cascade.compiler.backend import Backend
from cascade.vm import VirtualMachine
from cascade.vm.middleware.standard import (
    ArgumentResolutionMiddleware, 
    ConstraintMiddleware, 
    ResourceLifecycleMiddleware, 
    RetryMiddleware
)
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    async def execute(
~~~~~
~~~~~python.new
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.bus import MessageBus

# New Compiler Stack
from cascade.compiler.frontend import Frontend
from cascade.compiler.optimizer import Optimizer
from cascade.compiler.backend import Backend
from cascade.vm import VirtualMachine
from cascade.vm.middleware.standard import (
    ArgumentResolutionMiddleware, 
    ConstraintMiddleware, 
    ResourceLifecycleMiddleware, 
    RetryMiddleware
)
from cascade.vm.middleware.observability import ObservabilityMiddleware
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
        bus: MessageBus,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event
        self.bus = bus

    async def execute(
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # Configure Middleware Pipeline (Order matters!)
        # Order: Retry (Outer) -> Constraints -> Resources -> Resolution -> Core execution (Inner)
        vm.set_middlewares([
            RetryMiddleware(),
            ConstraintMiddleware(self.constraint_manager),
            ResourceLifecycleMiddleware(self.resource_manager),
            ArgumentResolutionMiddleware(active_resources, params),
        ])
~~~~~
~~~~~python.new
        # Configure Middleware Pipeline (Order matters!)
        # Onion Layer:
        # 1. Observability (Outermost): Logs everything including retries? 
        #    Note: Does Observability log individual attempts? 
        #    If Retry is inner, Observability sees one "Task" execution which might take long.
        #    If Retry is outer, Observability sees each attempt as a "Task"? No, that's not right.
        #    Correct nesting:
        #    [Observability] -> [Retry] -> [Constraints] -> [Resources] -> [Resolve] -> [Core]
        #    This way, Observability records the *Total* time for the task (including retries).
        #    The RetryMiddleware itself should emit TaskRetrying events (TODO).
        
        vm.set_middlewares([
            ObservabilityMiddleware(self.bus, run_id),
            RetryMiddleware(),
            ConstraintMiddleware(self.constraint_manager),
            ResourceLifecycleMiddleware(self.resource_manager),
            ArgumentResolutionMiddleware(active_resources, params),
        ])
~~~~~

#### Acts 3: 更新 `Engine` 初始化以传递 `bus`

由于修改了 `VMExecutionStrategy` 的 `__init__` 签名，我们需要更新 `Engine` 对其的实例化调用。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
        self.vm_strategy = VMExecutionStrategy(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self._wakeup_event,
        )

        self._managed_subscribers = []
~~~~~
~~~~~python.new
        self.vm_strategy = VMExecutionStrategy(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self._wakeup_event,
            bus=self.bus,
        )

        self._managed_subscribers = []
~~~~~

#### Acts 4: Flip the Switch (默认启用 VM)

这是最后一步。我们将 `use_vm` 的默认值改为 `True`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
    async def run(
        self,
        target: Any,
        params: Optional[Dict[str, Any]] = None,
        use_vm: bool = False,
    ) -> Any:
~~~~~
~~~~~python.new
    async def run(
        self,
        target: Any,
        params: Optional[Dict[str, Any]] = None,
        use_vm: bool = True,
    ) -> Any:
~~~~~

### 下一步建议
现在，你可以运行整个测试套件了：
`pytest packages/cascade-engine/tests`

预期结果：
大部分基础功能测试应该通过。但可能会有一些失败，例如：
1.  **缓存 (Caching)**：我们还没有实现 CacheMiddleware，关于缓存命中的测试会失败。
2.  **重试事件 (Retry Events)**：目前的 RetryMiddleware 还没有发出 `TaskRetrying` 事件，相关测试会失败。
3.  **复杂流控制**：如果 Jump 指令处理有细微差异，可能会有边缘情况失败。

这些失败将直接指导我们下一步的中间件开发工作。
