简要回答

好的，我们开始 **Phase 5** 的第一步。我们将把构建 `GraphIR` 所需的核心静态分析工具从 v2.0 的 `cascade-graph` 迁移到 v3.0 的 `cascade-compiler` 中。这将解除编译器对旧图模型的依赖，为构建独立的 Frontend 铺平道路。

## [WIP] feat(compiler): 迁移静态分析与哈希工具至编译器

### 用户需求
为了构建独立的 Compiler Frontend，需要将 `ReflectionAnalyzer` (用于分析任务定义) 和 `HashingService` (用于计算节点实例哈希) 从 `cascade-graph` 迁移到 `cascade-compiler` 包中，并解除它们对 v2.0 `Graph/Node` 模型的依赖。

### 评论
这是一个关键的基础设施重构。
1.  **解耦**: `HashingService` 原本紧密耦合于 v2.0 的 `Node` (属性 `structural_id`)。迁移后，我们将使其兼容 v3.0 的 `NodeIR` (属性 `id`)，从而实现平滑过渡。
2.  **瘦身**: 我们只迁移计算 "Instance Hash" 的 `HashingService`，而丢弃计算 v2.0 图拓扑哈希的 `BlueprintHasher`，因为 v3.0 的拓扑结构完全不同，旧的哈希逻辑不再适用。

### 目标
1.  在 `cascade-compiler` 中创建 `utils/reflection.py`，包含 `ReflectionAnalyzer`。
2.  在 `cascade-compiler` 中创建 `utils/hashing.py`，包含适配后的 `HashingService`。
3.  更新 `cascade-compiler` 的 `utils/__init__.py` 暴露这些新工具。

### 基本原理
*   **ReflectionAnalyzer**: 它是生成 `TaskDef` (IR 的一部分) 的唯一途径。
*   **HashingService**: Compiler Frontend 在将 `LazyResult` 转换为 `NodeIR` 时，需要计算一个确定的 ID。这个 ID 的计算逻辑（哈希算法）必须与 v2.0 保持一致（或兼容），以确保逻辑的一致性。通过在 `utils` 中重用此逻辑，我们可以避免重新发明轮子。

### 标签
#intent/refine #flow/draft #priority/high #comp/compiler #scope/core #ai/instruct #task/domain/compiler #task/object/frontend #task/action/migration #task/state/begin

---

### Script

#### Acts 1: 迁移 `ReflectionAnalyzer`

我们将 `ReflectionAnalyzer` 及其依赖的 Protocol 迁移到 `cascade.compiler.utils.reflection`。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/utils/reflection.py
~~~~~
~~~~~python
import inspect
import hashlib
from typing import Any, List, Optional, Protocol

from cascade.spec.ir.models import TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.fingerprint import Fingerprint


class TaskAnalyzer(Protocol):
    """
    Protocol for components capable of analyzing a raw target object (e.g. a function)
    and producing a static Task Definition (TaskDef).
    """

    def analyze(self, target: Any) -> TaskDef: ...


class ReflectionAnalyzer(TaskAnalyzer):
    """
    A TaskAnalyzer implementation that uses Python's built-in `inspect` module
    to analyze callable objects (or Task wrappers) at runtime.
    """

    def analyze(self, target: Any) -> TaskDef:
        # Determine the underlying function and metadata source
        func = target
        mode = "blocking"

        # Check if it's a cascade.spec.task.Task wrapper
        # We perform a loose check to avoid importing cascade.spec.task.Task directly
        if hasattr(target, "func") and hasattr(target, "mode"):
            func = target.func
            mode = getattr(target, "mode", "blocking")

        if not callable(func):
            raise TypeError(
                f"Target {target} must be callable (or enclose a callable) to be analyzed."
            )

        # 1. Basic Metadata
        name = getattr(func, "__name__", "unknown")
        docstring = inspect.getdoc(func)
        is_async = inspect.iscoroutinefunction(func)

        # Extract return annotation if available
        sig = inspect.signature(func)
        return_annotation = None
        if sig.return_annotation is not inspect.Signature.empty:
            # We store the string representation for serialization safety
            return_annotation = str(sig.return_annotation)

        # 2. Analyze Arguments
        args = self._analyze_arguments(sig)

        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = structure_hash

        return TaskDef(
            name=name,
            args=args,
            fingerprint=fingerprint,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            mode=mode,
        )

    def _analyze_arguments(self, sig: inspect.Signature) -> List[ArgumentDef]:
        args = []
        for param in sig.parameters.values():
            try:
                kind = ArgumentKind[param.kind.name]
            except KeyError:
                # Fallback or unknown kind
                kind = ArgumentKind.POSITIONAL_OR_KEYWORD

            annotation = None
            if param.annotation is not inspect.Parameter.empty:
                annotation = str(param.annotation)

            default_repr = None
            if param.default is not inspect.Parameter.empty:
                # We use repr() to get a stable string representation of the default value
                try:
                    default_repr = repr(param.default)
                except Exception:
                    default_repr = "<unrepresentable>"

            args.append(
                ArgumentDef(
                    name=param.name,
                    kind=kind,
                    annotation=annotation,
                    default_value_repr=default_repr,
                )
            )
        return args

    def _compute_structure_hash(
        self,
        name: str,
        args: List[ArgumentDef],
        return_annotation: Optional[str],
        docstring: Optional[str],
        is_async: bool,
        mode: str,
    ) -> str:
        components = [f"Name:{name}"]
        components.append(f"Async:{is_async}")
        components.append(f"Mode:{mode}")
        if return_annotation:
            components.append(f"Return:{return_annotation}")

        if docstring:
            components.append(f"Doc:{docstring}")

        for arg in args:
            comp = f"Arg(Name:{arg.name},Kind:{arg.kind},Ann:{arg.annotation},Def:{arg.default_value_repr})"
            components.append(comp)

        fingerprint_str = "|".join(components)
        return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()
~~~~~

#### Acts 2: 迁移并适配 `HashingService`

我们将 `HashingService` 迁移到 `cascade.compiler.utils.hashing`。
关键修改：在 `_build_hash_components` 中，使用 `getattr(node, "id", ...)` 来同时兼容 v3.0 的 `NodeIR` (属性为 `id`) 和 v2.0 的 `Node` (属性为 `structural_id`)。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/utils/hashing.py
~~~~~
~~~~~python
import hashlib
from typing import Any, List, Dict

from cascade.spec.ir.models import TaskDef
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    """
    Service responsible for computing a stable Merkle hash for a node instance.
    This is the `Instance Hash`, which uniquely identifies a specific, fully-parameterized
    node instance.
    """

    def compute_node_instance_hash(
        self,
        definition: TaskDef,
        result: Any,  # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, Any],  # Values can be NodeIR (v3) or Node (v2)
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        code_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{code_hash}"]

        # 2. Purity Salt
        # Get purity from the Task wrapper if available, else assume False (Impure) for safety
        task_obj = getattr(result, "task", None) or getattr(result, "factory", None)
        is_pure = getattr(task_obj, "pure", False) if task_obj else False

        if not is_pure:
            # Impure tasks are instance-identity based.
            # We use the LazyResult's UUID as a salt.
            components.append(f"Salt({result._uuid})")

        # 3. Policies
        if getattr(result, "_retry_policy", None):
            rp = result._retry_policy
            components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if getattr(result, "_cache_policy", None):
            components.append(f"Cache({type(result._cache_policy).__name__})")

        # 4. Bindings (Instance Arguments)
        if isinstance(result, MappedLazyResult):
            components.append("MapKwargs:")
            components.extend(
                self._build_hash_components(result.mapping_kwargs, dep_nodes)
            )
        else:
            components.append("Args:")
            components.extend(self._build_hash_components(result.args, dep_nodes))
            components.append("Kwargs:")
            components.extend(self._build_hash_components(result.kwargs, dep_nodes))

        # 5. Metadata
        if getattr(result, "_condition", None):
            components.append("Condition:PRESENT")

        # 6. Constraints
        if getattr(result, "_constraints", None):
            reqs = result._constraints.requirements
            keys = sorted(reqs.keys())
            s_vals = [f"{k}={reqs[k]}" for k in keys]
            components.append(f"Constraints({','.join(s_vals)})")

        return self._get_merkle_hash(components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components(self, obj: Any, dep_nodes: Dict[str, Any]) -> List[str]:
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            # Duck-typing: Support both v3 NodeIR (id) and v2 Node (structural_id)
            node_id = getattr(node, "id", getattr(node, "structural_id", str(node)))
            components.append(f"LAZY({node_id})")

        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(self._build_hash_components(obj.selector, dep_nodes))
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(self._build_hash_components(obj.routes[k], dep_nodes))
            components.append("}")

        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(self._build_hash_components(item, dep_nodes))
            components.append("]")

        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(self._build_hash_components(obj[k], dep_nodes))
            components.append("}")

        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")

        else:
            try:
                components.append(repr(obj))
            except Exception:
                components.append("<unreprable>")

        return components
~~~~~

#### Acts 3: 暴露工具

更新 `cascade.compiler.utils` 包的导出。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/utils/__init__.py
~~~~~
~~~~~python
from .naming import PhysicalIdGenerator
from .reflection import ReflectionAnalyzer, TaskAnalyzer
from .hashing import HashingService

__all__ = [
    "PhysicalIdGenerator",
    "ReflectionAnalyzer",
    "TaskAnalyzer",
    "HashingService",
]
~~~~~

### 下一步建议
基础设施已经就位。下一步是 **Act 2: 建立 Frontend 脚手架**，创建 `cascade.compiler.frontend` 包并实现核心的 `IRGenerator`，开始消费 `LazyResult` 并产出 `GraphIR`。这将是连接用户侧 API 和编译器后端的关键桥梁。
