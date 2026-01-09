简要回答
我们将在 `cascade-spec` 包中创建 `physics` 模块，并实现 `Port` 定义体系（Law of Ports）和 `PhysicsSpec` 基类（Law of Spec），为物理层建立强类型的契约基础。

## [WIP] feat: 实施 PIDL 阶段一 - 定义物理法则

### 用户需求
在 `cascade-spec` 包中建立物理接口定义层 (PIDL) 的基础架构。具体包括：
1.  定义端口的元数据结构 (`PortDef`, `PortRole`, `PortType`)。
2.  定义物理节点契约的基类 (`PhysicsSpec`) 及其元类逻辑，用于自动收集端口定义。
3.  提供 `Port.Input` 和 `Port.Output` 等辅助工厂方法，实现类声明式的 Spec 定义风格。

### 评论
这是 PIDL 路线图的基石。通过引入 `PhysicsSpec`，我们将物理层的“隐式约定”（比如 Kernel 函数必须接受名为 `ledger_in` 的参数）转化为“显式契约”。这不仅消除了魔法字符串，还为未来的 Kernel 类型检查、文档自动生成和更智能的 Compiler 连线提供了元数据支持。

### 目标
在 `packages/cascade-spec/src/cascade/spec/physics/` 目录下完成 `core.py`, `spec.py` 和 `__init__.py` 的创建。

### 基本原理
我们采用 **描述符 (Descriptor) + 元类 (Metaclass)** 的模式来实现 DSL。
*   **`core.py`**: 定义原子概念。复用现有的 `cascade.spec.physical.ports.PortRole` 以保持语义一致性，同时引入新的 `PortType` 和 `PortDef`。
*   **`spec.py`**: 定义结构法则。`PhysicsSpecMeta` 负责在类创建时扫描 `PortDef` 描述符，并将它们注册到 `input_ports` 和 `output_ports` 字典中，从而使得 Spec 类既是定义也是注册表。

### 标签
#intent/architect #flow/ready #priority/high #comp/interfaces #concept/spec #scope/core #ai/instruct #task/domain/core #task/object/physics-spec #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建物理法则模块目录

首先，我们为新的 `physics` 模块创建目录结构。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-spec/src/cascade/spec/physics
~~~~~

#### Acts 2: 定义核心端口概念 (The Core Laws)

创建 `core.py`，定义端口的角色、类型和描述符。我们复用底层的 `PortRole` 以确保与现有物理图的兼容性。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physics/core.py
~~~~~
~~~~~python
from enum import Enum
from typing import Any

# Import PortRole from the existing physical layer to maintain compatibility
# and avoid semantic drift between the "Law" (physics) and the "Matter" (physical).
from cascade.spec.physical.ports import PortRole


class PortType(str, Enum):
    """
    Defines the semantic type of data flowing through a port.
    """
    Token = "Token"      # Generic data token
    Ledger = "Ledger"    # Resource ledger
    Any = "Any"          # Any type


class PortDirection(str, Enum):
    """
    Defines the direction of flow for a port relative to the Node.
    """
    INPUT = "input"
    OUTPUT = "output"


class PortDef:
    """
    Descriptor for defining a port on a PhysicsSpec.
    Acts as the definition of a single interface point on a physical node.
    """
    def __init__(
        self,
        name: str,
        direction: PortDirection,
        role: PortRole = PortRole.DATA,
        type_hint: Any = PortType.Any
    ):
        self.name = name
        self.direction = direction
        self.role = role
        self.type_hint = type_hint

    def __set_name__(self, owner, name):
        # We allow the attribute name to act as a fallback or strict mapping validation later.
        pass

    def __repr__(self):
        return f"PortDef(name='{self.name}', dir={self.direction}, role={self.role})"


class Port:
    """
    Namespace factory for defining ports in a declarative style.
    Example:
        data_in = Port.Input("data_in")
    """
    
    @staticmethod
    def Input(name: str, role: PortRole = PortRole.DATA, type: Any = PortType.Any) -> PortDef:
        return PortDef(name, PortDirection.INPUT, role, type)

    @staticmethod
    def Output(name: str, role: PortRole = PortRole.DATA, type: Any = PortType.Any) -> PortDef:
        return PortDef(name, PortDirection.OUTPUT, role, type)
~~~~~

#### Acts 3: 定义物理契约基类 (The Spec Laws)

创建 `spec.py`，实现 `PhysicsSpec` 及其元类。这是 PIDL 的核心，它负责将声明式的 Python 类转化为可自省的端口映射表。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physics/spec.py
~~~~~
~~~~~python
from typing import Dict, Protocol, Any
from .core import PortDef, PortDirection


class PhysicsSpecMeta(type):
    """
    Metaclass that collects PortDef descriptors and registers them
    into `input_ports` and `output_ports` dictionaries on the class.
    """
    def __new__(mcs, name, bases, namespace):
        # 1. Create the class
        cls = super().__new__(mcs, name, bases, namespace)
        
        input_ports: Dict[str, PortDef] = {}
        output_ports: Dict[str, PortDef] = {}
        
        # 2. Inherit ports from base classes (if any)
        # We traverse bases in reverse order so that later bases (and the class itself) override earlier ones.
        for base in reversed(bases):
            if hasattr(base, "input_ports"):
                input_ports.update(base.input_ports)
            if hasattr(base, "output_ports"):
                output_ports.update(base.output_ports)

        # 3. Collect ports from the current class definition
        for key, value in namespace.items():
            if isinstance(value, PortDef):
                # The key in the dict is the attribute name (e.g. 'ledger_in').
                # The value.name is the actual string name of the port (e.g. "ledger_in").
                # Usually they are the same, but the dict allows access by attribute name.
                if value.direction == PortDirection.INPUT:
                    input_ports[key] = value
                else:
                    output_ports[key] = value
        
        # 4. Register the collected ports
        cls.input_ports = input_ports
        cls.output_ports = output_ports
        
        return cls


class PhysicsSpec(metaclass=PhysicsSpecMeta):
    """
    Base class for all Physical Node Specifications.
    
    Subclasses should define ports using the `Port.Input` and `Port.Output` helpers.
    The metaclass will automatically aggregate these into `input_ports` and `output_ports`.
    """
    input_ports: Dict[str, PortDef]
    output_ports: Dict[str, PortDef]

    class IO(Protocol):
        """
        Protocol stub for Kernel function type hinting.
        
        In the future, `@implements(Spec)` will use this Protocol to enforce
        that the kernel function accepts an 'io' object with attributes matching
        the Spec's ports.
        """
        pass
~~~~~

#### Acts 4: 暴露模块接口

最后，创建 `__init__.py` 以导出这些新概念。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physics/__init__.py
~~~~~
~~~~~python
from .core import Port, PortRole, PortType, PortDef, PortDirection
from .spec import PhysicsSpec

__all__ = [
    "Port",
    "PortRole",
    "PortType",
    "PortDef",
    "PortDirection",
    "PhysicsSpec",
]
~~~~~

### 下一步建议
我们已经建立了“物理法则”的基础。根据路线图，下一步是 **阶段二：标准化物理契约 (The Contracts)**。

建议在 `cascade-std` 包中创建 `cascade.std.specs` 模块，并开始将现有的 IC（如 `DiscreteAllocator`, `Bleacher`）的隐式端口定义显式化为 `PhysicsSpec` 的子类。这将验证我们刚刚建立的 DSL 的表达能力。
