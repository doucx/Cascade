好的，我们继续。

现在，我将执行一个**故意的、破坏性的重构**。这一步是 TDD “红-绿-重构”循环中至关重要的一环：我们主动打破现有实现，以确保我们的测试（安全网）能够正确地捕捉到这种回归，从而进入 **RED** 状态。

我的计划是简化 `cascade-graph` 包中的 `HashingService`，彻底移除 `template_id` 的概念，使其只负责生成包含所有字面量参数的 `structural_id`（即实例哈希）。这将导致引擎的 JIT 计划缓存失效，因为 `add(1, 2)` 和 `add(3, 4)` 将不再共享同一个缓存键。

这将使我们上一步创建的 `test_engine_reuses_plan_for_structurally_identical_graphs` 测试用例失败，为我们接下来引入新的、更优越的 `BlueprintHasher` 铺平道路。

## [WIP] refactor: Simplify HashingService to only produce instance hashes

### 用户需求
根据阶段四的路线图，需要对 `HashingService` 进行重构，剥离其计算“模板哈希”(`template_id`)的职责，使其职责单一化，仅用于计算包含所有字面量参数的“实例哈希”(`structural_id`)。

### 评论
这是一个关键的、战略性的步骤。通过简化 `HashingService`，我们为引入一个独立的、职责更清晰的 `BlueprintHasher` 服务创造了空间。这是一个故意的破坏性更改，旨在通过 TDD 流程引导我们走向一个更健壮的架构。移除 `template_id` 将暂时破坏引擎的 JIT 计划缓存，并使我们新添加的集成测试失败，从而将测试套件置于预期的 **RED** 状态。

### 目标
1.  修改 `cascade.graph.model.Node`，移除 `template_id` 字段。
2.  重构 `cascade.graph.hashing.HashingService`，移除所有与 `template` 模式相关的逻辑，使其 `compute_structural_hash` 方法成为唯一功能。
3.  更新 `cascade.graph.build.GraphBuilder`，使其适应 `HashingService` 的新接口，并不再向 `Node` 写入 `template_id`。
4.  修改 `cascade.runtime.strategies.graph.GraphExecutionStrategy` 中的缓存逻辑，使其暂时依赖 `structural_id`，从而暴露缓存失效的问题。

### 基本原理
遵循单一职责原则，`HashingService` 的核心职责应该是为节点实例生成唯一的、可用于结果缓存的身份标识。计算可复用执行计划的“蓝图身份”是一个完全不同的关注点，它不应该与 `HashingService` 耦合。本次重构将强制分离这两个概念，为后续实现一个专门的 `BlueprintHasher` 奠定基础。

### 标签
#intent/refine #flow/ready #priority/critical #comp/graph #comp/engine #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/plan-caching #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 从数据模型中移除 `template_id`

首先，我们从核心的 `Node` 数据模型中移除 `template_id` 字段，这是一个明确的架构信号。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
@dataclass
class Node:
    """
    Represents a node in the computation graph template.

    A Node defines 'what' to execute (the callable) and 'how' to get its arguments
    (bindings or edges), but it DOES NOT contain the runtime data itself.
    """

    structural_id: str
    name: str
    template_id: str = ""  # Structural hash (ignoring literals)

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~
~~~~~python
@dataclass
class Node:
    """
    Represents a node in the computation graph template.

    A Node defines 'what' to execute (the callable) and 'how' to get its arguments
    (bindings or edges), but it DOES NOT contain the runtime data itself.
    """

    structural_id: str
    name: str

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
~~~~~

#### Acts 2: 简化 `HashingService`

现在，重构 `HashingService`，移除所有双重哈希逻辑，使其只专注于生成 `structural_id`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
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
        struct_args = self._build_hash_components(
            result.args, dep_nodes, template=False
        )
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
            base_comps
            + ["Args:"]
            + struct_args
            + ["Kwargs:"]
            + struct_kwargs
            + meta_comps
            + struct_constraints
        )

        # Assemble Template ID
        template_hash = self._get_merkle_hash(
            base_comps
            + ["Args:"]
            + temp_args
            + ["Kwargs:"]
            + temp_kwargs
            + meta_comps
            + temp_constraints
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
            components.extend(
                self._build_hash_components(obj.selector, dep_nodes, template)
            )
            components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                components.append(f"Key({k})->")
                components.extend(
                    self._build_hash_components(obj.routes[k], dep_nodes, template)
                )
            components.append("}")

        elif isinstance(obj, (list, tuple)):
            components.append("List[")
            for item in obj:
                components.extend(
                    self._build_hash_components(item, dep_nodes, template)
                )
            components.append("]")

        elif isinstance(obj, dict):
            components.append("Dict{")
            for k in sorted(obj.keys()):
                components.append(f"{k}:")
                components.extend(
                    self._build_hash_components(obj[k], dep_nodes, template)
                )
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
~~~~~python
class HashingService:
    """
    Service responsible for computing a stable Merkle hash for a node instance.
    This is the `Instance Hash`, which uniquely identifies a specific, fully-parameterized
    node instance. It is used for results caching and node de-duplication within a graph.
    """

    def compute_structural_hash(self, result: Any, dep_nodes: Dict[str, Node]) -> str:
        """
        Computes the Structural Hash (Instance Hash) for a given result object.
        """
        if isinstance(result, LazyResult):
            return self._compute_lazy_result_hash(result, dep_nodes)
        elif isinstance(result, MappedLazyResult):
            return self._compute_mapped_result_hash(result, dep_nodes)
        else:
            raise TypeError(f"Cannot compute hash for type {type(result)}")

    def _get_merkle_hash(self, components: List[str]) -> str:
        """Computes a stable hash from a list of string components."""
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _compute_lazy_result_hash(
        self, result: LazyResult, dep_nodes: Dict[str, Node]
    ) -> str:
        # 1. Base Components (Task identity and Policies)
        base_comps = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            base_comps.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if result._cache_policy:
            base_comps.append(f"Cache({type(result._cache_policy).__name__})")

        # 2. Argument Components (Always structural)
        struct_args = self._build_hash_components(result.args, dep_nodes)
        struct_kwargs = self._build_hash_components(result.kwargs, dep_nodes)

        # 3. Metadata Components (Structural properties)
        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # 4. Constraint Components (Always structural)
        struct_constraints = []
        if result._constraints:
            keys = sorted(result._constraints.requirements.keys())
            s_vals = [f"{k}={result._constraints.requirements[k]}" for k in keys]
            struct_constraints.append(f"Constraints({','.join(s_vals)})")

        # Assemble Structural ID
        return self._get_merkle_hash(
            base_comps
            + ["Args:"]
            + struct_args
            + ["Kwargs:"]
            + struct_kwargs
            + meta_comps
            + struct_constraints
        )

    def _compute_mapped_result_hash(
        self, result: MappedLazyResult, dep_nodes: Dict[str, Node]
    ) -> str:
        base_comps = [f"Map({getattr(result.factory, 'name', 'factory')})"]

        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
        if result._dependencies:
            meta_comps.append(f"Deps:{len(result._dependencies)}")

        # Arguments (Always structural)
        struct_kwargs = self._build_hash_components(result.mapping_kwargs, dep_nodes)

        # Assemble
        return self._get_merkle_hash(
            base_comps + ["MapKwargs:"] + struct_kwargs + meta_comps
        )

    def _build_hash_components(
        self, obj: Any, dep_nodes: Dict[str, Node]
    ) -> List[str]:
        """
        Recursively builds hash components, always including literal values.
        """
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            # The reference is always to the full structural ID of the dependency
            components.append(f"LAZY({node.structural_id})")

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

#### Acts 3: 更新 `GraphBuilder` 以适应新模型

接下来，更新 `GraphBuilder` 以使用新的 `HashingService` API 和 `Node` 模型。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # 2. Compute hashes using HashingService
        structural_hash, template_hash = self.hashing_service.compute_hashes(
            result, dep_nodes
        )

        # 3. Hash-consing: Query registry FIRST before doing more work
        node = self.registry.get(structural_hash)
        created_new = False

        if not node:
            created_new = True

            # Extract bindings
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            sig = None
            if result.task.func:
                try:
                    sig = inspect.signature(result.task.func)
                except (ValueError, TypeError):
                    pass

            # Robustly determine complexity to enable FAST PATH in ArgumentResolver
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.internal.inputs import _get_param_value

            has_complex = False

            # 1. Check for Runtime Context Injection (Special internal tasks)
            if result.task.func is _get_param_value.func:
                has_complex = True

            # 2. Check for Implicit Injection in Signature Defaults
            if not has_complex and sig:
                has_complex = any(
                    isinstance(p.default, InjectMarker) for p in sig.parameters.values()
                )

            # 3. Check for Explicit Injection in Bindings (recursively)
            if not has_complex:

                def is_complex_value(v):
                    if isinstance(v, InjectMarker):
                        return True
                    if isinstance(v, list):
                        return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict):
                        return any(is_complex_value(x) for x in v.values())
                    return False

                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            node = Node(
                structural_id=structural_hash,
                template_id=template_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
~~~~~
~~~~~python
        # 2. Compute structural hash using HashingService
        structural_hash = self.hashing_service.compute_structural_hash(
            result, dep_nodes
        )

        # 3. Hash-consing: Query registry FIRST before doing more work
        node = self.registry.get(structural_hash)
        created_new = False

        if not node:
            created_new = True

            # Extract bindings
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            sig = None
            if result.task.func:
                try:
                    sig = inspect.signature(result.task.func)
                except (ValueError, TypeError):
                    pass

            # Robustly determine complexity to enable FAST PATH in ArgumentResolver
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.internal.inputs import _get_param_value

            has_complex = False

            # 1. Check for Runtime Context Injection (Special internal tasks)
            if result.task.func is _get_param_value.func:
                has_complex = True

            # 2. Check for Implicit Injection in Signature Defaults
            if not has_complex and sig:
                has_complex = any(
                    isinstance(p.default, InjectMarker) for p in sig.parameters.values()
                )

            # 3. Check for Explicit Injection in Bindings (recursively)
            if not has_complex:

                def is_complex_value(v):
                    if isinstance(v, InjectMarker):
                        return True
                    if isinstance(v, list):
                        return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict):
                        return any(is_complex_value(x) for x in v.values())
                    return False

                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            node = Node(
                structural_id=structural_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # 2. Compute hashes using HashingService
        structural_hash, template_hash = self.hashing_service.compute_hashes(
            result, dep_nodes
        )

        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            return Node(
                structural_id=structural_hash,
                template_id=template_hash,
                name=f"map({getattr(result.factory, 'name', 'factory')})",
                node_type="map",
                mapping_factory=result.factory,
~~~~~
~~~~~python
        # 2. Compute structural hash using HashingService
        structural_hash = self.hashing_service.compute_structural_hash(
            result, dep_nodes
        )

        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            return Node(
                structural_id=structural_hash,
                name=f"map({getattr(result.factory, 'name', 'factory')})",
                node_type="map",
                mapping_factory=result.factory,
~~~~~

#### Acts 4: 故意破坏引擎的计划缓存

最后，修改 `GraphExecutionStrategy`，使其使用现在包含字面量的 `structural_id` 作为缓存键，这将导致我们的测试失败。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                target_node = instance_map[current_target._uuid]
                cache_key = target_node.template_id or target_node.structural_id

                # 2. Resolve Plan (with caching)
                if cache_key in self._template_plan_cache:
~~~~~
~~~~~python
                target_node = instance_map[current_target._uuid]
                cache_key = target_node.structural_id

                # 2. Resolve Plan (with caching)
                if cache_key in self._template_plan_cache:
~~~~~

### 下一步建议

我们已经成功地重构了 `HashingService` 并移除了 `template_id`，这应该会导致 `test_plan_caching` 测试失败。

现在，我们处于 TDD 流程的 **RED** 状态。下一步是回到 **GREEN** 状态，但要用一种新的、更好的方式。

我建议立即开始实现 `BlueprintHasher` 服务，并更新 `Engine` 以使用它来缓存执行计划。这将修复我们刚刚“制造”的失败，并最终完成阶段四的核心目标。如果你同意，我将着手生成实现 `BlueprintHasher` 的计划。
