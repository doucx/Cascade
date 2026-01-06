好的，我们继续实施计划，创建 `standard_dispatcher` 内核函数。

这是实现“断连式异步执行”模型的关键一步。`standard_dispatcher` 将扮演所有用户任务（`WorkerNode`）在物理层的代理。它不会自己执行业务逻辑，而是将执行请求打包成一个 `ComputeRequest`，然后“发射”到一个队列中，由我们刚刚创建的 `LocalComputeService` 这样的后台服务来处理。

为了让 `dispatcher` 能够工作，它需要知道要执行哪个函数（通过 `code_hash`）。最纯粹的方式是将这个信息作为元数据存储在物理 `WorkerNode` 上。因此，我将首先对 `WorkerNode` 的规范进行一个小小的补充。

## [WIP] feat(std): 创建 standard_dispatcher 用于异步计算卸载

### 用户需求

创建一个名为 `standard_dispatcher` 的标准库内核函数。该函数将作为所有用户 `WorkerNode` 在物理层的标准实现，负责创建 `ComputeRequest` 对象并将其发送到后台计算队列。

### 评论

这是将 `Reactor` 的物理循环与用户代码执行彻底解耦的核心步骤。通过引入 `dispatcher`，我们将 `WorkerNode` 的角色从一个“执行者”转变为一个“发射器”。这完全符合 v3.1 架构的“断连式执行”模型，为实现一个高性能、无阻塞的 `Reactor` 奠定了基础。

### 目标

1.  更新 `cascade.spec.physical.triad.WorkerNode` 的定义，使其能够携带要执行代码的规范哈希 (`canonical_code_structure_hash`)。
2.  在 `cascade-std` 包中创建新的 `dispatcher.py` 文件并实现 `standard_dispatcher` 函数。
3.  实现 `dispatcher` 的核心逻辑：组装 `ComputeRequest` 并将其放入通过 `resources` 注入的队列中。
4.  确保 `dispatcher` 返回一个空字典，以在物理层面正确地终止该计算分支的能量流。

### 基本原理

`dispatcher` 需要两个关键信息来组装 `ComputeRequest`：要执行代码的 `code_hash` 和计算完成后用于返回结果的 `reply_to_nid`。

1.  **`code_hash`**: 通过在 `WorkerNode` 数据结构上增加一个 `canonical_code_structure_hash` 字段，编译器可以将这个信息从逻辑层“烧录”到物理图中。这使得 `dispatcher` 在运行时可以无歧义地获取此信息，而无需违反“无 `partial` 闭包”的纯粹性原则。
2.  **`reply_to_nid`**: `dispatcher` 可以通过自己的 `node.id` (例如 `...-hash-....worker`) 推导出其兄弟节点 `d_worker_out` 的确定性 ID (例如 `...-hash-....data.out`)。这利用了编译器生成 ID 的确定性，避免了在图中传递额外的状态。

### 标签

#intent/build #flow/ready #priority/high #comp/std #comp/vm #concept/executor #scope/api #task/state/continue

---

### Script

#### Acts 1: 更新 `WorkerNode` 规范

我们首先修改 `WorkerNode` 的定义，为其添加 `canonical_code_structure_hash` 字段。提供默认值以确保向后兼容。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physical/triad.py
~~~~~
~~~~~python.old
@dataclass
class WorkerNode(PhysicsFuncNode):
    pass
~~~~~
~~~~~python.new
@dataclass
class WorkerNode(PhysicsFuncNode):
    # The canonical hash of the code this worker is supposed to execute.
    # This is populated by the compiler and used by the standard_dispatcher.
    canonical_code_structure_hash: str = ""
~~~~~

#### Acts 2: 实现 `standard_dispatcher`

现在，我们创建 `dispatcher.py` 文件并实现 `standard_dispatcher` 的逻辑。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/triad/dispatcher.py
~~~~~
~~~~~python
import logging
from typing import Dict, Any

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import WorkerNode
from cascade.spec.physical.object import Ref
from cascade.vm.compute import ComputeRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)


async def standard_dispatcher(
    inputs: Dict[str, Token], node: WorkerNode, resources: Any
) -> Dict[str, Token]:
    """
    The standard physical implementation for all user WorkerNodes.

    This function does not execute user code directly. Instead, it dispatches
    a ComputeRequest to a background service via a queue.
    """
    # 1. Extract input refs from the token prepared by the Bleacher.
    # The payload of the 'worker_input' token is expected to be a Dict[str, Ref].
    worker_input_token = inputs["worker_input"]
    input_refs: Dict[str, Ref] = worker_input_token.payload

    # 2. Deterministically calculate the reply-to address (the downstream DataNode).
    base_id = node.id.replace(".worker", "")
    reply_to_nid = PhysicalIdGenerator.worker_out_data(base_id)

    # 3. Get the code hash from the node's metadata.
    code_hash = node.canonical_code_structure_hash
    if not code_hash:
        raise ValueError(
            f"WorkerNode '{node.id}' is missing canonical_code_structure_hash. "
            "The compiler must populate this field."
        )

    # 4. Propagate the trace from the input token.
    trace = worker_input_token.trace

    # 5. Assemble the computation request.
    request = ComputeRequest(
        code_hash=code_hash,
        input_refs=input_refs,
        reply_to_nid=reply_to_nid,
        trace=trace,
    )

    # 6. Get the compute queue from the resource registry and dispatch.
    try:
        compute_queue = resources.get("system.compute_queue")
        await compute_queue.put(request)
    except KeyError:
        logger.error("Resource 'system.compute_queue' not found. Cannot dispatch compute request.")
        raise
    except Exception:
        logger.exception(f"Failed to dispatch compute request for node {node.id}")
        raise

    # 7. Return an empty dictionary to "evaporate" the energy in this branch.
    # The flow will resume when the ComputeService places the result token
    # into the `reply_to_nid` data node.
    return {}
~~~~~

#### Acts 3: 导出 `standard_dispatcher`

最后，更新 `triad` 包的 `__init__.py` 文件以导出新函数。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/triad/__init__.py
~~~~~
~~~~~python.old
# Standard Triad logic (Execution Units) for the Cascade VM.
~~~~~
~~~~~python.new
# Standard Triad logic (Execution Units) for the Cascade VM.
from .dispatcher import standard_dispatcher

__all__ = ["standard_dispatcher"]
~~~~~

### 下一步建议

我们已经构建了 `LocalComputeService` 和 `standard_dispatcher`，这是异步执行模型的两个核心支柱。然而，它们还没有被集成到系统中。下一步是进行一系列关键的集成工作：

1.  **更新编译器**: 修改 `cascade-compiler` 中的 `Expander`，使其在创建 `WorkerNode` 时，能够从 `SymbolTable` 获取 `canonical_code_structure_hash` 并填充到新增加的字段中。
2.  **更新链接器**: 修改 `cascade-vm` 中的 `Linker`，让它将所有用户 `WorkerNode` 链接到我们新创建的 `standard_dispatcher`，而不是之前生成的用户函数包装器。
3.  **更新测试Harness**: 修改 `cascade-vm` 中的 `EventDrivenRunner`，使其能够初始化 `LocalComputeService` 以及所需的队列，并将队列注入到 `ResourceRegistry` 中，以便 `dispatcher` 能够找到它们。
