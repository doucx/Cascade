简要回答
我们之前的诊断直击要害：`ParamNode` 的特殊处理导致了 `ArgumentResolver` 的逻辑分叉，进而引发了一系列依赖解析问题。我将执行战略重构，废除 `ParamNode` 的特殊地位，使其继承自 `TaskNode` 并通过标准执行管线运行。

## [WIP] refactor(core): 统一 ParamNode 执行模型以修复依赖解析问题

### 错误分析
当前的 `DependencyMissingError` 及其引发的 TCO 覆盖失效，根源在于 `ArgumentResolver` 对 `ParamNode` 进行了特殊且不完整的“偷跑”处理。
1.  **特殊处理的代价**：Resolver 试图直接解析并写入 `ParamNode` 的结果，而不是让它进入 `Executor`。这导致它通过 `isinstance` 检查绕过了标准的参数覆盖（Input Override）逻辑，因此在 TCO 递归（Jump）时忽略了传入的新值。
2.  **属性缺失**：`ParamNode` 作为 `Node` 的直接子类，缺乏 `callable_obj` 等标准属性，导致工具链（如 CLI 生成器）试图访问时崩溃。

### 用户需求
将 `ParamNode` 彻底重构为 `TaskNode` 的子类（或具有相同行为的实体），使其逻辑行为与普通任务一致：
1.  拥有 `callable_obj`（指向 `_get_param_value`）。
2.  由 `Executor` 负责执行，而不是在 `Resolver` 中被特殊处理。
3.  受 `ArgumentResolver` 的标准逻辑（包括 Override 检查）管理。

### 评论
这是一个高价值的架构简化。通过移除特例，我们不仅修复了特定 Bug，还减少了核心代码的复杂度，增强了系统的多态性设计。

### 目标
1.  修改 `cascade/graph/model.py`：让 `ParamNode` 继承自 `TaskNode`。
2.  修改 `cascade/graph/build.py`：在构建 `ParamNode` 时注入 `_get_param_value` 作为其 `_callable`。
3.  修改 `cascade/graph/serialize.py`：支持 `ParamNode` 的 `callable` 序列化与反序列化。
4.  修改 `cascade/runtime/resolvers.py`：**删除**针对 `ParamNode` 的特殊解析分支，依赖底部的通用上下文注入逻辑。

### 基本原理
将 `ParamNode` 视为执行 `_get_param_value` 函数的标准任务。`ArgumentResolver` 的职责归一化为“准备参数”，其中 `ParamNode` 需要的参数是隐式的 `params_context`。由于标准任务解析逻辑已经包含完善的“Input Override vs Edge”优先级判断，复用此逻辑将自动修复 TCO 问题。

### 标签
#intent/refine #intent/fix #flow/ready #priority/critical #comp/engine #concept/node #scope/core #ai/instruct #task/domain/core #task/object/param-node #task/action/unify-execution #task/state/begin

---

### Script

#### Acts 1: 重构数据模型 (Model)
让 `ParamNode` 继承自 `TaskNode`，从而获得 `_callable` 属性和 `TaskNode` 的身份。同时移除原本硬编码的 `callable_obj` 属性方法。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class ParamNode(Node):
    """Represents an external parameter injection."""

    # We store the ParamSpec here explicitly for type safety
    from cascade.spec.input import ParamSpec

    param_spec: Optional[ParamSpec] = None

    # Optimization flag, required for consistent interface
    has_complex_inputs: bool = False

    @property
    def callable_obj(self) -> Optional[Callable]:
        # Param nodes use a special internal task to retrieve values
        from cascade.internal.inputs import _get_param_value
        return _get_param_value.func
~~~~~
~~~~~python.new
@dataclass
class ParamNode(TaskNode):
    """Represents an external parameter injection."""

    # We store the ParamSpec here explicitly for type safety
    from cascade.spec.input import ParamSpec

    param_spec: Optional[ParamSpec] = None

    # Optimization flag, required for consistent interface
    has_complex_inputs: bool = False
    
    # Inherits callable_obj property from TaskNode
~~~~~

#### Acts 2: 更新图构建器 (Build)
在构建 `ParamNode` 时，显式传入 `_callable` 参数（`_get_param_value.func`）。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
                node = ParamNode(
                    structural_id=node_hash,
                    definition=task_def,
                    node_type="param",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_spec=param_spec,
                    has_complex_inputs=True,
                )
            else:
~~~~~
~~~~~python.new
                node = ParamNode(
                    structural_id=node_hash,
                    definition=task_def,
                    node_type="param",
                    _callable=result.task.func,
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_spec=param_spec,
                    has_complex_inputs=True,
                )
            else:
~~~~~

#### Acts 3: 更新序列化逻辑 (Serialize)
更新反序列化逻辑，确保 `ParamNode` 重建时也能获得 `_callable`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
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
            has_complex_inputs=True, # ParamNode always needs the complex path
        )
    else:
~~~~~
~~~~~python.new
    elif node_type == "param":
        # Note: We don't currently serialize the full ParamSpec, 
        # so restored ParamNodes will have param_spec=None. 
        # This is acceptable for simple visualization/analysis, 
        # but execution of restored ParamNodes might need the spec context.
        node = ParamNode(
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="param",
            _callable=_load_func_from_path(data.get("callable")),
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            has_complex_inputs=True, # ParamNode always needs the complex path
        )
    else:
~~~~~

#### Acts 4: 修复参数解析器 (Resolvers)
这是最关键的一步。删除 `ArgumentResolver.resolve` 顶部针对 `ParamNode` 的特殊处理块。这将迫使 `ParamNode` 走下方的通用逻辑路径。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python.old
    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Optional[Dict[str, Any]] = None,
        input_overrides: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        from cascade.graph.model import ParamNode
        
        # Handle ParamNode as a special case that doesn't execute but resolves from context
        if isinstance(node, ParamNode):
            param_name = node.param_spec.name if node.param_spec else node.name
            params = user_params or {}
            if param_name in params:
                # The "result" of a ParamNode is its value from the params dict.
                # We must put this into the state_backend so downstream tasks can find it.
                val = params[param_name]
                await state_backend.put_result(node.structural_id, val)
                # Param nodes themselves don't have args/kwargs to execute, but we return the value
                # for consistency, though it's the side effect on state_backend that matters.
                return [val], {}

        # FAST PATH: If node is simple (no Injects, no magic params), skip the ceremony.
        if not node.has_complex_inputs:
~~~~~
~~~~~python.new
    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Optional[Dict[str, Any]] = None,
        input_overrides: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # FAST PATH: If node is simple (no Injects, no magic params), skip the ceremony.
        if not node.has_complex_inputs:
~~~~~

### 下一步建议
这种底层变更通常只有在运行时才能验证完整性。建议立即运行之前失败的测试用例：
1. `tests/e2e/runtime/test_tco_param_override.py` (验证 TCO 覆盖是否生效)
2. `packages/cascade-spec/tests/spec/test_routing.py` (验证 Param 是否正常工作)
3. `packages/cascade-sdk/tests/tools/test_cli.py` (验证 Node 属性访问)
