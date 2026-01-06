这是实现 Cascade v3.1 物理层“Ref-Only”契约的关键重构。我们将修改标准库 IC 和运行时组件，确保元数据（Metadata）在整个系统中正确流动和被利用。

简要回答

## [WIP] refactor(std): 统一内核 IC 的 Ref 处理契约与元数据前置

### 用户需求
1.  **统一 Ref 处理**: 修改 `cascade-std` 中的所有内核 IC，使其不再直接处理原始数据，而是处理 `Ref` 对象。
2.  **元数据前置 (Metadata Hoisting)**: 在生成 `Ref` 时（Probe, ComputeService），将关键的标量值（如 int, bool）和状态（is_error）提升到 `Ref.meta` 中。
3.  **无 I/O 决策**: 强制 `Allocator` 和 `Stainer` 等决策型 IC 仅通过读取 `Ref.meta` 来执行逻辑，避免对 `ObjectStore` 的阻塞性读取。

### 评论
这是一次“心脏手术”。它将彻底切断物理层（Control Plane）对数据实体（Data Plane）的直接依赖，真正实现 v3.1 架构中“控制与数据分离”的愿景。这也解决了之前集成测试中遇到的类型不匹配问题。

### 目标
1.  **Probe 层**: `const_probe` 生成带有 `value` 元数据的 `Ref`。
2.  **Compute 层**: `LocalComputeService` 生成带有 `is_error` 和 `value` 元数据的 `Ref`。
3.  **Resource 层**: `discrete_allocator` 和 `reclaimer` 改为通过 `Ref` 交互，利用元数据读取请求量，利用 `store` 管理 Ledger 状态。
4.  **Triad 层**: `standard_stainer` 改为检查 `Ref.meta['is_error']`。
5.  **Reactor 层**: 增强 `prime` 方法，实现“创世物化”，确保初始注入的 Token 也是 `Ref` 类型。

### 基本原理
目前系统处于混合状态，导致 `Allocator` 收到 `Ref` 却试图将其当作 `int` 处理。通过强制实施 Ref 契约和元数据提升，我们允许内核在不知道数据具体内容（无需下载/反序列化）的情况下进行调度。对于必须修改状态的 `Allocator`，明确其作为“有状态内核函数”的地位，允许其与内存存储进行极速交互。

### 标签
#intent/refine #flow/ready #priority/high #comp/std #comp/runtime #concept/ref-architecture #scope/core #ai/instruct #task/domain/core #task/object/ic-contract #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 增强 `InMemoryObjectStore` 的元数据支持

我们需要确保存储层能够正确处理和合并元数据。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/storage/memory.py
~~~~~
~~~~~python.old
    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref:
        # 1. Generate URI
        uid = str(uuid.uuid4())
        uri = f"mem://{uid}"

        # 2. Prepare Metadata
        meta = metadata.copy() if metadata else {}

        # Auto-detect basic metadata if not provided
        if "type" not in meta:
            meta["type"] = type(obj).__name__

        # 3. Store
        self._store[uri] = (obj, meta)

        # 4. Return Ref
        return Ref(uri=uri, meta=meta)
~~~~~
~~~~~python.new
    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref:
        # 1. Generate URI
        uid = str(uuid.uuid4())
        uri = f"mem://{uid}"

        # 2. Prepare Metadata
        meta = metadata.copy() if metadata else {}

        # Auto-detect basic metadata
        if "type" not in meta:
            meta["type"] = type(obj).__name__

        # 3. Store
        self._store[uri] = (obj, meta)

        # 4. Return Ref
        return Ref(uri=uri, meta=meta)
~~~~~

#### Acts 2: 升级 `const_probe` 实现元数据前置

`const_probe` 现在不仅要存数据，还要把标量值“提升”到元数据中，供下游 `Allocator` 读取。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/const.py
~~~~~
~~~~~python.old
async def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    raw_value = val_token.payload

    # Ref-Based Architecture:
    # Probes are responsible for materializing external/static data into Refs.
    store = resources.get("system.object_store")
    ref = store.put(raw_value)

    return {"out": Token(payload=ref, trace=val_token.trace)}
~~~~~
~~~~~python.new
async def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    raw_value = val_token.payload

    # Ref-Based Architecture:
    # Probes are responsible for materializing external/static data into Refs.
    store = resources.get("system.object_store")

    # Metadata Hoisting: Lift scalars to metadata for Kernel access
    meta = {}
    if isinstance(raw_value, (int, float, bool, str)) and len(str(raw_value)) < 64:
        meta["value"] = raw_value

    ref = store.put(raw_value, metadata=meta)

    return {"out": Token(payload=ref, trace=val_token.trace)}
~~~~~

#### Acts 3: 升级 `LocalComputeService` 实现结果元数据化

计算服务在返回结果时，必须标记是否出错，并尽可能提升返回值。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
        # 4. Store Result and Prepare Token
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))
~~~~~
~~~~~python.new
        # 4. Store Result and Prepare Token
        meta = {}
        if isinstance(result, Exception):
            meta["is_error"] = True
            meta["error_type"] = type(result).__name__
            meta["error_msg"] = str(result)
        elif isinstance(result, (int, float, bool, str)) and len(str(result)) < 64:
            meta["value"] = result
            meta["is_error"] = False
        else:
            meta["is_error"] = False

        result_ref = self.store.put(result, metadata=meta)
        result_token = Token(payload=result_ref, trace=request.trace)

        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))
~~~~~

#### Acts 4: 重写 `discrete` 资源 IC 以适配 Ref

这是最复杂的变更。`allocator` 和 `reclaimer` 需要处理 `Ref` 输入，并与 Store 交互以更新 Ledger。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python
from typing import Dict, Any
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref


@dataclass
class DiscreteLedger:
    total: int
    available: int


async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # 1. Access Store (Kernel Capability)
    store = resources.get("system.object_store")

    # 2. Dereference Ledger (Stateful)
    ledger_ref: Ref = inputs["ledger_in"].payload
    # Note: For state, we allow get() in kernel because it's typically in-memory
    ledger_data = store.get(ledger_ref)
    
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    elif isinstance(ledger_data, DiscreteLedger):
        ledger = ledger_data
    else:
        # It might be a Ref if we have nested refs (should not happen in clean state)
        # Or it might be the Raw object if Reactor.prime didn't wrap it.
        # Assuming Reactor.prime wraps initial state, this should be the object.
        raise TypeError(f"Unknown ledger type: {type(ledger_data)}")

    # 3. Read Request (Metadata Hoisted)
    req_token = inputs["req_in"]
    req_ref: Ref = req_token.payload
    
    # Try to get value from metadata first (Fast Path)
    if "value" in req_ref.meta:
        req_amount = req_ref.meta["value"]
    else:
        # Slow Path (Should be avoided by const_probe hoisting)
        req_amount = store.get(req_ref)

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        # We mutate the ledger object. Since it's a dataclass, we can clone or mutate.
        # For Ref architecture, we should treat it as immutable and put a new version.
        new_ledger = DiscreteLedger(total=ledger.total, available=ledger.available - req_amount)
        
        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            out_port = f"gnt_for_{requestor_id}"
            outputs[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Recirculate
        # Ledger remains unchanged (but we still need to emit it back)
        new_ledger = ledger
        outputs["req_out"] = req_token

    # 4. Commit New State
    # We put the new ledger state back to store and get a NEW Ref
    new_ledger_ref = store.put(new_ledger, metadata={"type": "DiscreteLedger"})
    outputs["ledger_out"] = Token(payload=new_ledger_ref)
    
    return outputs


async def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    store = resources.get("system.object_store")

    # 1. Dereference Ledger
    ledger_ref: Ref = inputs["ledger_in"].payload
    ledger_data = store.get(ledger_ref)
    
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    # 2. Get Release Amount
    rel_token = inputs["rel_in"]
    # Rel payload might be raw int (if coming from Stainer output) or Ref
    # Currently Stainer outputting raw int for resources.
    # TODO: Stainer should probably output Ref too? 
    # For now, let's handle both.
    release_amount = rel_token.payload
    if isinstance(release_amount, Ref):
         # If it's a Ref, try meta
        if "value" in release_amount.meta:
            release_amount = release_amount.meta["value"]
        else:
            release_amount = store.get(release_amount)

    # 3. Update
    new_available = min(ledger.total, ledger.available + release_amount)
    new_ledger = DiscreteLedger(total=ledger.total, available=new_available)

    # 4. Commit
    new_ledger_ref = store.put(new_ledger, metadata={"type": "DiscreteLedger"})

    return {"ledger_out": Token(payload=new_ledger_ref)}
~~~~~

#### Acts 5: 更新 `standard_stainer` 以检查元数据

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
    result_payload = worker_result_token.payload

    # Merge traces
    trace_payload = worker_result_token.trace.copy()
    trace_payload.update(trace_input_token.payload)

    # 2. Calculate duration
    start_mono = trace_payload.get("start_ts", end_mono)
    duration = end_mono - start_mono
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_mono

    # 3. Construct EventIR
    logical_id = node.id.replace(".stain", "")

    # Heuristic: Extract task_name from physical name "Stain(MyTask)"
    task_name = "unknown"
    if node.name.startswith("Stain(") and node.name.endswith(")"):
        task_name = node.name[6:-1]

    # Determine Status (Simplified for now, assuming success if reached here)
    # Error handling logic will be refined in future phases
    state = EventState.SUCCEEDED
    error_msg = None

    # TODO: Check if result_payload is an Exception wrapper
    if isinstance(result_payload, Exception):
        state = EventState.FAILED
        error_msg = str(result_payload)

    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    # Handle preview generation: pass Refs through, stringify others.
    preview = None
    if state == EventState.SUCCEEDED:
        from cascade.spec.physical.object import Ref

        if isinstance(result_payload, Ref):
            preview = result_payload
        else:
            preview = str(result_payload)[:100]
~~~~~
~~~~~python.new
    result_ref = worker_result_token.payload

    # Merge traces
    trace_payload = worker_result_token.trace.copy()
    trace_payload.update(trace_input_token.payload)

    # 2. Calculate duration
    start_mono = trace_payload.get("start_ts", end_mono)
    duration = end_mono - start_mono
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_mono

    # 3. Construct EventIR
    logical_id = node.id.replace(".stain", "")

    # Heuristic: Extract task_name from physical name "Stain(MyTask)"
    task_name = "unknown"
    if node.name.startswith("Stain(") and node.name.endswith(")"):
        task_name = node.name[6:-1]

    # Determine Status using Metadata
    from cascade.spec.physical.object import Ref
    state = EventState.SUCCEEDED
    error_msg = None
    
    if isinstance(result_ref, Ref) and result_ref.meta.get("is_error"):
        state = EventState.FAILED
        error_msg = result_ref.meta.get("error_msg", "Unknown error")
        # For telemetry, we might want the error type
    elif isinstance(result_ref, Exception):
        # Fallback for legacy raw exception payloads
        state = EventState.FAILED
        error_msg = str(result_ref)

    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    # Handle preview generation
    preview = None
    if isinstance(result_ref, Ref):
        preview = result_ref
    else:
        preview = str(result_ref)[:100]
~~~~~

#### Acts 6: 修改 `Reactor.prime` 实现创世物化

确保即使是初始注入的 Token（如 Ledger 初始状态），在进入物理层之前也被转换为 Ref。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor.py
~~~~~
~~~~~python.old
    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None:
        genesis_trace = genesis_trace or {}
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    # We inject the genesis trace (e.g. run_id) into these primordial tokens.
                    self.memory.put(
                        node,
                        Token(payload=node.initial_payload, trace=genesis_trace.copy()),
                    )
~~~~~
~~~~~python.new
    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None:
        genesis_trace = genesis_trace or {}
        # Try to get object store for genesis materialization
        store = None
        if self.resource_registry and self.resource_registry.has("system.object_store"):
            store = self.resource_registry.get("system.object_store")

        from cascade.spec.physical.object import Ref

        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    payload = node.initial_payload
                    
                    # Genesis Materialization: Convert raw initial payloads to Refs if possible
                    if store and payload is not None and not isinstance(payload, Ref):
                        # Hoist basic metadata for Ledger/Constants
                        meta = {}
                        if hasattr(payload, "__class__"):
                             meta["type"] = payload.__class__.__name__
                        # For simple scalars, hoist value
                        if isinstance(payload, (int, float, bool, str)) and len(str(payload)) < 64:
                            meta["value"] = payload
                            
                        payload = store.put(payload, metadata=meta)

                    self.memory.put(
                        node,
                        Token(payload=payload, trace=genesis_trace.copy()),
                    )
~~~~~

### 下一步建议
现在物理层的核心 IC 已经升级为 Ref-Aware，并且通过 Metadata Hoisting 机制避免了不必要的 IO。下一步我们应该运行集成测试 `test_resource_backpressure.py` 和 `test_ref_architecture.py`，验证这套新机制是否能打通从创世到执行的全流程。如果测试通过，我们将正式进入第四阶段：彻底移除旧的 Executor 概念，完全转向 Kernel/Compute 双态模型。
