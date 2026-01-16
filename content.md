好的，我们开始执行计划的第一步。

这个阶段的目标是将 `cascade-spec` 包强化为架构的核心，集中管理所有跨包共享的接口、数据契约和开发工具，从而为后续的解耦工作奠定坚实的基础。

## [WIP] refactor: 强化 cascade-spec 以集中管理契约和绑定工具

### 用户需求

根据架构重构蓝图，我们需要将关键的数据契约（`ComputeRequest`, `DelayRequest`）和物理节点实现工具（`implements` 装饰器等）从它们各自的实现包（`cascade-vm`, `cascade-std`）中移出，并统一整合到 `cascade-spec` 包中。

### 评论

这是解耦 `cascade-std` 与 `cascade-vm`、并确立 `cascade-spec` 作为“单一事实来源”的关键第一步。此举不仅能理清混乱的依赖关系，还能极大地改善为 Cascade 生态系统开发第三方组件（如自定义物理节点）时的开发者体验（DX）。

### 目标

1.  在 `cascade.spec.runtime` 模块下创建一个新的 `contracts.py` 文件，用于存放运行时服务之间交互的数据结构。
2.  在 `cascade.spec.physics` 模块下创建一个新的 `binding.py` 文件，用于提供将 Python 函数安全地绑定到物理节点规范的工具。
3.  更新相应的 `__init__.py` 文件，将这些新组件提升为包的公共 API。

### 基本原理

通过将这些定义移动到 `cascade-spec`，我们将它们固化为一套稳定、公开的 API。这使得其他包（如 `cascade-std`）可以仅依赖于 `cascade-spec` 来获取所有必要的接口和工具，而无需关心（甚至导入）具体的实现包（如 `cascade-vm`）。这种方式强制了正确的依赖方向：**实现 -> 规范**，而非 **实现 -> 实现**，从而保证了架构的长期健康。

### 标签

#intent/architect #intent/refine #flow/ready #priority/high #comp/spec #comp/vm #comp/std #scope/api #scope/dx #task/domain/architecture #task/object/decoupling #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建运行时契约模块

我们首先创建 `contracts.py` 文件，并将 `ComputeRequest` 和 `DelayRequest` 这两个核心数据结构移入其中。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/runtime/contracts.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Any

from ..physical.object import Ref
from ..physical.nodes import Token


@dataclass(frozen=True)
class ComputeRequest:
    """A request sent from the VM's dispatcher to a ComputeService."""

    code_hash: str
    input_refs: Dict[str, Ref]
    reply_to_nid: str
    trace: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DelayRequest:
    """A request sent from a 'sleep' IC to the ChronosService."""

    delay_seconds: float
    target_nid: str
    token: Token
~~~~~

#### Acts 2: 暴露运行时契约

接下来，我们更新 `runtime` 包的 `__init__.py`，使其导出新创建的数据契约。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/__init__.py
~~~~~
~~~~~python.old
from .strategies import ExecutionContext, ExecutionStrategy

__all__ = [
    "Solver",
    "Executor",
    "CacheBackend",
    "CachePolicy",
    "StateBackend",
    "SubscriptionHandle",
    "LazyFactory",
    "Provider",
    "Connector",
    "ObjectStore",
    "ComputeDelegate",
    "ExecutionContext",
    "ExecutionStrategy",
]
~~~~~
~~~~~python.new
from .strategies import ExecutionContext, ExecutionStrategy
from .contracts import ComputeRequest, DelayRequest

__all__ = [
    "Solver",
    "Executor",
    "CacheBackend",
    "CachePolicy",
    "StateBackend",
    "SubscriptionHandle",
    "LazyFactory",
    "Provider",
    "Connector",
    "ObjectStore",
    "ComputeDelegate",
    "ExecutionContext",
    "ExecutionStrategy",
    "ComputeRequest",
    "DelayRequest",
]
~~~~~

#### Acts 3: 创建物理层绑定工具模块

现在，我们创建 `binding.py` 文件，并将原位于 `cascade-std` 中的 `kernel_tools` 内容迁移过来。这些工具是实现自定义物理节点（IC）的核心。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/physics/binding.py
~~~~~
~~~~~python
from functools import wraps
from typing import Dict, Any, Type, TypeVar, MutableMapping
from ..physical.nodes import Token, PhysicsNode
from .spec import PhysicsSpec

T = TypeVar("T", bound=PhysicsSpec)


class DynamicOutputMap(MutableMapping):
    def __init__(self, target_dict: Dict[str, Token], prefix: str):
        self._target = target_dict
        self._prefix = prefix

    def __setitem__(self, key: str, value: Token) -> None:
        if not key.startswith(self._prefix):
            raise ValueError(
                f"Dynamic port '{key}' does not match required prefix '{self._prefix}'"
            )
        self._target[key] = value

    def __getitem__(self, key: str) -> Token:
        return self._target[key]

    def __delitem__(self, key: str) -> None:
        del self._target[key]

    def __iter__(self):
        return iter(self._target)

    def __len__(self):
        return len(self._target)


class IOWrapper:
    __slots__ = ("_inputs", "_outputs", "_spec")

    def __init__(
        self,
        inputs: Dict[str, Token],
        outputs: Dict[str, Token],
        spec: Type[PhysicsSpec],
    ):
        self._inputs = inputs
        self._outputs = outputs
        self._spec = spec

    def __getattr__(self, name: str) -> Any:
        # 1. Check Input Ports
        if name in self._spec.input_ports:
            port_def = self._spec.input_ports[name]

            # Case A: Dynamic Map Input
            if port_def.is_map:
                # Collect all inputs that are NOT associated with a static port
                static_names = {
                    p.name for p in self._spec.input_ports.values() if not p.is_map
                }
                return {k: v for k, v in self._inputs.items() if k not in static_names}

            # Case B: Static Input
            port_name = port_def.name
            return self._inputs.get(port_name)

        # 2. Check Output Ports
        if name in self._spec.output_ports:
            port_def = self._spec.output_ports[name]

            # Case C: Dynamic Map Output
            if port_def.is_map:
                return DynamicOutputMap(self._outputs, port_def.prefix)

            # Case D: Static Output (Reading back what we wrote)
            port_name = port_def.name
            return self._outputs.get(port_name)

        raise AttributeError(
            f"'{self._spec.__name__}' IO has no port mapping for '{name}'"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_inputs", "_outputs", "_spec"):
            super().__setattr__(name, value)
            return

        # Check Output Ports
        if name in self._spec.output_ports:
            port_def = self._spec.output_ports[name]

            # Direct assignment to a Map property is not allowed (must use item assignment)
            if port_def.is_map:
                raise AttributeError(
                    f"Cannot assign to map port '{name}' directly. Use indexing (io.{name}['key'] = val)."
                )

            port_name = port_def.name
            self._outputs[port_name] = value
            return

        raise AttributeError(
            f"'{self._spec.__name__}' IO has no output port mapping for '{name}'"
        )


def implements(spec: Type[PhysicsSpec]):
    def decorator(func):
        @wraps(func)
        def wrapper(
            inputs: Dict[str, Token], node: PhysicsNode, resources: Any
        ) -> Dict[str, Token]:
            outputs: Dict[str, Token] = {}
            io = IOWrapper(inputs, outputs, spec)

            # Call the inner function. It is expected to set attributes on 'io' (populating 'outputs')
            # and return None.
            func(io, node, resources)

            return outputs

        # Attach spec metadata for introspection/docs
        setattr(wrapper, "__spec__", spec)
        return wrapper

    return decorator
~~~~~

#### Acts 4: 暴露物理层绑定工具

最后，我们将这些绑定工具添加到 `physics` 包的公共 API 中。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics/__init__.py
~~~~~
~~~~~python.old
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
~~~~~python.new
from .core import Port, PortRole, PortType, PortDef, PortDirection
from .spec import PhysicsSpec
from .binding import implements, IOWrapper, DynamicOutputMap

__all__ = [
    "Port",
    "PortRole",
    "PortType",
    "PortDef",
    "PortDirection",
    "PhysicsSpec",
    "implements",
    "IOWrapper",
    "DynamicOutputMap",
]
~~~~~

### 下一步建议

我们已经成功地将核心契约和工具集中到了 `cascade-spec` 包中。接下来的关键步骤是：

1.  **清理 `cascade-vm`**: 修改 `cascade-vm` 内部代码，使其从 `cascade-spec` 导入 `ComputeRequest` 和 `DelayRequest`，并删除本地的旧文件。
2.  **清理 `cascade-std`**: 修改所有物理节点实现，使其从 `cascade-spec` 导入 `implements` 装饰器和相关契约，并删除本地的 `kernel_tools.py` 文件。

如果你同意，我将生成执行这些清理步骤的计划。
