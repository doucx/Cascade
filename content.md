简要回答
我们将升级 `cascade-spec` 和 `cascade-std` 中的基础设施，引入 `Port.Map` 概念和相应的运行时支持，以处理动态端口（如 Bleacher 的参数和 Allocator 的 Grant）。

## [WIP] feat: PIDL 基础设施升级 - 支持动态端口映射

### 用户需求
1.  修改 `PortDef` 和 `Port` 工厂，支持定义动态端口映射 (`MapInput`, `MapOutput`)。
2.  升级 `IOWrapper`，使其在访问 Map 类型的端口时，能够动态收集未匹配的输入或提供支持前缀校验的输出代理。

### 评论
引入 "Static First, Dynamic Fallback" 策略是对 PIDL 的重要补充。它不仅解决了 `Bleacher` 和 `Allocator` 的燃眉之急，也为未来任何需要灵活接口的 IC 提供了标准模式。这种模式在保持核心契约强类型的同时，保留了必要的动态灵活性。

### 目标
1.  更新 `packages/cascade-spec/src/cascade/spec/physics/core.py`。
2.  更新 `packages/cascade-std/src/cascade/std/kernel_tools.py`。

### 基本原理
*   **Schema 层 (`core.py`)**: 增加 `is_map` 标记。对于 Map 类型的端口，`name` 字段不再代表单一物理端口，而是作为一个占位符。增加 `prefix` 字段用于输出端口的命名空间约束。
*   **Runtime 层 (`kernel_tools.py`)**:
    *   **Input Map**: 运行时计算 `set(inputs.keys()) - set(static_port_names)`，返回剩余输入的字典。
    *   **Output Map**: 返回一个 `DynamicOutputMap` 代理对象，拦截 `__setitem__` 操作，验证前缀并写入底层的 `outputs` 字典。

### 标签
#intent/refine #flow/ready #priority/high #comp/std #comp/interfaces #concept/spec #scope/core #ai/instruct #task/domain/core #task/object/kernel-infra #task/action/upgrade #task/state/continue

---

### Script

#### Acts 1: 升级核心定义 (The Core Laws)

修改 `core.py`，为 `PortDef` 增加动态属性，并添加 `MapInput` / `MapOutput` 工厂方法。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics/core.py
~~~~~
~~~~~python.old
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
~~~~~python.new
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
        type_hint: Any = PortType.Any,
        is_map: bool = False,
        prefix: str = ""
    ):
        self.name = name
        self.direction = direction
        self.role = role
        self.type_hint = type_hint
        self.is_map = is_map
        self.prefix = prefix

    def __set_name__(self, owner, name):
        # We allow the attribute name to act as a fallback or strict mapping validation later.
        pass

    def __repr__(self):
        return f"PortDef(name='{self.name}', dir={self.direction}, role={self.role}, map={self.is_map})"


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

    @staticmethod
    def MapInput(role: PortRole = PortRole.DATA, type: Any = PortType.Any) -> PortDef:
        """
        Defines a dynamic dictionary of input ports. 
        It captures all inputs that are NOT matched by static Port.Inputs.
        """
        return PortDef("*", PortDirection.INPUT, role, type, is_map=True)

    @staticmethod
    def MapOutput(prefix: str = "", role: PortRole = PortRole.DATA, type: Any = PortType.Any) -> PortDef:
        """
        Defines a dynamic dictionary of output ports.
        Allows writing to any port name starting with the given prefix.
        """
        return PortDef("*", PortDirection.OUTPUT, role, type, is_map=True, prefix=prefix)
~~~~~

#### Acts 2: 升级运行时工具 (The Runtime Tools)

修改 `kernel_tools.py`，实现 `DynamicOutputMap` 并在 `IOWrapper` 中处理 Map 逻辑。

~~~~~act
write_file
packages/cascade-std/src/cascade/std/kernel_tools.py
~~~~~
~~~~~python
from functools import wraps
from typing import Dict, Any, Type, TypeVar, MutableMapping
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physics import PhysicsSpec, PortDirection

T = TypeVar("T", bound=PhysicsSpec)


class DynamicOutputMap(MutableMapping):
    """
    Proxy for writing to dynamic output ports with prefix validation.
    """
    def __init__(self, target_dict: Dict[str, Token], prefix: str):
        self._target = target_dict
        self._prefix = prefix

    def __setitem__(self, key: str, value: Token) -> None:
        if not key.startswith(self._prefix):
             raise ValueError(f"Dynamic port '{key}' does not match required prefix '{self._prefix}'")
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
    """
    A zero-copy view over the input and output dictionaries.
    Translates attribute access to dictionary lookups based on the Spec.
    Supports "Static First, Dynamic Fallback" for map ports.
    """
    __slots__ = ("_inputs", "_outputs", "_spec")

    def __init__(self, inputs: Dict[str, Token], outputs: Dict[str, Token], spec: Type[PhysicsSpec]):
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
                    p.name for p in self._spec.input_ports.values() 
                    if not p.is_map
                }
                return {
                    k: v for k, v in self._inputs.items() 
                    if k not in static_names
                }
            
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

        raise AttributeError(f"'{self._spec.__name__}' IO has no port mapping for '{name}'")

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

        raise AttributeError(f"'{self._spec.__name__}' IO has no output port mapping for '{name}'")


def implements(spec: Type[PhysicsSpec]):
    """
    Decorator that adapts a kernel function to use the typed IO interface.
    
    Transforms:
        def my_kernel(inputs, node, resources) -> Dict
    Into:
        def my_kernel(io, node, resources) -> None
        
    The wrapper handles the creation of the outputs dictionary and returns it.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(inputs: Dict[str, Token], node: PhysicsNode, resources: Any) -> Dict[str, Token]:
            outputs: Dict[str, Token] = {}
            io = IOWrapper(inputs, outputs, spec)
            
            # Call the inner function. It is expected to set attributes on 'io' (populating 'outputs')
            # and return None.
            func(io, node, resources)
            
            return outputs
        
        # Attach spec metadata for introspection/docs
        wrapper.__spec__ = spec
        return wrapper
    return decorator
~~~~~

### 下一步建议
基础设施升级完毕。现在我们可以生成一个新的计划，利用这些新能力来重构 `Bleacher` 和 `DiscreteAllocator`。

接下来的步骤：
1.  修改 `cascade.std.specs.triad.BleacherSpec` 使用 `Port.MapInput`。
2.  修改 `cascade.std.specs.resource.DiscreteAllocatorSpec` 使用 `Port.MapOutput`。
3.  重构 `standard_bleacher` 和 `discrete_allocator` 内核函数。
