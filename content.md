好的，我们现在进入 TDD 流程的“GREEN”阶段。我已经创建了失败的测试（RED），现在我将生成实现 `cascade.spec.ir` 模块的代码，以使这些测试通过。

这个计划将创建所需的数据模型，为整个重构奠定数据契约的基础。

## [WIP] feat(spec): 实现核心 IR 数据模型

### 用户需求
根据 TDD 流程，需要实现 `cascade.spec.ir.models` 模块中的核心数据类，以满足 `test_ir_models.py` 中定义的契约，从而使测试套件从“RED”状态转为“GREEN”状态。

### 评论
这是整个“焦土政策”重构计划的基石。通过定义这些纯粹的、不可变的数据结构，我们为编译器和运行时之间建立了一个稳定且可序列化的契约。这是将旧架构的耦合问题从根本上解决的第一步。遵循测试驱动开发可以确保我们的实现从一开始就是正确且符合预期的。

### 目标
1.  创建 `packages/cascade-spec/src/cascade/spec/ir/` 目录。
2.  创建 `models.py` 文件，并在其中使用 `@dataclass(frozen=True)` 定义所有必需的 IR 模型，包括 `GraphIR`, `NodeIR`, `EdgeIR`, `TaskDef`, `ArgumentDef`, `ArgumentKind` 以及 `Instruction` 指令集。
3.  创建 `__init__.py` 文件，并从中导出所有新定义的模型，使它们成为 `cascade.spec.ir` 公开 API 的一部分。
4.  本次实现应足以让 `packages/cascade-spec/tests/spec/test_ir_models.py` 中的所有测试用例通过。

### 基本原理
我们将使用 Python 标准库中的 `dataclasses` 模块来定义这些 IR 模型。选择 `dataclasses` 是因为它轻量、无依赖，并且其生成的类默认支持序列化（通过 `asdict`），完全符合我们对纯数据结构的需求。将它们设置为 `frozen=True` 可以强制实现 IR 的不可变性，确保数据在编译器各阶段传递过程中的一致性和线程安全。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #concept/ir #scope/api #ai/instruct #task/domain/refactor #task/object/ir-models #task/action/define #task/state/continue

---

### Script

#### Acts 1: 创建 IR 模块目录结构

首先，我们创建 `ir` 子包的目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-spec/src/cascade/spec/ir
~~~~~

#### Acts 2: 实现 IR 数据模型

接下来，我们创建 `models.py` 文件并定义所有需要的数据类。这些定义直接响应了测试文件中的断言。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from cascade.spec.fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    """
    Defines the kind of an argument, aligning with Python's inspect.Parameter kinds.
    """

    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    """
    A serializable, static definition of a single argument in a task's signature.
    """

    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass(frozen=True)
class TaskDef:
    """
    The static intermediate representation (IR) of a Task.
    This separates the 'definition' of what a task is from its usage 'node' in a graph.
    """

    name: str
    args: List[ArgumentDef]
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    mode: str = "blocking"


@dataclass(frozen=True)
class NodeIR:
    """
    Represents a single node in the computation graph IR.
    """

    id: str
    definition: TaskDef
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeIR:
    """
    Represents a dependency edge between two nodes in the graph IR.
    """

    source_id: str
    target_id: str
    target_arg: str


@dataclass(frozen=True)
class GraphIR:
    """
    Represents the entire computation graph IR.
    """

    nodes: List[NodeIR] = field(default_factory=list)
    edges: List[EdgeIR] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


# --- VM Instruction Set IR ---


@dataclass(frozen=True)
class Instruction:
    """
    Base class for all VM instructions.
    """

    id: str


@dataclass(frozen=True)
class Call(Instruction):
    """

    Represents a function call instruction.
    """

    task_name: str
    args: List[Any]
    output_register: str


@dataclass(frozen=True)
class Return(Instruction):
    """
    Represents a return instruction from a function.
    """

    source_register: str
~~~~~

#### Acts 3: 导出新的 IR 模型

最后，创建 `__init__.py` 文件，将所有新定义的类导出，使它们成为包的公共 API 的一部分。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/__init__.py
~~~~~
~~~~~python
from .models import (
    ArgumentKind,
    ArgumentDef,
    TaskDef,
    NodeIR,
    EdgeIR,
    GraphIR,
    Instruction,
    Call,
    Return,
)

__all__ = [
    "ArgumentKind",
    "ArgumentDef",
    "TaskDef",
    "NodeIR",
    "EdgeIR",
    "GraphIR",
    "Instruction",
    "Call",
    "Return",
]
~~~~~

### 下一步建议
我们已经完成了 Phase 0 的实现。现在应该运行测试套件，验证 `test_ir_models.py` 中的测试是否全部通过，从而确认我们已经达到了 TDD 流程的“GREEN”状态。

如果你同意，请告诉我，我将生成一个运行测试的 `run_command` 计划。
