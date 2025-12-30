谢谢你提供所有需要的文件内容。我已经准备好执行重构了。

我们将分两步走：

1.  **定义 `Node` 的子类体系**：在 `cascade-graph/model.py` 中引入 `TaskNode`, `ParamNode` 等子类。
2.  **更新 `GraphBuilder`**：在 `cascade-graph/build.py` 中，根据输入对象的不同，实例化相应的 `Node` 子类。
3.  **修复 SDK 和 Engine 中的类型访问**：由于有了具体的子类，我们可以使用 `isinstance` 来安全地访问特定属性，这将直接解决 `pyright` 报错。

这个计划将非常具体和具有针对性。

## [WIP] refactor: 实现 Node 的显式多态化层次结构

### 用户需求
根据“白板重构”计划，将 `Node` 类重构为抽象基类，并为不同类型的图实体（Task, Param, Map 等）提供具体的强类型子类。

### 评论
当前 `Node` 类通过动态附加属性（如 `param_spec`）来模拟多态，这种“隐式约定”在静态分析下非常脆弱。通过显式的类层次结构，我们可以利用 `isinstance` 作为类型保护，让编译器和开发者都能清晰地知道某个节点具备哪些属性。

### 目标
1.  在 `cascade-graph` 中定义 `Node` (ABC), `TaskNode`, `ParamNode`, `MapNode`。
2.  更新 `GraphBuilder`，使其根据输入的 `LazyResult` 或 `Param` 类型产生对应的子类实例。
3.  利用 `isinstance` 修复 `cascade-sdk` 和 `cascade-engine` 中的类型安全问题。

### 基本原理
这是一次从“基于字符串类型判断”到“基于类身份判断”的转变。它将运行时的不确定性转化为编译时的确定性。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/graph #comp/sdk #comp/engine #concept/graph-model #scope/core
#ai/brainstorm
#task/domain/core
#task/object/node-hierarchy
#task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: 定义 Node 子类体系

我们首先修改 `cascade-graph/model.py`，将 `Node` 拆分为一个基类和三个子类。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class Node:
    # Stable identifier for the node instance in the graph.
    # Computed from TaskDef fingerprint + Instance configuration (bindings, policies)
    structural_id: str

    # The static definition of the task.
    # Single Source of Truth for name, signature, mode, etc.
    definition: TaskDef

    # The actual python executable object.
    # This is NOT part of the definition (it's runtime state), but checked here for convenience.
    callable_obj: Optional[Callable] = None

    # Node-specific type ("task", "map", "param") - might be merged into definition later?
    # For now, it distinguishes how the definition is APPLIED.
    node_type: str = "task"

    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Mapping logic (only for node_type='map')
    mapping_factory: Optional[Any] = None

    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # Optimization flag
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        # SHORTCUT for debugging/logging, but code should prefer definition.name where possible
        return self.definition.name
~~~~~
~~~~~python.new
@dataclass
class Node:
    """Base class for all nodes in the Cascade graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str

    # The static definition of the task.
    definition: TaskDef

    # Node-specific type ("task", "map", "param")
    # Kept for serialization and legacy checks, but logic should prefer isinstance.
    node_type: str = "task"

    # Instance-specific configuration common to most executable nodes
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def callable_obj(self) -> Optional[Callable]:
        """Polymorphic accessor for the executable object."""
        return None


@dataclass
class TaskNode(Node):
    """Represents a standard executable task."""

    # The actual python executable object.
    _callable: Optional[Callable] = None
    
    # Optimization flag
    has_complex_inputs: bool = False

    @property
    def callable_obj(self) -> Optional[Callable]:
        return self._callable


@dataclass
class MapNode(Node):
    """Represents a mapped task execution."""

    mapping_factory: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        # For map nodes, the factory is the closest thing to a callable
        return self.mapping_factory


@dataclass
class ParamNode(Node):
    """Represents an external parameter injection."""
    
    # We store the ParamSpec here explicitly for type safety
    from cascade.spec.input import ParamSpec
    param_spec: Optional[ParamSpec] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        # Param nodes use a special internal task to retrieve values
        from cascade.internal.inputs import _get_param_value
        return _get_param_value.func
~~~~~

#### Acts 2: 更新 GraphBuilder 以实例化子类

接下来，我们修改 `cascade-graph/build.py`，让它能够识别并创建正确的节点类型。我们需要特别注意 `_get_param_value` 这个特殊任务，它是 `ParamNode` 的标志。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
            # Note: execution_mode is now part of task_def (definition.mode)
            node = Node(
                structural_id=node_hash,
                definition=task_def,
                callable_obj=result.task.func,
                node_type="task",
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
            self.registry._registry[node_hash] = node
~~~~~
~~~~~python.new
            # Note: execution_mode is now part of task_def (definition.mode)
            if result.task.func is _get_param_value.func:
                # Retrieve the ParamSpec from the global context to attach to the node
                from cascade.context import get_current_context
                
                # The arg at index 0 is the param name
                param_name = input_bindings.get("0") or input_bindings.get("name")
                param_spec = None
                if param_name:
                    ctx = get_current_context()
                    # Linear scan is okay for build time, or we could optimize context lookup
                    for spec in ctx.get_all_specs():
                        if spec.name == param_name:
                            # We import inside to avoid top-level circular imports if possible, 
                            # though ParamSpec is imported in ParamNode definition
                            from cascade.spec.input import ParamSpec
                            if isinstance(spec, ParamSpec):
                                param_spec = spec
                            break

                node = ParamNode(
                    structural_id=node_hash,
                    definition=task_def,
                    node_type="param",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_spec=param_spec
                )
            else:
                node = TaskNode(
                    structural_id=node_hash,
                    definition=task_def,
                    _callable=result.task.func,
                    node_type="task",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    has_complex_inputs=has_complex,
                )
            self.registry._registry[node_hash] = node
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
            node = Node(
                structural_id=node_hash,
                definition=task_def,
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry._registry[node_hash] = node
~~~~~
~~~~~python.new
            node = MapNode(
                structural_id=node_hash,
                definition=task_def,
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry._registry[node_hash] = node
~~~~~

#### Acts 3: 修复序列化逻辑

`serialize.py` 中的 `_dict_to_node` 也需要更新，以支持反序列化为正确的子类。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
    node = Node(
        structural_id=data["structural_id"],
        definition=stub_def,
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
        mapping_factory=_load_func_from_path(data.get("mapping_factory")),
        retry_policy=retry_policy,
        constraints=constraints,
        input_bindings=data.get("input_bindings", {}),
    )
    return node
~~~~~
~~~~~python.new
    node_type = data["node_type"]
    input_bindings = data.get("input_bindings", {})
    
    if node_type == "map":
        node = MapNode(
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="map",
            mapping_factory=_load_func_from_path(data.get("mapping_factory")),
            retry_policy=retry_policy,
            cache_policy=result._cache_policy if False else None, # Serialization of cache policy not implemented yet
            constraints=constraints,
            input_bindings=input_bindings,
        )
    elif node_type == "param":
        # Note: We don't currently serialize the full ParamSpec, 
        # so restored ParamNodes will have param_spec=None. 
        # This is acceptable for simple visualization/analysis, 
        # but execution of restored ParamNodes might need the spec context.
        node = ParamNode(
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="param",
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
        )
    else:
        # Default to TaskNode
        node = TaskNode(
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="task",
            _callable=_load_func_from_path(data.get("callable")),
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            # has_complex_inputs is an optimization flag, safe to default False on restore
            has_complex_inputs=False, 
        )
    return node
~~~~~

#### Acts 4: 修复 Lisp 转译器的类型报错

最后，我们修复 `lisp.py`，现在我们可以安全地使用 `isinstance(node, ParamNode)` 并访问 `param_spec` 了。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/lisp.py
~~~~~
~~~~~python.old
    def _render_expr(self, node: Node) -> str:
        parts = []

        # Function Name
        func_name = self._sanitize_name(node.name)
        if node.node_type == "map":
            parts.append(f"map {func_name}")
        elif node.node_type == "param":
            p_name = node.param_spec.name if node.param_spec else "?"
            return f'(param "{p_name}")'
        else:
            parts.append(func_name)
~~~~~
~~~~~python.new
    def _render_expr(self, node: Node) -> str:
        parts = []

        from cascade.graph.model import MapNode, ParamNode

        # Function Name
        if isinstance(node, MapNode):
            func_name = self._sanitize_name(node.definition.name)
            parts.append(f"map {func_name}")
        elif isinstance(node, ParamNode):
            # Safe access with fallback if param_spec is missing (e.g. from restore)
            p_name = node.param_spec.name if node.param_spec else "unknown"
            return f'(param "{p_name}")'
        else:
            func_name = self._sanitize_name(node.name)
            parts.append(func_name)
~~~~~

### 下一步建议
我们已经完成了核心的重构工作。接下来，我们需要验证：
1.  **运行现有测试**：确保新的类层次结构没有破坏现有的图构建和执行逻辑。
2.  **`pyright` 检查**：确认 `ParamNode` 和 `param_spec` 相关的报错已经消除。

如果一切顺利，我们将拥有一个更健壮、类型安全且易于扩展的图模型。
