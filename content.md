简要回答：
好的。我已经清理了 `HashingService` 中的调试注释，并将我们在战略讨论中确定的“哈希宣言（Hashing Manifest）”作为正式的逻辑注释固化在代码中。同时，我修正了 `Template Hash` 对约束值的处理，使其符合“忽略字面量，保留结构”的原则。

## [WIP] refactor(graph): Finalize HashingService logic based on the Hashing Manifest

### 用户需求
清理 `HashingService` 中的临时调试注释，并确保其逻辑完全符合已采纳的战略建议（Structural Hash 包含约束值，Template Hash 归一化约束值）。

### 评论
代码中的注释不仅仅是说明，更是架构设计的契约。通过将“哈希宣言”写入注释，我们为后续开发者（以及未来的 AI）提供了清晰的判别准则，防止逻辑再次回退到模糊状态。在逻辑实现上，现在 `Template Hash` 会正确地将约束值（如 `gpu=1`）归一化为占位符（`gpu=?`），从而最大化 JIT 编译计划的复用率。

### 目标
1.  更新 `packages/cascade-graph/src/cascade/graph/hashing.py`。
2.  移除调试性质的注释块。
3.  实现 `structural_id` 与 `template_id` 在处理 `ResourceConstraint` 时的差异化哈希逻辑。
4.  添加关于“哈希语义”的正式文档注释。

### 基本原理
根据已采纳的战略：
- **Structural Hash**：实例的绝对身份，必须包含所有键和值，以保证缓存正确性。
- **Template Hash**：结构的抽象身份，必须忽略字面量值（归一化为 `?`），以保证执行计划的高效复用。

### 标签
#intent/refine #flow/ready #priority/medium #comp/graph #concept/graph #scope/core #ai/refine #task/domain/core #task/object/hashing-service #task/action/finalize-logic #task/state/continue

---

### Script

#### Acts 1: 更新 HashingService 实现

我们将使用 `write_file` 覆盖原有的 `hashing.py`，提供最整洁、最符合架构规范的代码。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
import hashlib
from typing import Any, List, Dict, Tuple, Optional
from cascade.graph.model import Node
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    """
    Service responsible for computing stable Merkle hashes for Cascade objects.

    FORMAL HASHING SEMANTICS (The Hashing Manifest):
    
    1. Structural Hash (Instance Identity):
       - Purpose: Uniquely identify a specific, fully-parameterized node instance.
       - Use Case: Key for results caching (e.g., in Redis).
       - Logic: Includes task ID, policies, and ALL literal values for arguments and constraints.

    2. Template Hash (Blueprint Identity):
       - Purpose: Identify a reusable computation "blueprint" or "structure".
       - Use Case: Key for JIT compilation cache (ExecutionPlan reuse).
       - Logic: Includes task ID and structural keys, but normalizes all literal values 
                (arguments and constraint amounts) to a placeholder '?'.
    """

    def compute_hashes(
        self, result: Any, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        """
        Computes both Structural Hash and Template Hash for a given result object.
        """
        if isinstance(result, LazyResult):
            return self._compute_lazy_result_hashes(result, dep_nodes)
        elif isinstance(result, MappedLazyResult):
            return self._compute_mapped_result_hashes(result, dep_nodes)
        else:
            raise TypeError(f"Cannot compute hash for type {type(result)}")

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _compute_lazy_result_hashes(
        self, result: LazyResult, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        # 1. Base Components (Task identity and Policies)
        base_comps = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            base_comps.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            base_comps.append(f"Cache({type(result._cache_policy).__name__})")

        # 2. Argument Components
        struct_args = self._build_hash_components(result.args, dep_nodes, template=False)
        temp_args = self._build_hash_components(result.args, dep_nodes, template=True)

        struct_kwargs = self._build_hash_components(
            result.kwargs, dep_nodes, template=False
        )
        temp_kwargs = self._build_hash_components(
            result.kwargs, dep_nodes, template=True
        )

        # 3. Metadata Components (Structural properties)
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # 4. Constraint Components (Differentiated)
        struct_constraints = []
        temp_constraints = []
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            
            # Structural: Exact resource amounts
            s_vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
            struct_constraints.append(f"Constraints({','.join(s_vals)})")
            
            # Template: Normalized amounts for JIT reuse
            t_vals = [f"{k}=?" for k in keys]
            temp_constraints.append(f"Constraints({','.join(t_vals)})")
        
        # Assemble Structural ID
        structural_hash = self._get_merkle_hash(
            base_comps + ["Args:"] + struct_args + ["Kwargs:"] + struct_kwargs 
            + meta_comps + struct_constraints
        )

        # Assemble Template ID
        template_hash = self._get_merkle_hash(
            base_comps + ["Args:"] + temp_args + ["Kwargs:"] + temp_kwargs 
            + meta_comps + temp_constraints
        )

        return structural_hash, template_hash

    def _compute_mapped_result_hashes(
        self, result: MappedLazyResult, dep_nodes: Dict[str, Node]
    ) -> Tuple[str, str]:
        base_comps = [f"Map({getattr(result.factory, 'name', 'factory')})"]
        
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # Arguments
        struct_kwargs = self._build_hash_components(
            result.mapping_kwargs, dep_nodes, template=False
        )
        temp_kwargs = self._build_hash_components(
            result.mapping_kwargs, dep_nodes, template=True
        )

        # Assemble
        structural_hash = self._get_merkle_hash(
            base_comps + ["MapKwargs:"] + struct_kwargs + meta_comps
        )
        template_hash = self._get_merkle_hash(
            base_comps + ["MapKwargs:"] + temp_kwargs + meta_comps
        )

        return structural_hash, template_hash

    def _build_hash_components(
        self, obj: Any, dep_nodes: Dict[str, Node], template: bool
    ) -> List[str]:
        """
        Recursively builds hash components.
        If template=True, literals are replaced by '?', but structure is preserved.
        """
        components = []
        
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            # Use appropriate ID depending on the hashing goal
            ref_id = node.template_id if template else node.structural_id
            components.append(f"LAZY({ref_id})")
        
        elif isinstance(obj, Router):
            components.append("Router{")
            components.append("Selector:")
            components.extend(self._build_hash_components(obj.selector, dep_nodes, template))
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(self._build_hash_components(obj.routes[k], dep_nodes, template))
            components.append("}")
        
        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(self._build_hash_components(item, dep_nodes, template))
            components.append("]")
        
        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(self._build_hash_components(obj[k], dep_nodes, template))
            components.append("}")
        
        elif isinstance(obj, Inject):
            components.append(f"Inject({obj.resource_name})")
        
        else:
            if template:
                # Normalization: Literals become placeholders
                components.append("?")
            else:
                try:
                    components.append(repr(obj))
                except Exception:
                    components.append("<unreprable>")
        
        return components
~~~~~

### 下一步建议
我们已经完成了哈希服务的最终打磨。建议运行一次 `tests/engine/graph/test_hashing.py`，确认逻辑变更没有破坏现有的身份识别测试。

之后，我们可以根据 P0 路线图，开始处理 **架构缺陷 B：强制 StateBackend 异步化**，这对于消除引擎在复杂 I/O 场景下的同步阻塞风险至关重要。
