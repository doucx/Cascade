简要回答
我们将实现 Cascade 的中间表示 (IR) 层，定义用于描述任务静态结构的 `TaskDef` 和 `ArgumentDef` 模型，并将 `Fingerprint` 集成其中作为核心身份标识。

## [WIP] feat(spec): 引入 IR 层与 TaskDef 定义

### 用户需求
在 `cascade.spec.ir` 包中实现 IR 层，具体包含 `ArgumentDef` 和 `TaskDef` 数据类。`TaskDef` 必须将之前引入的 `Fingerprint` 类作为其核心属性，用于承载任务的稳定标识符。

### 评论
这是“解构 Node 对象”提案的第一步物理落地。通过将任务的“定义 (Definition)”与“图节点 (Node)”分离，我们将为未来的序列化、分布式执行和增量编译打下坚实的基础。

### 目标
1.  创建 `cascade.spec.ir` 包结构。
2.  实现 `ArgumentKind` 枚举（与 Stitcher 对齐）。
3.  实现 `ArgumentDef` 和 `TaskDef`，其中 `TaskDef` 包含 `fingerprint: Fingerprint` 字段。

### 基本原理
IR 是静态分析和运行时之间的契约。
-   **类型安全**: 使用 `Enum` 和 `dataclass` 确保定义的严格性。
-   **身份明确**: 通过强制包含 `Fingerprint` 对象，我们在定义阶段就确立了“身份 (Identity)”的首要地位，遵循“稳定标识符”的架构原则。
-   **对应关系**: `ArgumentDef` 对应 Python 的参数定义，但针对序列化进行了简化（例如 `default_value_repr` 存储字符串而非对象）。

### 标签
#intent/architect #flow/ready #priority/high #comp/interfaces #concept/ir #scope/core #ai/instruct #task/domain/core #task/object/ir-models #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 IR 包结构

创建存放 IR 模型的目录。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-spec/src/cascade/spec/ir
~~~~~

#### Acts 2: 实现 IR 模型

创建 `cascade/spec/ir/models.py`，定义核心数据结构。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from cascade.spec.fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    """
    Defines the kind of an argument, aligning with Python's inspect.Parameter kinds
    and the Stitcher specification.
    """
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"        # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    """
    A specific definition of a single argument in a task's signature.
    Designed to be serializable.
    """
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
    # Must contain keys like 'current_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
~~~~~

#### Acts 3: 导出 IR 模块

创建 `cascade/spec/ir/__init__.py` 以公开新的模型。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/ir/__init__.py
~~~~~
~~~~~python
from .models import ArgumentKind, ArgumentDef, TaskDef

__all__ = ["ArgumentKind", "ArgumentDef", "TaskDef"]
~~~~~

### 下一步建议
IR 层的基本模型定义完成。接下来的逻辑步骤是：
1.  定义 `Analyzer` 协议 (`cascade.graph.analysis.protocols`)。
2.  实现默认的 `ReflectionAnalyzer`，这是将 Python 可调用对象转换为这些 IR 模型的桥梁。
3.  最后修改 `Node` 对象以使用新的 `TaskDef`。
