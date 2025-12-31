## [WIP] feat(arch): 架构硬化 - 阶段1：语义与数据的丰富化

### 用户需求
在架构硬化流程的阶段1，核心需求是丰富 Spec 和 Compiler 的数据模型，使其能够承载和传递“上下文”与“策略”信息，从而通过之前创建的 TDD 测试。

### 评论
当前的 `NodeIR` 和 `Blueprint` 过于贫瘠，导致 Compiler Frontend 丢弃了用户的重试、资源等策略，且无法表达参数注入。我们需要引入 `ContextOperand`, `ResourceOperand` 以及结构化的 `ExecutionPolicy`。这是一次“正规军”式的架构升级，为后续 Middleware 化的 VM 打下数据基础。

### 目标
1.  **Spec 升级**: 在 `cascade-spec` 中定义 `ContextOperand`, `ResourceOperand`, `ExecutionPolicy` 等核心数据结构。
2.  **IR 升级**: 更新 `NodeIR` 以包含 `policy` 和支持 `InjectionIR`。
3.  **Frontend 升级**: 让 Compiler Frontend 能够解析 `Inject/Param` 并提取策略，不再做有损转换。
4.  **Backend 升级**: 让 Compiler Backend 能够编译新的 IR 及其策略到指令集。

### 基本原理
通过将策略和上下文依赖显式化为数据（IR/Blueprint fields），我们解耦了“定义”与“执行”。VM 不再需要魔法般地猜测如何重试或注入参数，而是执行明确的指令和策略对象。

### 标签
#intent/build #flow/ready #priority/critical #comp/spec #comp/compiler #scope/core #task/domain/core #task/object/hardening-enrichment #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: Spec 基础设施 (Policy & IRI)

首先创建策略定义的独立模块，并更新 IR 模型。

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/policy.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class RetryPolicySpec:
    """Serializable specification for retry logic."""
    max_attempts: int = 0
    delay: float = 0.0
    backoff: float = 1.0

@dataclass
class ExecutionPolicy:
    """Aggregate policy for task execution."""
    retry: Optional[RetryPolicySpec] = None
    resources: Dict[str, Any] = field(default_factory=dict)
    timeouts: Dict[str, float] = field(default_factory=dict)  # e.g., {"execution": 60.0}
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint


class EdgeKind(str, Enum):
~~~~~
~~~~~python.new
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint
from cascade.spec.policy import ExecutionPolicy


class EdgeKind(str, Enum):
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass(frozen=True)
class TaskDef:
~~~~~
~~~~~python.new
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass
class InjectionIR:
    """Represents a dependency injection request in the IR."""
    resource_name: str


@dataclass(frozen=True)
class TaskDef:
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
~~~~~
~~~~~python.new
@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    policy: Optional[ExecutionPolicy] = None
~~~~~

#### Acts 2: Spec Blueprint 升级 (Operands & Instruction Policy)

丰富 Operand 类型，并在 Blueprint 层面重导出 Policy，满足测试要求。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/blueprint.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional
from cascade.spec.constraint import ResourceConstraint


@dataclass
class Operand:
    pass


@dataclass
class Literal(Operand):
    value: Any


@dataclass
class Register(Operand):
    index: int


@dataclass
class Instruction:
~~~~~
~~~~~python.new
from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.policy import ExecutionPolicy, RetryPolicySpec


@dataclass
class Operand:
    pass


@dataclass
class Literal(Operand):
    value: Any


@dataclass
class Register(Operand):
    index: int


@dataclass
class ContextOperand(Operand):
    """Loads a value from the execution context (e.g. user params)."""
    scope: str  # e.g., 'params', 'env'
    key: str


@dataclass
class ResourceOperand(Operand):
    """Loads a resource instance from the resource container."""
    name: str


@dataclass
class Instruction:
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/blueprint.py
~~~~~
~~~~~python.old
@dataclass
class Call(Instruction):
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None
    structure_hash: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass
class Call(Instruction):
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None  # Deprecated: prefer policy.resources
    structure_hash: Optional[str] = None
    policy: Optional[ExecutionPolicy] = None
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/blueprint.py
~~~~~
~~~~~python.old
@dataclass
class MapCall(Instruction):
    """Represents a map operation over iterable inputs."""

    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None
    structure_hash: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass
class MapCall(Instruction):
    """Represents a map operation over iterable inputs."""

    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None
    structure_hash: Optional[str] = None
    policy: Optional[ExecutionPolicy] = None
~~~~~

#### Acts 3: Compiler Frontend 升级 (Extract Logic)

修改 Frontend 以提取策略并识别 Inject。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
from typing import Any, Dict, List, cast, Callable
from dataclasses import dataclass

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.spec.compiler_result import CompilationResult
from .analysis.reflection import ReflectionAnalyzer
from .hashing import HashingService
~~~~~
~~~~~python.new
from typing import Any, Dict, List, cast, Callable
from dataclasses import dataclass
import inspect

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind, InjectionIR
from cascade.spec.compiler_result import CompilationResult
from cascade.spec.policy import ExecutionPolicy, RetryPolicySpec
from cascade.spec.resource import Inject
from .analysis.reflection import ReflectionAnalyzer
from .hashing import HashingService
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
    def _visit_lazy_result(self, obj: LazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}

        for arg in obj.args:
~~~~~
~~~~~python.new
    def _extract_policy(self, obj: LazyResult | MappedLazyResult) -> ExecutionPolicy:
        policy = ExecutionPolicy()
        
        # 1. Retry
        if obj._retry_policy:
            policy.retry = RetryPolicySpec(
                max_attempts=obj._retry_policy.max_attempts,
                delay=obj._retry_policy.delay,
                backoff=obj._retry_policy.backoff
            )
            
        # 2. Constraints -> Resources
        if obj._constraints and obj._constraints.requirements:
            policy.resources.update(obj._constraints.requirements)
            
        return policy

    def _resolve_injections(self, func: Callable, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Looks for Inject markers in defaults and promotes them to explicit kwargs."""
        new_kwargs = kwargs.copy()
        try:
            # We must inspect the raw function to get default values which might be Inject objects
            sig = inspect.signature(func)
            for name, param in sig.parameters.items():
                if isinstance(param.default, Inject) and name not in new_kwargs:
                    new_kwargs[name] = InjectionIR(resource_name=param.default.resource_name)
        except (ValueError, TypeError):
            # Signature inspection failed, possibly not a python function (e.g. C extension)
            pass
            
        return new_kwargs

    def _visit_lazy_result(self, obj: LazyResult) -> str:
        if obj._uuid in self._visited_lazy_uuids:
            return self._visited_lazy_uuids[obj._uuid]

        dep_shims: Dict[str, NodeIDShim] = {}

        for arg in obj.args:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        if node_id not in self.nodes:
            literal_args = [
                arg for arg in obj.args if not isinstance(arg, (LazyResult, MappedLazyResult))
            ]
            literal_kwargs = {
                k: val for k, val in obj.kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }

            node = NodeIR(id=node_id, definition=task_def, args=literal_args, kwargs=literal_kwargs)
            self.nodes[node_id] = node

        for i, arg in enumerate(obj.args):
~~~~~
~~~~~python.new
        if node_id not in self.nodes:
            literal_args = [
                arg for arg in obj.args if not isinstance(arg, (LazyResult, MappedLazyResult))
            ]
            
            # Use raw task mapping, but we might check for Injection objects in args too?
            # cascade usually supports injection in kwargs/defaults.
            # We need to scan obj.kwargs AND merge with signature defaults for Injections.
            
            # 1. Start with explicit kwargs
            raw_kwargs = obj.kwargs.copy()
            
            # 2. Resolve defaults from signature (promote defaults to explicit InjectionIR)
            full_kwargs = self._resolve_injections(obj.task.func, raw_kwargs)
            
            literal_kwargs = {}
            for k, val in full_kwargs.items():
                if isinstance(val, (LazyResult, MappedLazyResult)):
                    continue
                # If it's a raw Inject object (explicitly passed), convert to IR
                if isinstance(val, Inject):
                    literal_kwargs[k] = InjectionIR(resource_name=val.resource_name)
                else:
                    literal_kwargs[k] = val

            policy = self._extract_policy(obj)

            node = NodeIR(
                id=node_id, 
                definition=task_def, 
                args=literal_args, 
                kwargs=literal_kwargs,
                policy=policy
            )
            self.nodes[node_id] = node

        for i, arg in enumerate(obj.args):
~~~~~

#### Acts 4: Compiler Backend 升级 (Operand Construction)

修改 Backend 以识别 `InjectionIR` 并生成 `ResourceOperand`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.spec.blueprint import Blueprint, Call, MapCall, Register, Literal, Operand, JumpIfFalse
from .optimizer import ExecutionPlan
~~~~~
~~~~~python.new
from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind, InjectionIR
from cascade.spec.blueprint import (
    Blueprint, Call, MapCall, Register, Literal, Operand, JumpIfFalse, ResourceOperand
)
from .optimizer import ExecutionPlan
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        args: List[Operand] = [Literal(val) for val in node.args]
        kwargs: Dict[str, Operand] = {k: Literal(v) for k, v in node.kwargs.items()}
        control_dependency_reg: Any = None

        # 1a. Overlay dependencies from Edges
~~~~~
~~~~~python.new
    def _convert_to_operand(self, val: Any) -> Operand:
        if isinstance(val, InjectionIR):
            return ResourceOperand(name=val.resource_name)
        return Literal(val)

    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        args: List[Operand] = [self._convert_to_operand(val) for val in node.args]
        kwargs: Dict[str, Operand] = {k: self._convert_to_operand(v) for k, v in node.kwargs.items()}
        control_dependency_reg: Any = None

        # 1a. Overlay dependencies from Edges
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
        if node.meta.get("is_map"):
            instr = MapCall(
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
                # Note: Constraints on Map nodes are not yet propagated to MapCall.
            )
        else:
            instr = Call(
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
            )
        self._instructions.append(instr)
~~~~~
~~~~~python.new
        if node.meta.get("is_map"):
            instr = MapCall(
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
                policy=node.policy, 
            )
        else:
            instr = Call(
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
                policy=node.policy,
            )
        self._instructions.append(instr)
~~~~~

### 下一步建议
我们已经完成了数据流的丰富化。现在的 Spec 定义了新概念，Frontend 提取了它们，Backend 编译了它们。TDD 测试套件现在应该能够通过。此时 VM 暂时还不知道如何执行 `ResourceOperand` 或 `policy`，因此下一步我们将进入 **阶段 2: VM 的管道化改造**，利用这些新数据来实现中间件执行模型。
