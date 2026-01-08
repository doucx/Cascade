好的，我将处理这些 Pyright 类型错误，并移除已弃用的 `add_sink` 机制。

这是一个系统性的清理和类型修复任务。我将按照组件的依赖关系，从底层规约（spec）和协议（protocols）开始，逐步向上修复实现。

## [WIP] fix(typing): 修复 Pyright 错误并移除 add_sink 机制

### 用户需求

1.  修复 `pyright packages` 命令报告的 31 个类型错误。
2.  移除整个系统中已弃用的 `add_sink` 机制，包括其在协议、实现和文档中的所有引用。

### 评论

这是一个重要的技术债清理任务。类型错误表明代码的某些部分存在不一致或潜在的运行时问题，修复它们可以提高代码的健壮性和可维护性。移除 `add_sink` 机制则简化了 Reactor 的核心逻辑，使其更符合物理模型的定义。

### 目标

1.  **协议层**: 更新 `ReactorProtocol`，移除 `add_sink` 并添加 `Machine` 正常运行所需的其他属性（如 `shutdown_event`）。
2.  **实现层**:
    *   从 `Reactor` 实现中移除 `add_sink` 和 `sinks` 相关逻辑。
    *   修复 `cascade-compiler`、`cascade-std` 和 `cascade-vm` 中的类型不匹配问题。
3.  **文档层**: 移除与 `add_sink` 相关的 stitcher 文档条目。
4.  确保所有修改后，类型检查能够干净地通过。

### 基本原理

我将采用分阶段、原子化的方式进行修复：

1.  **移除 `add_sink`**: 这是一项全局性的删除操作。我将一次性从协议、实现和文档中彻底移除所有相关代码，以确保一致性。
2.  **修复核心类型定义**: 首先修复 `cascade-spec` 和 `cascade-reflection` 中的类型定义和依赖问题，因为它们是其他包的基础。例如，修复 `MappedLazyResult` 和 `HashingService` 中的问题。
3.  **修复实现代码**: 在核心类型正确后，我将修复上层 `cascade-std` 和 `cascade-vm` 中因类型不匹配或逻辑错误导致的 pyright 错误。这包括显式类型注解、`None` 值检查和正确的类型转换。

通过这种自下而上的方法，可以确保修复是彻底和无副作用的。

### 标签

#intent/fix #flow/ready #priority/high #comp/compiler #comp/vm #comp/spec #scope/core #scope/dx #ai/instruct #task/domain/typing #task/object/pyright-errors #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 协议层修复：更新 ReactorProtocol 并移除 add_sink

首先，我们更新 `ReactorProtocol`，使其准确反映 `Reactor` 的接口，并移除 `add_sink`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/protocols.py
~~~~~
~~~~~python
import asyncio
from typing import Protocol, Callable, Awaitable, Dict, Any, Optional
from cascade.spec.physical.nodes import Token


class ReactorProtocol(Protocol):
    shutdown_event: asyncio.Event
    drain_event: asyncio.Event
    ingress_queue: Optional[asyncio.Queue]

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None: ...

    def step(self) -> int: ...
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/protocols.stitcher.yaml
~~~~~
~~~~~
"ReactorProtocol.add_sink": |-
  Register a callback to receive tokens emitted by a specific port.
"ReactorProtocol.prime": |-
~~~~~
~~~~~
"ReactorProtocol.prime": |-
~~~~~

#### Acts 2: 实现层修复：从 Reactor 中移除 Sinks

现在，从具体的 `Reactor` 实现和文档中移除 `add_sink` 逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
        self.shutdown_event = asyncio.Event()
        self.drain_event = asyncio.Event()

        # State
        # node_id -> port_name -> list of callbacks
        self.sinks: Dict[str, Dict[str, List[Callable[[Token], Awaitable[None]]]]] = {}

        # Indexing for O(1) lookups during step/fire
        self._func_nodes: List[PhysicsFuncNode] = []
~~~~~
~~~~~python.new
        self.shutdown_event = asyncio.Event()
        self.drain_event = asyncio.Event()

        # Indexing for O(1) lookups during step/fire
        self._func_nodes: List[PhysicsFuncNode] = []
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
                self._outbound_channels[source.id].append(channel)

    def add_sink(
        self,
        node_id: str,
        port_name: str,
        callback: Callable[[Token], Awaitable[None]],
    ) -> None:
        if node_id not in self.sinks:
            self.sinks[node_id] = {}
        if port_name not in self.sinks[node_id]:
            self.sinks[node_id][port_name] = []
        self.sinks[node_id][port_name].append(callback)

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None:
        genesis_trace = genesis_trace or {}
        for node in self.graph.nodes.values():
~~~~~
~~~~~python.new
                self._outbound_channels[source.id].append(channel)

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None:
        genesis_trace = genesis_trace or {}
        for node in self.graph.nodes.values():
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
            )
            return

        outbound = self._outbound_channels.get(node.id, [])
        node_sinks = self.sinks.get(node.id, {})

        for port_name, token in results.items():
            if token is None:
                continue

            # 0. Intercept System Control Tokens
            if isinstance(token.payload, SystemControlToken):
                self._handle_control_signal(token.payload)

            # A. Handle Sinks (Callbacks)
            # Note: Sinks in the physical layer MUST be non-blocking.
            # If they return a coroutine, we schedule it on the loop but do NOT await.
            if port_name in node_sinks:
                for cb in node_sinks[port_name]:
                    try:
                        res = cb(token)
                        if inspect.isawaitable(res):
                            # Fire and forget for async sinks
                            asyncio.create_task(res)
                    except Exception as e:
                        logger.exception(
                            f"Sink callback failed for {node.id}:{port_name}: {e}"
                        )

            # B. Handle Outbound Channels (Topological Flow)
            matching_channels = [c for c in outbound if c.source_port == port_name]
            for channel in matching_channels:
                target_node = self.graph.nodes[channel.target_node_id]
~~~~~
~~~~~python.new
            )
            return

        outbound = self._outbound_channels.get(node.id, [])

        for port_name, token in results.items():
            if token is None:
                continue

            # 0. Intercept System Control Tokens
            if isinstance(token.payload, SystemControlToken):
                self._handle_control_signal(token.payload)

            # A. Handle Outbound Channels (Topological Flow)
            matching_channels = [c for c in outbound if c.source_port == port_name]
            for channel in matching_channels:
                target_node = self.graph.nodes[channel.target_node_id]
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.stitcher.yaml
~~~~~
~~~~~yaml.old
"Reactor": |-
  The heart of the physics engine.
  Scans the topology for excited states and fires transitions.
"Reactor.add_sink": |-
  Register a callback to receive tokens emitted by a specific port.
"Reactor.prime": |-
  Injects initial potential energy (tokens) into the system
  based on PhysicsDataNode.initial_tokens.
~~~~~
~~~~~yaml.new
"Reactor": |-
  The heart of the physics engine.
  Scans the topology for excited states and fires transitions.
"Reactor.prime": |-
  Injects initial potential energy (tokens) into the system
  based on PhysicsDataNode.initial_tokens.
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/system/retry.py
~~~~~
~~~~~python.old
        trace["retry_count"] = retry_count
        return {"retry_out": context_token}
    else:
        # Fail permanently: route error token to failure sink
        return {"fail_out": error_token}
~~~~~
~~~~~python.new
        trace["retry_count"] = retry_count
        return {"retry_out": context_token}
    else:
        # Fail permanently: route error token to the failure output port
        return {"fail_out": error_token}
~~~~~

#### Acts 3: 修复 Compiler 和 Spec 中的类型错误

接下来，我们修复编译器前端和核心规约中的类型不一致问题。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/dsl/fluent.py
~~~~~
~~~~~python.old
    _cache_policy: Optional[Any] = None  # CachePolicy
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List[LazyResult] = field(default_factory=list)

    def __hash__(self):
        return hash(self._uuid)
~~~~~
~~~~~python.new
    _cache_policy: Optional[Any] = None  # CachePolicy
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List[LazyResult] = field(default_factory=list)
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)

    def __hash__(self):
        return hash(self._uuid)
~~~~~
~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/hashing.py
~~~~~
~~~~~python.old
from typing import Any, List, Dict
from cascade.spec.ir.graph import TaskDef
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.spec.dsl.routing import Router
from cascade.spec.dsl.resources import Inject
from cascade.runtime.graph.model import Node


class HashingService:
    def compute_node_instance_hash(
        self,
        definition: TaskDef,
        result: Any,  # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, Node],
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        canonical_code_structure_hash = definition.fingerprint[
~~~~~
~~~~~python.new
import hashlib
from typing import Any, List, Dict
from cascade.spec.ir.graph import TaskDef, NodeIR
from cascade.spec.dsl.fluent import LazyResult, MappedLazyResult
from cascade.spec.dsl.routing import Router
from cascade.spec.dsl.resources import Inject


class HashingService:
    def compute_node_instance_hash(
        self,
        definition: TaskDef,
        result: Any,  # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, "NodeIR"],
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        canonical_code_structure_hash = definition.fingerprint[
~~~~~
~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/hashing.py
~~~~~
~~~~~python.old
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components(self, obj: Any, dep_nodes: Dict[str, Node]) -> List[str]:
        # This recursive helper remains largely similar, just updated type hints if needed
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            components.append(f"LAZY({node.current_node_instance_hash})")

        elif isinstance(obj, Router):
            components.append("Router{")
~~~~~
~~~~~python.new
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf--8")).hexdigest()

    def _build_hash_components(
        self, obj: Any, dep_nodes: Dict[str, "NodeIR"]
    ) -> List[str]:
        # This recursive helper remains largely similar, just updated type hints if needed
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            components.append(f"LAZY({node.current_node_instance_hash})")

        elif isinstance(obj, Router):
            components.append("Router{")
~~~~~

#### Acts 4: 修复 Standard Library (`std`) 中的类型错误

现在修复 `std` 包中的类型问题，包括资源管理和 Triad 逻辑。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = _extract_scalar(req_token.payload)

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
~~~~~
~~~~~python.new
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = int(_extract_scalar(req_token.payload))

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
        ledger = ledger_data

    rel_token = inputs["rel_in"]
    release_amount = _extract_scalar(rel_token.payload)

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)
~~~~~
~~~~~python.new
        ledger = ledger_data

    rel_token = inputs["rel_in"]
    release_amount = int(_extract_scalar(rel_token.payload))

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
from typing import Dict, Any, List
import time

from cascade.spec import EventIR, EventType, EventState
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import BleachNode
~~~~~
~~~~~python.new
from typing import Dict, Any, List
import time

from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import BleachNode
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (The Hologram)
    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
~~~~~
~~~~~python.new
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (The Hologram)
    ctx: EventContext = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
from typing import Dict, Any
import time

from cascade.spec import EventIR, EventType, EventState
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import StainNode
~~~~~
~~~~~python.new
from typing import Dict, Any
import time

from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import StainNode
~~~~~
~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
        state = EventState.FAILED
        error_msg = str(result_payload)

    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    # Handle preview generation: pass Refs through, stringify others.
~~~~~
~~~~~python.new
        state = EventState.FAILED
        error_msg = str(result_payload)

    ctx: EventContext = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    # Handle preview generation: pass Refs through, stringify others.
~~~~~

#### Acts 5: 修复 VM 中的类型错误

最后，我们修复虚拟机（VM）及其协调层（Machine）中的类型错误。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        max_workers: int = None,
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self.store = store
~~~~~
~~~~~python.new
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        max_workers: Optional[int] = None,
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self.store = store
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
import asyncio
import logging
from cascade.vm.reactor import Reactor
from cascade.vm.compute.service import LocalComputeService
from cascade.vm.services.chronos import ChronosService

logger = logging.getLogger(__name__)


class Machine:
    def __init__(
        self,
        reactor: Reactor,
        compute_service: LocalComputeService,
        chronos_service: ChronosService,
~~~~~
~~~~~python.new
import asyncio
import logging
from cascade.vm.protocols import ReactorProtocol
from cascade.vm.compute.service import LocalComputeService
from cascade.vm.services.chronos import ChronosService

logger = logging.getLogger(__name__)


class Machine:
    def __init__(
        self,
        reactor: ReactorProtocol,
        compute_service: LocalComputeService,
        chronos_service: ChronosService,
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
                        if (
                            fired_count == 0
                            and self.compute_service.active_count == 0
                            and self.ingress_queue.empty()
                        ):
                            logger.info("System drained (Quiescent). Shutting down.")
                            self.reactor.shutdown_event.set()
~~~~~
~~~~~python.new
                        is_ingress_pending = (
                            self.ingress_queue and not self.ingress_queue.empty()
                        )
                        if (
                            fired_count == 0
                            and self.compute_service.active_count == 0
                            and not is_ingress_pending
                        ):
                            logger.info("System drained (Quiescent). Shutting down.")
                            self.reactor.shutdown_event.set()
~~~~~

### 下一步建议

我们已经解决了 `cascade-compiler`、`cascade-std` 和 `cascade-vm` 包中的类型错误和 `add_sink` 移除。下一步是重新运行 `pyright packages`，检查是否还有其他错误。特别是那些我因为缺少文件上下文而跳过的包（`cascade-library`、`cascade-runtime` 等），它们可能仍有错误。如果还有错误，请提供新的错误报告，我将继续修复它们。
