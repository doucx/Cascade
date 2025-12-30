## [WIP] feat(spec): 实现 IR 核心数据模型

### 用户需求
在 `cascade-spec` 包中实现 Intermediate Representation (IR) 的核心数据模型。这些模型包括图结构的定义 (`GraphIR`, `NodeIR`, `EdgeIR`) 以及虚拟机指令集的初步定义 (`Instruction`, `Call`, `Return`)。这是 TDD 流程的 "Green" 阶段，旨在通过之前创建的 `test_ir_models.py` 测试。

### 评论
当前 `packages/cascade-spec/src/cascade/spec/ir/models.py` 仅包含 `TaskDef` 等基础定义。为了支持编译器和 VM 的解耦架构，我们需要引入更完整的图描述结构和线性指令集结构。这些类被设计为纯数据类 (`dataclass`)，以确保易于序列化和在组件间传递。

### 目标
1.  修改 `packages/cascade-spec/src/cascade/spec/ir/models.py`，添加 `GraphIR`, `NodeIR`, `EdgeIR`, `Instruction`, `Call`, `Return` 等类定义。
2.  修改 `packages/cascade-spec/src/cascade/spec/ir/__init__.py`，导出上述新类。
3.  更新 `packages/cascade-spec/tests/spec/test_ir_models.py`，移除 `xfail` 标记，正式启用测试断言。

### 基本原理
根据 "焦土政策" 路线图的阶段 0，我们需要建立 "真理" 数据结构。通过使用 `dataclass`，我们获得免费的 `__init__`, `__repr__` 和易于转换为字典的能力（这对 `asdict` 测试至关重要）。将图结构 (IR) 与指令集 (VM Instructions) 定义在规范层，有助于后续实现编译器前端和后端时的依赖解耦。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #concept/ir #scope/core #ai/instruct #task/domain/refactor #task/object/ir-models #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 定义 IR 数据模型

我们将向 `models.py` 添加缺少的类定义。注意我们需要导入 `field` 和 `Any`, `Dict` 等类型提示。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from cascade.spec.fingerprint import Fingerprint
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'current_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'current_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"


@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeIR:
    source_id: str
    target_id: str
    target_arg: str


@dataclass
class GraphIR:
    nodes: List[NodeIR]
    edges: List[EdgeIR]
    meta: Dict[str, Any] = field(default_factory=dict)


# --- VM Instruction Set ---


@dataclass
class Instruction:
    id: str


@dataclass
class Call(Instruction):
    task_name: str
    args: List[Any]
    output_register: str


@dataclass
class Return(Instruction):
    source_register: str
~~~~~

#### Acts 2: 导出新模型

更新 `__init__.py` 以公开新添加的类，使其可以被外部模块（如测试）导入。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/__init__.py
~~~~~
~~~~~python.old
from .models import ArgumentKind, ArgumentDef, TaskDef

__all__ = ["ArgumentKind", "ArgumentDef", "TaskDef"]
~~~~~
~~~~~python.new
from .models import (
    ArgumentKind,
    ArgumentDef,
    TaskDef,
    GraphIR,
    NodeIR,
    EdgeIR,
    Instruction,
    Call,
    Return,
)

__all__ = [
    "ArgumentKind",
    "ArgumentDef",
    "TaskDef",
    "GraphIR",
    "NodeIR",
    "EdgeIR",
    "Instruction",
    "Call",
    "Return",
]
~~~~~

#### Acts 3: 启用测试

现在代码已实现，我们需要移除测试文件中的 `xfail` 标记，并删除为了兼容 `ImportError` 而写的 try-except 块，让测试能够正常运行并验证代码。

~~~~~act
patch_file
packages/cascade-spec/tests/spec/test_ir_models.py
~~~~~
~~~~~python.old
# NOTE: These classes are not yet defined. We expect an ImportError here.
# This is the normal "RED" state of the TDD process.
try:
    from cascade.spec.ir.models import (
        GraphIR,
        NodeIR,
        EdgeIR,
        TaskDef,
        ArgumentDef,
        ArgumentKind,
        Instruction,
        Call,
        Return,
    )
    from cascade.spec.fingerprint import Fingerprint
except ImportError:
    # We allow the import to fail so that the test file itself is syntactically valid,
    # but the tests below will fail at runtime if the classes do not exist.
    pass


@pytest.mark.xfail(raises=NameError, reason="IR models not yet implemented")
def test_ir_structures_exist():
~~~~~
~~~~~python.new
from cascade.spec.ir.models import (
    GraphIR,
    NodeIR,
    EdgeIR,
    TaskDef,
    ArgumentDef,
    ArgumentKind,
    Instruction,
    Call,
    Return,
)
from cascade.spec.fingerprint import Fingerprint


def test_ir_structures_exist():
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/spec/test_ir_models.py
~~~~~
~~~~~python.old
@pytest.mark.xfail(raises=NameError, reason="IR models not yet implemented")
def test_ir_serialization_roundtrip():
~~~~~
~~~~~python.new
def test_ir_serialization_roundtrip():
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/spec/test_ir_models.py
~~~~~
~~~~~python.old
@pytest.mark.xfail(raises=NameError, reason="IR models not yet implemented")
def test_instruction_serialization():
~~~~~
~~~~~python.new
def test_instruction_serialization():
~~~~~
