好的，我们将立即开始执行 **Phase 4.5** 的第一步：清理静态错误和注释。

这是一个 `[WIP]` 计划，专注于代码质量修复，为后续的架构对齐工作奠定一个干净的基础。

## [WIP] fix(typing): 解决 pyright 静态分析错误并修正注释

### 用户需求

根据代码审查报告，需要修复 `pyright` 发现的所有类型错误，并将代码库中不符合规范（例如，使用中文）的注释进行修正。

### 评论

这是偿还技术债务的第一步，也是最基础的一步。解决这些静态分析错误和规范性问题，可以确保我们的代码基线是健康的，从而让后续更大规模的重构能够在一个稳定、可靠的基础上进行。这些是提升开发者体验（DX）和代码可维护性的关键小改进。

### 目标

1.  **修复 `expander.py`**: 在 `SubGraph` dataclass 中为 `bleacher` 和 `stainer` 字段添加 `Optional` 类型提示，使其与 `None` 的默认值匹配。
2.  **修复 `bleacher.py`**: 将函数签名中错误的 `any` 类型提示更正为从 `typing` 导入的 `Any`。
3.  **修正 `input.py`**: 将 `InputSpec` 类中的中文注释翻译为符合项目规范的英文。

### 基本原理

我们将通过三个独立的 `patch_file` 操作，精确地对三个文件中的问题进行原子化修复。这确保了每个修改的意图都清晰明确，便于审查。

1.  对于 `expander.py`，问题在于类型声明与实际默认值不符，`Optional` 是解决此问题的标准方法。
2.  对于 `bleacher.py`，问题是误用了 Python 的内置函数 `any` 作为类型注解，应使用 `typing.Any`。
3.  对于 `input.py`，问题是注释语言不统一，违反了项目全英文的规范。

### 标签

#intent/fix #flow/ready #priority/high #comp/compiler #comp/vm #comp/spec #scope/dx #ai/instruct #task/domain/refactoring #task/object/static-analysis #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修复 `expander.py` 的类型注解

我们将为 `SubGraph` 中的 `bleacher` 和 `stainer` 字段添加 `Optional` 类型，以解决类型不匹配的错误。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import List, Dict

from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsNode, PhysicsDataNode
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel


@dataclass
class SubGraph:
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)

    # Interface pointers
    bleacher: BleachNode = None
    stainer: StainNode = None
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsNode, PhysicsDataNode
from cascade.spec.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.topology import Channel


@dataclass
class SubGraph:
    nodes: Dict[str, PhysicsNode] = field(default_factory=dict)
    channels: List[Channel] = field(default_factory=list)

    # Interface pointers
    bleacher: Optional[BleachNode] = None
    stainer: Optional[StainNode] = None
~~~~~

#### Acts 2: 修复 `bleacher.py` 的类型注解

这里我们将 `any` 修正为 `Any`，并更新 `worker_payload` 和 `trace_payload` 的类型提示。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/instructions/bleacher.py
~~~~~
~~~~~python.old
from typing import Dict
import time

from cascade.spec.physics import Token


from typing import List, Optional


def standard_bleacher(
    inputs: Dict[str, Token], expected_args: Optional[List[str]] = None
) -> Dict[str, Token]:
    worker_payload: Dict[str, any] = {}
    trace_payload: Dict[str, any] = {}
    held_resources: List[str] = []

    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        # Only pass expected data args to the worker
        if expected_args is None or port_name in expected_args:
            worker_payload[port_name] = input_token.payload
        else:
~~~~~
~~~~~python.new
from typing import Dict, Any
import time

from cascade.spec.physics import Token


from typing import List, Optional


def standard_bleacher(
    inputs: Dict[str, Token], expected_args: Optional[List[str]] = None
) -> Dict[str, Token]:
    worker_payload: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        # Only pass expected data args to the worker
        if expected_args is None or port_name in expected_args:
            worker_payload[port_name] = input_token.payload
        else:
~~~~~

#### Acts 3: 修正 `input.py` 中的注释

我们将 `InputSpec` 中的中文注释翻译为英文。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/input.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class InputSpec:
    name: str
    default: Any = None
    description: str = ""
    # 注意: 'required' 属性被移除，其逻辑由 'default' 是否存在来隐式定义。
    # 运行时若无 default 且未提供值，则会失败。
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class InputSpec:
    name: str
    default: Any = None
    description: str = ""
    # NOTE: The 'required' attribute is removed; its logic is implicitly defined
    # by whether 'default' is present. A runtime error will occur if no default
    # is set and no value is provided.
~~~~~

### 下一步建议

我们已经完成了代码清理。现在代码库处于一个更健康的状态，我建议我们继续执行 **Phase 4.5** 的第二步：**形式化环境定义 (Formalize Environment)**。

这将涉及从 `Builder` 中剥离其凭空创造资源的权力，并引入一个 `EnvironmentDef` 结构，使资源管理更符合物理场的客观现实。如果你同意，我将开始制定该计划。
