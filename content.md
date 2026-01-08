Answering this request in my capacity as a Certified ACA Protocol Interpreter.

## [WIP] fix: 修复 Compiler/Runtime 集成中的 Param 识别、DI 注入与路由剪枝问题

### 错误分析

1.  **Param 任务识别失败 (`TypeError: ... missing 'params_context'`)**:
    *   **现象**: `_get_param_value` 任务在执行时缺少 `params_context` 参数。
    *   **原因**: `IRGenerator` 默认将所有 `LazyResult` 生成为 `type="task"` 的 `NodeIR`。在 Runtime 中，`ArgumentResolver` 仅对 `ParamNode` 类型注入 `params_context`。由于 `IRGenerator` 未能识别 `_get_param_value` 并将其标记为 `type="param"`，导致 Runtime 按照普通任务处理，从而跳过了参数上下文注入。
    *   **修复**: 修改 `IRGenerator`，检测任务名称若为 `_get_param_value`，则生成 `type="param"` 的 `NodeIR`。

2.  **依赖注入 (DI) 失效 (`AttributeError: 'Inject' object has no attribute...`)**:
    *   **现象**: 任务函数接收到的参数是 `Inject` 对象本身，而非被注入的资源实例。
    *   **原因**: `IRToRuntimeAdapter` 在创建 Runtime Node 时，仅根据**输入参数 (`node_ir.inputs`)** 是否包含 `Inject` 来决定 `has_complex_inputs` 标志。然而，大多数资源注入（如 Connector、DB）是通过函数签名的**默认值**定义的。如果 `has_complex_inputs` 为 `False`，`ArgumentResolver` 会进入“快速路径”，完全跳过 DI 逻辑。
    *   **修复**: 修改 `IRToRuntimeAdapter`，在创建 Node 时检查对应的 Executable 的函数签名。如果签名中包含 `Inject` 类型的默认值，强制设置 `has_complex_inputs=True`。

3.  **路由剪枝失效 (`AssertionError: ... 'branch_b' in set()`)**:
    *   **现象**: `Router` 分支未被正确剪枝。
    *   **原因**: `IRToRuntimeAdapter` 使用 `_StubLazyResult` 重建 Router 结构。`FlowManager` 中的 `_get_node_from_instance` 方法使用严格的 `isinstance(instance, (LazyResult, MappedLazyResult))` 检查。由于 `_StubLazyResult` 不是 `LazyResult` 的子类，导致检查失败，FlowManager 无法追踪 Router 的下游分支。
    *   **修复**: 修改 `FlowManager._get_node_from_instance`，放宽类型检查，改为鸭子类型（检查是否具有 `_uuid` 属性），以兼容 `_StubLazyResult`。

### 用户需求

修复 `cascade-runtime` 切换到 Compiler 路径后导致的一系列回归错误，确保参数传递、依赖注入和控制流剪枝功能正常工作。

### 评论

这些问题揭示了从“直接 Graph 构建”切换到“IR 生成 -> 适配”模式时的语义丢失。Compiler 需要更精确地保留原始意图（如 Param 类型），Adapter 需要更智能地恢复运行时所需的元数据（如 DI 需求），而 Runtime 组件（如 FlowManager）需要对 Adapter 生成的存根对象更宽容。

### 目标

1.  修改 `cascade-compiler` 中的 `IRGenerator` 以正确识别 Param 任务。
2.  修改 `cascade-runtime` 中的 `IRToRuntimeAdapter` 以基于函数签名检测 DI 需求。
3.  修改 `cascade-runtime` 中的 `FlowManager` 以支持 `_StubLazyResult` 对象。
4.  通过所有相关回归测试。

### 基本原理

*   **IR 语义增强**: 将特殊的运行时行为（如参数获取）编码进 IR 的类型系统中，保持了编译器前后端分离的原则，同时确保后端能采取正确的特殊处理。
*   **运行时元数据恢复**: `IRToRuntimeAdapter` 作为连接静态 IR 和动态 Runtime 的桥梁，有责任利用运行时可用的额外信息（如 Python 函数对象）来填补 IR 中缺失的动态行为标志（如 `has_complex_inputs`）。
*   **鸭子类型**: Python 的动态特性允许我们在不引入循环依赖或复杂继承结构的情况下，通过接口兼容性解决 `Stub` 对象识别问题。

### 标签

#intent/fix #flow/ready #priority/high #comp/compiler #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/runtime #task/object/integration #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 IRGenerator 的 Param 识别逻辑

我们将修改 `IRGenerator`，使其在访问 `LazyResult` 时检查任务名称。如果是 `_get_param_value`，则将生成的 `NodeIR` 类型设置为 `param`。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
~~~~~
~~~~~python.old
        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type="task",
            logical_id=lr._uuid,
            inputs=inputs,
            constraints=constraints,
~~~~~
~~~~~python.new
        # Detect Param nodes
        node_type = "task"
        if task_def.name == "_get_param_value":
            node_type = "param"

        node_ir = NodeIR(
            current_node_instance_hash=node_id,
            name=task_def.name,
            task=task_def,
            type=node_type,
            logical_id=lr._uuid,
            inputs=inputs,
            constraints=constraints,
~~~~~

#### Acts 2: 修复 IRToRuntimeAdapter 的 DI 检测逻辑

我们需要增强 `IRToRuntimeAdapter`。它现在不仅要检查输入参数，还要检查对应的 Executable 函数签名，看是否有 `Inject` 默认值。这确保了通过默认参数注入资源的依赖注入（DI）机制能触发 Runtime 的复杂处理路径。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python.old
    def _create_node(self, node_ir: NodeIR) -> Node:
        # Recover policies
        retry_policy = None
~~~~~
~~~~~python.new
    def _create_node(
        self, node_ir: NodeIR, executables: Dict[str, Callable]
    ) -> Node:
        # Recover policies
        retry_policy = None
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python.old
        # Input bindings: filter out router definitions from inputs
        input_bindings = {}
        has_complex_inputs = False
        from cascade.spec.dsl.resources import Inject
        
        def check_complexity(obj):
            if isinstance(obj, Inject):
                return True
            if isinstance(obj, (list, tuple)):
                return any(check_complexity(x) for x in obj)
            if isinstance(obj, dict):
                return any(check_complexity(x) for x in obj.values())
            return False

        for k, v in node_ir.inputs.items():
            if isinstance(v, dict) and v.get("$router"):
                continue
            input_bindings[k] = v
            if not has_complex_inputs and check_complexity(v):
                has_complex_inputs = True

        # Determine Node Type
~~~~~
~~~~~python.new
        # Input bindings: filter out router definitions from inputs
        input_bindings = {}
        has_complex_inputs = False
        from cascade.spec.dsl.resources import Inject
        import inspect
        
        def check_complexity(obj):
            if isinstance(obj, Inject):
                return True
            if isinstance(obj, (list, tuple)):
                return any(check_complexity(x) for x in obj)
            if isinstance(obj, dict):
                return any(check_complexity(x) for x in obj.values())
            return False

        for k, v in node_ir.inputs.items():
            if isinstance(v, dict) and v.get("$router"):
                continue
            input_bindings[k] = v
            if not has_complex_inputs and check_complexity(v):
                has_complex_inputs = True

        # Also check the executable signature for Inject defaults
        if not has_complex_inputs:
            executable = executables.get(node_ir.current_node_instance_hash)
            if executable:
                try:
                    sig = inspect.signature(executable)
                    for param in sig.parameters.values():
                        if isinstance(param.default, Inject):
                            has_complex_inputs = True
                            break
                except (ValueError, TypeError):
                    pass

        # Determine Node Type
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/graph/adapter.py
~~~~~
~~~~~python.old
        # 1. Create Nodes
        for node_ir in ir.nodes:
            node = self._create_node(node_ir)
            self.graph.add_node(node)
            self.node_map[node.current_node_instance_hash] = node
            if node_ir.logical_id:
                self.logical_map[node_ir.logical_id] = node
~~~~~
~~~~~python.new
        # 1. Create Nodes
        for node_ir in ir.nodes:
            node = self._create_node(node_ir, executables)
            self.graph.add_node(node)
            self.node_map[node.current_node_instance_hash] = node
            if node_ir.logical_id:
                self.logical_map[node_ir.logical_id] = node
~~~~~

#### Acts 3: 修复 FlowManager 以支持 Stub 对象

放宽 `FlowManager` 对 `LazyResult` 的类型检查，使其能够识别 `IRToRuntimeAdapter` 生成的 `_StubLazyResult` 对象，从而正确进行路由分析和剪枝。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/flow.py
~~~~~
~~~~~python.old
    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        return None
~~~~~
~~~~~python.new
    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        # We use duck typing here to support _StubLazyResult from the Adapter
        # as well as real LazyResult objects.
        if hasattr(instance, "_uuid"):
            return self.instance_map.get(instance._uuid)
        return None
~~~~~

### 下一步建议

执行测试套件以验证修复：
1.  `pytest packages/cascade-library/tests/integration/test_http.py` (验证 Param)
2.  `pytest packages/cascade-library/tests/integration/test_signal_provider.py` (验证 DI)
3.  `pytest packages/cascade-runtime/tests/integration/test_engine_router_pruning.py` (验证 Router)
4.  运行完整回归测试。
