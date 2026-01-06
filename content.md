好的，我们开始实现路线图的第三阶段修订版。

第一步是定义计算契约 `ComputeRequest`，它将作为物理层和计算层之间通信的标准数据结构。

我将创建一个新文件 `packages/cascade-vm/src/cascade/vm/compute/contract.py` 来存放这个结构，并更新相应的 `__init__.py` 文件。

## [WIP] feat(vm): 定义计算契约 ComputeRequest

### 用户需求

根据修订后的 v3.1 架构路线图，需要在 `cascade.vm.compute` 命名空间下定义一个标准的、可序列化的 `ComputeRequest` 数据结构。该结构用于封装从物理图发往后台计算服务的计算请求。

### 评论

这是实现“出境-入境 (Dispatch Model)”异步计算模型的关键第一步。通过定义一个标准的、不可变的数据结构作为契约，我们确保了物理层（Reactor）和计算层（ComputeDelegate/Service）之间的通信是清晰、解耦且可审计的。这为后续实现 `standard_dispatcher` 和 `LocalComputeService` 奠定了基础。

### 目标

1.  创建新文件 `packages/cascade-vm/src/cascade/vm/compute/contract.py`。
2.  在该文件中，使用 `@dataclass(frozen=True)` 定义 `ComputeRequest` 结构，包含 `code_hash`, `input_refs`, `reply_to_nid`, 和 `trace` 字段。
3.  更新 `packages/cascade-vm/src/cascade/vm/compute/__init__.py`，导出 `ComputeRequest`。

### 基本原理

将 `ComputeRequest` 作为一个独立的契约（contract）文件，可以清晰地分离数据结构定义与具体实现。使用 `dataclasses` 可以快速创建一个健壮且类型安全的值对象。将其设为 `frozen=True` 确保了计算请求在系统内部流转时是不可变的，这增强了系统的可预测性。

### 标签

#intent/architect #flow/ready #priority/high #comp/vm #concept/executor #scope/api #ai/instruct #task/domain/vm #task/object/compute-contract #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建计算契约文件

首先，我们创建 `contract.py` 文件并定义 `ComputeRequest` 数据类。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/compute/contract.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Any

from cascade.spec.physical.object import Ref


@dataclass(frozen=True)
class ComputeRequest:
    """
    A standard data structure to define a computation request dispatched
    from the Physics Layer to the Data Plane.
    """

    code_hash: str
    """The canonical hash of the code to execute."""

    input_refs: Dict[str, Ref]
    """A dictionary mapping argument names to input References."""

    reply_to_nid: str
    """
    The "reply-to" address. After computation, the result Token should be
    injected into the DataNode with this ID.
    """

    trace: Dict[str, Any] = field(default_factory=dict)
    """The physical trace inherited from the original Token, for context propagation."""
~~~~~

#### Acts 2: 更新 `__init__.py` 以导出新符号

接下来，更新 `__init__.py` 文件，使 `ComputeRequest` 成为 `cascade.vm.compute` 命名空间的一部分。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/__init__.py
~~~~~
~~~~~python.old
from .local import LocalComputeDelegate

__all__ = ["LocalComputeDelegate"]
~~~~~
~~~~~python.new
from .local import LocalComputeDelegate
from .contract import ComputeRequest

__all__ = ["LocalComputeDelegate", "ComputeRequest"]
~~~~~

### 下一步建议

我们已经成功定义了计算契约。下一步是实现 `LocalComputeService`，它将作为一个后台服务，监听并处理这些 `ComputeRequest` 对象。
