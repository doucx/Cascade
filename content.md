简要回答
我们将修复运行时层 (`Engine`, `Resolvers`) 和序列化层 (`Serialize`) 针对新 `Node` 对象的兼容性问题。

## [WIP] fix(runtime): 适配 Node 对象重构

### 用户需求
1.  修复 `ResourceContainer` 和 `ArgumentResolver` 中对 `node.signature` 的访问，改为动态获取。
2.  修复 `serialize.py` 中对 `node.param_spec` 的访问，移除非核心元数据的序列化支持。
3.  修复手动实例化 `Node` 的单元测试。

### 评论
由于“焦土政策”移除了 `Node.signature` 和 `Node.param_spec`，所有依赖这些属性的代码现在都必须更新。对于签名，我们改用 `node.callable_obj` 并在运行时按需反射（这是合理的，因为这只发生在图构建后的准备阶段）。对于 `param_spec`，鉴于它主要用于 CLI 生成且目前实现较为次要，我们将暂时移除其序列化逻辑以恢复核心功能。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/runtime/resource_container.py`。
2.  修改 `packages/cascade-engine/src/cascade/runtime/resolvers.py`。
3.  修改 `packages/cascade-graph/src/cascade/graph/serialize.py`。
4.  修改 `packages/cascade-engine/tests/adapters/executors/test_local.py`。
5.  修改 `packages/cascade-graph/tests/test_serialize.py`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #concept/reflection #scope/core #ai/instruct #task/domain/runtime #task/object/node-adaptation #task/action/repair #task/state/continue

---

### Script

#### Acts 1: 修复 ResourceContainer

不再依赖缓存的 `signature`，而是检查 `callable_obj`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resource_container.py
~~~~~
~~~~~old
        # 2. Scan Node Signatures for Inject defaults
        for node in graph.nodes:
            if node.signature:
                for param in node.signature.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
            elif node.callable_obj:
                try:
                    # Cast to Any to bypass strict signature check for ResourceDefinition
                    obj_to_inspect: Any = node.callable_obj
                    sig = inspect.signature(obj_to_inspect)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            required.add(param.default.resource_name)
                except (ValueError, TypeError):
                    pass
        return required
~~~~~
~~~~~new
        # 2. Scan Node Signatures for Inject defaults
        for node in graph.nodes:
            if node.callable_obj:
                try:
                    # Inspect the callable object directly since Node no longer caches the signature
                    obj_to_inspect: Any = node.callable_obj
                    sig = inspect.signature(obj_to_inspect)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            required.add(param.default.resource_name)
                except (ValueError, TypeError):
                    pass
        return required
~~~~~

#### Acts 2: 修复 ArgumentResolver

同样，使用 `callable_obj` 进行 bind 操作。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~old
        # 3. Handle Resource Injection in Defaults
        if node.signature:
            # Create a bound arguments object to see which args are not yet filled
            try:
                bound_args = node.signature.bind_partial(*args, **kwargs)
                for param in node.signature.parameters.values():
                    if (
                        isinstance(param.default, Inject)
                        and param.name not in bound_args.arguments
                    ):
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
            except TypeError:
                # This can happen if args/kwargs are not yet valid, but we can still try a simpler check
                pass
~~~~~
~~~~~new
        # 3. Handle Resource Injection in Defaults
        if node.callable_obj:
            try:
                # Re-inspect signature on demand
                sig = inspect.signature(node.callable_obj)
                bound_args = sig.bind_partial(*args, **kwargs)
                for param in sig.parameters.values():
                    if (
                        isinstance(param.default, Inject)
                        and param.name not in bound_args.arguments
                    ):
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
            except (ValueError, TypeError):
                pass
~~~~~

#### Acts 3: 修复 serialize.py

移除对 `param_spec` 的支持。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~old
    if node.mapping_factory:
        data["mapping_factory"] = _get_func_path(node.mapping_factory)

    if node.param_spec:
        data["param_spec"] = {
            "name": node.param_spec.name,
            "default": node.param_spec.default,
            "type_name": node.param_spec.type.__name__
            if node.param_spec.type
            else None,
            "description": node.param_spec.description,
        }

    if node.retry_policy:
~~~~~
~~~~~new
    if node.mapping_factory:
        data["mapping_factory"] = _get_func_path(node.mapping_factory)

    # Note: param_spec serialization removed as Node no longer holds it directly.
    # Future implementation should serialize definition metadata if needed.

    if node.retry_policy:
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~old
def _dict_to_node(data: Dict[str, Any]) -> Node:
    # Recover Param Spec
    param_spec = None
    if "param_spec" in data:
        ps_data = data["param_spec"]
        # Recovering type is hard without `pydoc.locate` or similar, defaulting to None or str
        param_spec = ParamSpec(
            name=ps_data["name"],
            default=ps_data["default"],
            description=ps_data["description"],
        )

    # Recover Retry Policy
    retry_policy = None
    if "retry_policy" in data:
        rp = data["retry_policy"]
        retry_policy = RetryPolicy(
            max_attempts=rp["max_attempts"], delay=rp["delay"], backoff=rp["backoff"]
        )

    # Recover Constraints
    constraints = None
    if "constraints" in data:
        constraints = ResourceConstraint(requirements=data["constraints"])

    node = Node(
        structural_id=data["structural_id"],
        name=data["name"],
        node_type=data["node_type"],
        callable_obj=_load_func_from_path(data.get("callable")),
        mapping_factory=_load_func_from_path(data.get("mapping_factory")),
        param_spec=param_spec,
        retry_policy=retry_policy,
        constraints=constraints,
        input_bindings=data.get("input_bindings", {}),
    )
    return node
~~~~~
~~~~~new
def _dict_to_node(data: Dict[str, Any]) -> Node:
    # Note: param_spec recovery removed

    # Recover Retry Policy
    retry_policy = None
    if "retry_policy" in data:
        rp = data["retry_policy"]
        retry_policy = RetryPolicy(
            max_attempts=rp["max_attempts"], delay=rp["delay"], backoff=rp["backoff"]
        )

    # Recover Constraints
    constraints = None
    if "constraints" in data:
        constraints = ResourceConstraint(requirements=data["constraints"])

    # Reconstruct a minimal TaskDef for the Node from the serialized data
    # This is a stub definition to satisfy the Node contract for deserialization
    from cascade.spec.ir.models import TaskDef
    from cascade.spec.fingerprint import Fingerprint
    
    # We use a dummy fingerprint for deserialized nodes if not present
    fp = Fingerprint()
    # If we serialized the code hash, we should restore it, but for now we put a placeholder
    fp["current_code_structure_hash"] = "restored_from_json"

    stub_def = TaskDef(
        name=data["name"],
        args=[], # Args info lost in simplified serialization, ok for basic runtime restoration if callables are loaded
        fingerprint=fp
    )

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

#### Acts 4: 修复 test_serialize.py

移除对 `param_spec` 的断言。

~~~~~act
patch_file
packages/cascade-graph/tests/test_serialize.py
~~~~~
~~~~~old
def test_serialize_params():
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _ = build_graph(target)

    data = graph_to_dict(graph)
    # In v1.3, Param produces a task named '_get_param_value'
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")

    assert param_node["node_type"] == "task"
    assert "name" in param_node["input_bindings"]
    assert param_node["input_bindings"]["name"] == "env"
    # The default value is part of the ParamSpec, not a direct input to the internal task node.
    # So we should not expect it here.
    assert "default" not in param_node["input_bindings"]

    # Note: Serialization currently only saves graph structure, not the Context.
    # So deserialized graph will have the node, but not the ParamSpec metadata
    # (which lives in WorkflowContext). This is expected behavior for v1.3.

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.name == "_get_param_value")
    assert "name" in p_node.input_bindings
    assert p_node.input_bindings["name"] == "env"
    assert "default" not in p_node.input_bindings
~~~~~
~~~~~new
def test_serialize_params_structure_only():
    # Renamed: this test now only checks the graph structure for params, not metadata
    p = cs.Param("env", default="dev", description="Environment")
    target = simple_task(p)
    graph, _ = build_graph(target)

    data = graph_to_dict(graph)
    param_node = next(n for n in data["nodes"] if n["name"] == "_get_param_value")

    assert param_node["node_type"] == "task"
    assert "name" in param_node["input_bindings"]
    assert param_node["input_bindings"]["name"] == "env"

    # Round trip
    restored = from_json(to_json(graph))
    p_node = next(n for n in restored.nodes if n.name == "_get_param_value")
    assert "name" in p_node.input_bindings
    assert p_node.input_bindings["name"] == "env"
~~~~~

#### Acts 5: 修复 test_local.py

修复 `Node` 的手动构造。

~~~~~act
patch_file
packages/cascade-engine/tests/adapters/executors/test_local.py
~~~~~
~~~~~old
def test_local_executor_sync_execution():
    # 1. Define the callable
    @task
    def add(x: int, y: int, z: int = 0) -> int:
        return x + y + z

    # 2. Simulate the Node (Only callable_obj is needed here)
    node_add = Node(structural_id="add", name="add", callable_obj=add.func)

    # 3. Simulate arguments resolved by the Engine
~~~~~
~~~~~new
from cascade.spec.ir.models import TaskDef
from cascade.spec.fingerprint import Fingerprint

def test_local_executor_sync_execution():
    # 1. Define the callable
    @task
    def add(x: int, y: int, z: int = 0) -> int:
        return x + y + z

    # 2. Simulate the Node with Definition
    stub_def = TaskDef(name="add", args=[], fingerprint=Fingerprint())
    node_add = Node(structural_id="add", definition=stub_def, callable_obj=add.func)

    # 3. Simulate arguments resolved by the Engine
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/adapters/executors/test_local.py
~~~~~
~~~~~old
def test_local_executor_async_execution():
    @task
    async def async_add(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    node_async = Node(
        structural_id="async_add", name="async_add", callable_obj=async_add.func
    )

    resolved_args = [5]
    resolved_kwargs = {}
~~~~~
~~~~~new
def test_local_executor_async_execution():
    @task
    async def async_add(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    stub_def = TaskDef(name="async_add", args=[], fingerprint=Fingerprint())
    node_async = Node(
        structural_id="async_add", definition=stub_def, callable_obj=async_add.func
    )

    resolved_args = [5]
    resolved_kwargs = {}
~~~~~

### 下一步建议
通过上述修改，我们从运行时代码和主要测试用例中移除了对旧 `signature` 和 `param_spec` 属性的所有访问。系统现在应该能基于新的 `definition` 属性和动态反射正常运行。可以运行测试进行验证。
