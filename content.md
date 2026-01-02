好的，我们继续执行迁移路线图。

这是为执行 **任务 5.0.2: 定义编译器中间表示 (IR)** 生成的计划。

## [WIP] feat(spec): 定义编译器中间表示 (IR)

### 用户需求

根据《Cascade 3.0: Phase 5 迁移总纲与执行路线图》的规定，执行任务 5.0.2。需要在 `cascade-spec` 包中，创建一个新的 `ir/` 子目录，并定义连接 Frontend 和 Backend 的核心数据契约，包括 `GraphIR`, `NodeIR`, 和 `TaskDef` 等数据模型。

### 评论

这是奠定整个 v3.0 编译流程基石的关键一步。通过在 `cascade-spec` (规格包) 中定义 IR，我们将其确立为一份全系统共享的、不可更改的**协议**，而非某个组件的内部实现细节。这从架构上强制解耦了 Frontend (意图解析) 和 Backend (物理实现)，使得两部分可以独立开发、测试和演进，是实现“概念纯粹性”原则的核心体现。

### 目标

1.  在 `packages/cascade-spec/src/cascade/spec/` 目录下创建 `ir/` 子目录。
2.  创建并填充 `ir/models.py` 文件，定义所有核心 IR 数据类。
3.  创建 `ir/__init__.py` 以便其他包可以方便地导入这些模型。
4.  更新顶层的 `spec/__init__.py` 文件，将新的 IR 模型暴露出来。

### 基本原理

我们继续遵循“原子化、非破坏性演进”原则，通过创建新文件和新目录来引入 IR 定义。`GraphIR` 将作为 Frontend 的输出和 Backend 的输入，是连接用户声明式 API 和 VM 物理执行之间的“通用语”。此操作将为下一个阶段（Phase 5.1: 构建桥梁）提供明确的、类型安全的目标数据结构。

### 标签

#intent/architect #flow/ready #priority/high #comp/spec #concept/compiler #scope/api #ai/instruct #task/domain/compiler #task/object/ir-models #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 IR 目录

首先，我们创建 `ir` 子目录，为新的模型文件提供存放位置。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/cascade-spec/src/cascade/spec/ir
~~~~~

#### Acts 2: 定义 IR 数据模型

接下来，我们创建 `ir/models.py` 文件，并写入所有核心数据类的定义。这些定义包含了详尽的文档字符串，以阐明其在架构中的作用。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    """Defines the kind of an argument, aligning with Python's inspect.Parameter kinds."""

    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    """A specific definition of a single argument in a task's signature."""

    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass(frozen=True)
class TaskDef:
    """
    The static intermediate representation (IR) of a Task.
    This separates the 'definition' of what a task is from the 'node'
    of where it is used in a graph.
    """

    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'canonical_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"


@dataclass(frozen=True)
class NodeIR:
    """
    Intermediate Representation of a Task instantiation in the logical graph.
    This is the input to the Compiler Backend.
    """

    id: str
    """Unique identifier for this node instance (e.g. current_instance_hash)."""

    name: str
    """Human-readable name."""

    task: TaskDef
    """The definition of the task being invoked."""

    inputs: Dict[str, Any] = field(default_factory=dict)
    """Mapping of argument names to values. 
    Values can be literals or references to other NodeIR IDs."""

    constraints: Dict[str, Any] = field(default_factory=dict)
    """Resource constraints for this node (e.g. {'gpu': 1})."""


@dataclass(frozen=True)
class GraphIR:
    """A collection of NodeIRs representing the full logical workflow."""

    nodes: List[NodeIR] = field(default_factory=list)
~~~~~

#### Acts 3: 创建 IR 包的 `__init__.py`

我们创建一个 `__init__.py` 文件，以便其他包可以从 `cascade.spec.ir` 导入这些模型。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/__init__.py
~~~~~
~~~~~python
from .models import ArgumentKind, ArgumentDef, TaskDef, NodeIR, GraphIR

__all__ = ["ArgumentKind", "ArgumentDef", "TaskDef", "NodeIR", "GraphIR"]
~~~~~

#### Acts 4: 将 IR 模型暴露到顶层 `spec` 命名空间

最后，我们修改 `cascade-spec` 的顶层 `__init__.py`，将新定义的 IR 模型加入其公共 API。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/__init__.py
~~~~~
~~~~~python.old
from .ports import PortRole, PortDef

__all__ = [
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Token",
    "PhysicsNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "BleachNode",
    "WorkerNode",
    "StainNode",
    "ObservabilityNode",
    "Channel",
    "BipartiteGraph",
    "ResourceSlot",
    "EnvironmentDef",
    "ResourceDef",
    "PortRole",
    "PortDef",
]
~~~~~
~~~~~python.new
from .ports import PortRole, PortDef
from .ir import ArgumentKind, ArgumentDef, TaskDef, NodeIR, GraphIR

__all__ = [
    "ArgumentDef",
    "ArgumentKind",
    "BipartiteGraph",
    "BleachNode",
    "Channel",
    "EnvironmentDef",
    "Fingerprint",
    "GraphIR",
    "InvalidFingerprintKeyError",
    "NodeIR",
    "ObservabilityNode",
    "PhysicsDataNode",
    "PhysicsFuncNode",
    "PhysicsNode",
    "PortDef",
    "PortRole",
    "ResourceDef",
    "ResourceSlot",
    "StainNode",
    "TaskDef",
    "Token",
    "WorkerNode",
]
~~~~~

### 下一步建议

我们已经成功定义了连接编译器前端和后端的“通用语言”。至此，Phase 5.0 的所有准备工作均已完成。

根据路线图，下一步我们将进入 **Phase 5.1: 构建桥梁**，其核心任务是 **5.1.1: 创建新的 IR 生成器 (`IRGenerator`)**。这个组件将负责将用户编写的 `LazyResult` 树，转换为我们刚刚定义的 `GraphIR` 结构。如果你同意，我将开始准备该任务的计划。
