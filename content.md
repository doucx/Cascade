这是执行“纠偏行动计划”的第一步。我们将集中修复 `cascade-std` 中的核心组件，使其适应 Ref-Based 架构（通过标量提升）并转换为同步函数，为真正的 PhysicsKernel 铺平道路。

简要回答：
我们将修改 `const_probe` 以支持标量提升，并将 `discrete` (allocator/reclaimer), `requestor`, `bleacher`, `stainer`, `dispatcher` 重写为同步函数。

## [WIP] refactor(std): Implement scalar hoisting and sync kernel functions

### 用户需求
1.  **修复数据流协议**: `const_probe` 产生的 `Ref` 必须携带可直接读取的标量值 (`scalar_value`)，以便 `allocator` 等内核组件无需 I/O 即可进行决策。
2.  **同步化标准库**: 将核心 ICs (`allocator`, `reclaimer`, `bleacher`, `stainer`, `requestor`, `dispatcher`) 从 `async def` 转换为 `def`，以符合 `PhysicsKernel` 的纯同步执行要求。
3.  **兼容性适配**: 更新后的 ICs 需要能同时处理 v3.1 的 `Ref` 输入和 v3.0 的直接值输入（用于旧测试兼容）。

### 评论
这是一个关键的架构修正。它解决了“恐怖谷”问题——即系统处于新旧架构中间状态导致的崩溃。通过“标量提升 (Scalar Hoisting)”，我们巧妙地绕过了“内核不能做 I/O”的限制，使得控制流决策依然可以在纯物理层高效完成。

### 目标
1.  修改 `const_probe.py`: 在生成 `Ref` 时检测并注入 `scalar_value` 元数据。
2.  修改 `discrete.py`:
    *   移除 `async`。
    *   在 `allocator` 和 `reclaimer` 中增加对 `Ref` 输入的检查，优先从 `meta['scalar_value']` 获取数值。
3.  修改 `requestor.py`: 移除 `async`。
4.  修改 `bleacher.py`: 移除 `async`。
5.  修改 `stainer.py`: 移除 `async`。
6.  修改 `dispatcher.py`: 移除 `async`，改用 `queue.put_nowait()`。

### 基本原理
*   **Scalar Hoisting**: `Allocator` 需要知道“申请多少资源”才能工作。在 Ref-Based 架构中，这个数字被封装在 `Ref` 指向的 `ObjectStore` 中。为了避免 `Allocator` 进行 I/O (这会阻塞 Kernel)，我们在 `Probe` 阶段（允许 I/O）就将这个关键数字提取出来，放在 `Ref` 的元数据“信封”上。
*   **Sync Kernel**: `PhysicsKernel` 被设计为单线程、无阻塞的极速循环。任何 `async` 函数都会迫使 Reactor 使用 `await` 或线程池，破坏了这一设计目标。标准库组件作为系统的基础指令集，必须是同步的。

### 标签
#intent/refine #flow/ready #priority/critical #comp/std #concept/ref-architecture #scope/core #ai/instruct #task/domain/core #task/object/std-lib #task/action/sync-conversion #task/state/begin

---

### Script

#### Acts 1: 实现标量提升 (Scalar Hoisting)

修改 `const_probe`，使其在创建 `Ref` 时，如果数据是标量，则将其放入元数据中。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/probe/const.py
~~~~~
~~~~~python.old
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


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
from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    raw_value = val_token.payload

    # Ref-Based Architecture:
    # Probes are responsible for materializing external/static data into Refs.
    store = resources.get("system.object_store")

    # Scalar Hoisting:
    # If the value is a scalar, we hoist it into metadata so Kernel ICs (Allocator)
    # can read it without I/O.
    meta = {}
    if isinstance(raw_value, (int, float, bool, str)) and len(str(raw_value)) < 1024:
        meta["scalar_value"] = raw_value

    ref = store.put(raw_value, metadata=meta)

    return {"out": Token(payload=ref, trace=val_token.trace)}
~~~~~

#### Acts 2: 同步化资源组件并适配 Ref

修改 `discrete.py`，移除 `async`，并添加从 `Ref` 元数据读取值的逻辑。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python
from typing import Dict, Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref


@dataclass
class DiscreteLedger:
    total: int
    available: int


def _extract_scalar(payload: Any) -> Union[int, float]:
    """Helper to extract scalar value from Ref or raw payload."""
    if isinstance(payload, Ref):
        # v3.1: Try to get hoisted scalar
        if "scalar_value" in payload.meta:
            return payload.meta["scalar_value"]
        # If not hoisted, we technically can't read it in Kernel.
        # But for now we fail gracefully or return 0?
        # Raising error is better to catch missing hoisting.
        raise ValueError(f"Ref {payload.uri} missing 'scalar_value' metadata for Kernel access.")
    return payload


def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    
    # Extract Ledger (Handle Ref if ledger itself is ref-based in future, currently payload is obj)
    # For now ledger payload is passed as-is (PhysicsDataNode initial_payload)
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = _extract_scalar(req_token.payload)

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount

        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            outputs[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Recirculate
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs


def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = inputs["rel_in"]
    release_amount = _extract_scalar(rel_token.payload)

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    return {"ledger_out": Token(payload=ledger)}
~~~~~

#### Acts 3: 同步化 Requestor

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/requestor.py
~~~~~
~~~~~python.old
async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    amount_token = inputs["amount"]

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    return {"req_out": Token(payload=amount_token.payload, trace=trace)}
~~~~~
~~~~~python.new
def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    amount_token = inputs["amount"]

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    return {"req_out": Token(payload=amount_token.payload, trace=trace)}
~~~~~

#### Acts 4: 同步化 Bleacher

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/bleacher.py
~~~~~
~~~~~python.old
async def standard_bleacher(
    inputs: Dict[str, Token], node: BleachNode, resources: Any
) -> Dict[str, Token]:
    worker_payload: Dict[str, Any] = {}
~~~~~
~~~~~python.new
def standard_bleacher(
    inputs: Dict[str, Token], node: BleachNode, resources: Any
) -> Dict[str, Token]:
    worker_payload: Dict[str, Any] = {}
~~~~~

#### Acts 5: 同步化 Stainer

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/stainer.py
~~~~~
~~~~~python.old
async def standard_stainer(
    inputs: Dict[str, Token], node: StainNode, resources: Any
) -> Dict[str, Token]:
    end_mono = time.monotonic()
~~~~~
~~~~~python.new
def standard_stainer(
    inputs: Dict[str, Token], node: StainNode, resources: Any
) -> Dict[str, Token]:
    end_mono = time.monotonic()
~~~~~

#### Acts 6: 同步化 Dispatcher

我们将使用 `put_nowait` 来避免 `await`，假设队列容量足够。如果队列已满，这里会抛出 `QueueFull`，这在同步上下文中是可接受的错误（甚至可以触发背压机制，虽然目前没有处理）。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/dispatcher.py
~~~~~
~~~~~python.old
async def standard_dispatcher(
    inputs: Dict[str, Token], node: WorkerNode, resources: Any
) -> Dict[str, Token]:
    # 1. Extract input refs from the token prepared by the Bleacher.
~~~~~
~~~~~python.new
def standard_dispatcher(
    inputs: Dict[str, Token], node: WorkerNode, resources: Any
) -> Dict[str, Token]:
    # 1. Extract input refs from the token prepared by the Bleacher.
~~~~~

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/dispatcher.py
~~~~~
~~~~~python.old
    # 6. Get the compute queue from the resource registry and dispatch.
    try:
        compute_queue = resources.get("system.compute_queue")
        await compute_queue.put(request)
    except KeyError:
        logger.error(
            "Resource 'system.compute_queue' not found. Cannot dispatch compute request."
        )
~~~~~
~~~~~python.new
    # 6. Get the compute queue from the resource registry and dispatch.
    try:
        compute_queue = resources.get("system.compute_queue")
        compute_queue.put_nowait(request)
    except KeyError:
        logger.error(
            "Resource 'system.compute_queue' not found. Cannot dispatch compute request."
        )
~~~~~

### 下一步建议

现在标准库已经同步化且具备了 Ref 感知能力。接下来的关键步骤是：
1.  **激活 `PhysicsKernel`**: 修改 `Reactor` 以识别同步的 `KernelFunc` 并直接调用它们，绕过 `executor.submit` 线程池。
2.  **修复测试 Harness**: `test_resource_backpressure.py` 需要注入 `system.object_store`，否则 `const_probe` 会失败。
3.  **运行测试**: 验证这些修改是否解决了 `TypeError: '>=' not supported` 错误。
