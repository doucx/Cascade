简要回答：
我们将执行路线图的阶段 1，在 `cascade-vm` 中实现 `ResourceRegistry`，并重构 `Reactor` 及 `cascade-std` 中的所有核心物理原语函数，使其签名统一支持 `resources` 参数的注入，从而建立图与环境分离的物理基础。

## [WIP] refactor(vm): 实现 ResourceRegistry 并统一物理函数签名

### 用户需求
根据 "统一上下文与资源管理" 路线图的阶段 1，需要：
1.  在 `cascade-vm` 中定义 `ResourceRegistry` 用于集中管理运行时资源。
2.  改造 `Reactor`，使其持有 `ResourceRegistry` 并在执行任务时将其作为第三个参数注入。
3.  更新 `cascade-std` 中所有标准物理原语（Probe, Resource Broker, Triad, System ICs）的函数签名，以接收新的 `resources` 参数。
4.  更新相关测试中的 Mock 函数签名，确保测试通过。

### 评论
这是一个具有广泛破坏性的重构（Breaking Change），涉及修改所有物理层函数的签名。为了保证系统的原子性和一致性，我们必须在一个原子操作中同时更新 `Reactor` 调用方和所有 `cascade-std` 被调用方，以及相关的测试用例。这是消除 `functools.partial` 依赖、实现图与环境解耦的关键一步。

### 目标
1.  创建 `cascade.vm.resource_registry.ResourceRegistry`。
2.  更新 `Reactor._execute_task` 以传递 `resource_registry`。
3.  将所有 `cascade-std` 及测试中的物理函数签名从 `(inputs, node)` 更新为 `(inputs, node, resources)`。

### 基本原理
目前的架构中，资源通常通过闭包或 `partial` 绑定到函数上，导致物理图无法纯粹序列化。通过引入 `ResourceRegistry` 并强制所有物理函数接受它作为标准参数，我们为后续通过字符串 ID 动态查找资源（如 `resources.get("queue")`）奠定了基础，从而实现了逻辑图（引用）与物理环境（实例）的彻底分离。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/std #concept/resource #scope/core #ai/instruct #task/domain/core #task/object/resource-registry #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 ResourceRegistry

首先在 `cascade-vm` 中实现资源注册表。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/resource_registry.py
~~~~~
~~~~~python
from typing import Any, Dict, Optional


class ResourceRegistry:
    def __init__(self):
        self._resources: Dict[str, Any] = {}

    def register(self, resource_id: str, resource: Any) -> None:
        if resource_id in self._resources:
            raise ValueError(f"Resource '{resource_id}' is already registered.")
        self._resources[resource_id] = resource

    def get(self, resource_id: str) -> Any:
        if resource_id not in self._resources:
            raise KeyError(f"Resource '{resource_id}' not found.")
        return self._resources[resource_id]

    def has(self, resource_id: str) -> bool:
        return resource_id in self._resources
~~~~~

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/__init__.py
~~~~~
~~~~~python
from .resource_registry import ResourceRegistry

__all__ = ["ResourceRegistry"]
~~~~~

#### Acts 2: 改造 Reactor

修改 `Reactor` 以接收并传递注册表。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
from typing import List, Callable, Dict, Tuple, Awaitable
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map

        # State
~~~~~
~~~~~python.new
from typing import List, Callable, Dict, Tuple, Awaitable, Optional, Any
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()

        # State
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node)
            else:
                result_tokens = await self.executor.submit(func, (input_data, node))

            if not isinstance(result_tokens, dict):
~~~~~
~~~~~python.new
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node, self.resource_registry)
            else:
                result_tokens = await self.executor.submit(
                    func, (input_data, node, self.resource_registry)
                )

            if not isinstance(result_tokens, dict):
~~~~~

#### Acts 3: 更新 cascade-std 函数签名 (Probe & Resource)

批量更新 `cascade-std` 中所有物理函数的签名，增加 `resources` 参数。由于 `cascade-std` 不依赖 `cascade-vm`，我们使用 `Any` 类型。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/const.py
~~~~~
~~~~~python.old
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def const_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode


async def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/context.py
~~~~~
~~~~~python.old
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.common.context import get_current_context


async def param_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    name = inputs["name"].payload
    # In a real run, values are resolved by the Context/Engine.
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode
from cascade.common.context import get_current_context


async def param_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    name = inputs["name"].payload
    # In a real run, values are resolved by the Context/Engine.
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/env.py
~~~~~
~~~~~python.old
import os
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def env_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    name = inputs["name"].payload
    val = os.environ.get(name)
~~~~~
~~~~~python.new
import os
from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode


async def env_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    name = inputs["name"].payload
    val = os.environ.get(name)
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/pulse.py
~~~~~
~~~~~python.old
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def pulse_generator(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    trigger_token = inputs["trigger"]
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode


async def pulse_generator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    trigger_token = inputs["trigger"]
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
async def continuous_allocator(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
~~~~~
~~~~~python.new
from typing import Any

async def continuous_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/continuous.py
~~~~~
~~~~~python.old
async def continuous_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
~~~~~
~~~~~python.new
async def continuous_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
~~~~~
~~~~~python.new
from typing import Any

async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
async def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
~~~~~
~~~~~python.new
async def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/requestor.py
~~~~~
~~~~~python.old
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    amount_token = inputs["amount"]
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode


async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    amount_token = inputs["amount"]
~~~~~

#### Acts 4: 更新 cascade-std 函数签名 (System & Triad)

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/drainer.py
~~~~~
~~~~~python.old
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken


async def drain_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    control_token = SystemControlToken(command="DRAIN")
    return {"out": Token(payload=control_token)}
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken


async def drain_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    control_token = SystemControlToken(command="DRAIN")
    return {"out": Token(payload=control_token)}
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/terminator.py
~~~~~
~~~~~python.old
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken


async def halt_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
~~~~~
~~~~~python.new
from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken


async def halt_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
async def standard_bleacher(
    inputs: Dict[str, Token], node: BleachNode
) -> Dict[str, Token]:
    worker_payload: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
~~~~~
~~~~~python.new
from typing import Any

async def standard_bleacher(
    inputs: Dict[str, Token], node: BleachNode, resources: Any
) -> Dict[str, Token]:
    worker_payload: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/observer.py
~~~~~
~~~~~python.old
async def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, *, queue: Queue
) -> None:
    event_token = inputs["event_token"]
    trace = event_token.trace
~~~~~
~~~~~python.new
async def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any, *, queue: Queue
) -> None:
    event_token = inputs["event_token"]
    trace = event_token.trace
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
async def standard_stainer(
    inputs: Dict[str, Token], node: StainNode
) -> Dict[str, Token]:
    end_ts = time.monotonic()

    # 1. Extract inputs
~~~~~
~~~~~python.new
from typing import Any

async def standard_stainer(
    inputs: Dict[str, Token], node: StainNode, resources: Any
) -> Dict[str, Token]:
    end_ts = time.monotonic()

    # 1. Extract inputs
~~~~~

#### Acts 5: 更新测试用例中的 Mock 函数

更新 `cascade-vm` 测试中的 dummy 函数以匹配新签名。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
# Dummy function for testing
def noop(inputs, node):
    # Echos back a generic result token on 'out' port
    return {"out": Token(payload="result")}
~~~~~
~~~~~python.new
# Dummy function for testing
def noop(inputs, node, resources):
    # Echos back a generic result token on 'out' port
    return {"out": Token(payload="result")}
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_observability_congestion.py
~~~~~
~~~~~python.old
def noop_producer(inputs, node):
    return {"out": Token(payload="event")}
~~~~~
~~~~~python.new
def noop_producer(inputs, node, resources):
    return {"out": Token(payload="event")}
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_branching.py
~~~~~
~~~~~python.old
def switch_logic(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    in_token = inputs["in"]
    direction = in_token.payload
~~~~~
~~~~~python.new
def switch_logic(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    in_token = inputs["in"]
    direction = in_token.payload
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ping_pong.py
~~~~~
~~~~~python.old
def simple_increment(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    # Extract
    in_token = inputs["value"]
~~~~~
~~~~~python.new
def simple_increment(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    # Extract
    in_token = inputs["value"]
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
def mock_worker(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload
    val = worker_payload["x"]
    return {"worker_result": Token(payload=val + 1)}


def noop_observer(inputs: Dict[str, Token], node) -> Dict[str, Token]:
    return {}
~~~~~
~~~~~python.new
def mock_worker(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    worker_input_token = inputs["worker_input"]
    worker_payload = worker_input_token.payload
    val = worker_payload["x"]
    return {"worker_result": Token(payload=val + 1)}


def noop_observer(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    return {}
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~
~~~~~python.old
    def obs_enabled_logic(inputs, node):
        val = inputs["value"].payload
        # Emit Result AND Observation
~~~~~
~~~~~python.new
    def obs_enabled_logic(inputs, node, resources):
        val = inputs["value"].payload
        # Emit Result AND Observation
~~~~~

### 下一步建议
我们已经完成了物理层的基础设施改造。所有物理节点现在都通过统一的 `(inputs, node, resources)` 接口接收运行时环境。
下一步应继续执行阶段 2：**应用新模型并重构测试工具**。具体来说，重构 `EventDrivenRunner` 和 `standard_observer`，移除对 `functools.partial` 的依赖，改用 `ResourceRegistry` 查找队列资源。这将验证我们的新架构在实际测试场景中的可用性。
