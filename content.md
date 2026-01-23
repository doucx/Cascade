好的，我明白了。我们已经完成了核心路线图中的重构，但遗漏了对旧的 `cascade-execution-graph` 包的适配，导致它仍然在使用已被废弃的 `NodeIR.inputs` 字段。这是一个关键的疏漏，必须立即修正，以确保整个系统的端到端一致性。

我将生成一个计划来修复 `IRToRuntimeAdapter`，使其完全符合新的 `NodeIR` 规约。

## [WIP] fix: Align legacy graph executor with new NodeIR spec

### 用户需求
`IRToRuntimeAdapter` in `cascade-execution-graph` 需要被更新，以从新的 `NodeIR.args` 和 `NodeIR.kwargs` 字段读取数据，而不是从现在已经不存在的 `NodeIR.inputs` 字段。

### 评论
这是一个关键的收尾工作，它确保了我们宏大的基础重构能够覆盖到系统的所有角落，包括为了兼容性而保留的旧执行器。完成这一步后，整个 Cascade 生态系统将在一个新的、统一且无损的 IR 规约下运作。

### 目标
1.  修改 `IRToRuntimeAdapter` 的 `_create_node` 方法，使其能够从 `node_ir.args` 和 `node_ir.kwargs` 中正确地构建 `input_bindings`。
2.  修改 `IRToRuntimeAdapter` 的 `_create_edges` 方法，使其能够从 `node_ir.args` 和 `node_ir.kwargs` 中正确地识别数据依赖并创建相应的边。

### 基本原理
我们将遵循在编译器重构中被证明是行之有效的模式：在处理输入之前，首先将 `node_ir.args` (使用其索引作为键) 和 `node_ir.kwargs` 合并成一个临时的 `all_inputs` 字典。这使得后续处理依赖关系和字面量绑定的循环逻辑可以保持简洁和统一，只需将对 `node_ir.inputs` 的引用改为对这个新的 `all_inputs` 字典的引用即可。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/ir #scope/core #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 更新 IRToRuntimeAdapter 以适配新的 IR 规约

我们将对 `adapter.py` 文件进行两次精确的 `patch` 操作，分别更新 `_create_node` 和 `_create_edges` 方法。

~~~~~act
patch_file
packages/cascade-execution-graph/src/cascade/execution/graph/model/adapter.py
~~~~~
~~~~~python.old
        # Input bindings: filter out router definitions and dependencies
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

            # If it's a direct dependency string, don't add to bindings
            if self._is_dependency(v):
                continue

            input_bindings[k] = v
            if not has_complex_inputs and check_complexity(v):
                has_complex_inputs = True
~~~~~
~~~~~python.new
        # Input bindings: filter out router definitions and dependencies
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

        # Create a unified view of all inputs
        all_inputs = {str(i): v for i, v in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        for k, v in all_inputs.items():
            if isinstance(v, dict) and v.get("$router"):
                continue

            # If it's a direct dependency string, don't add to bindings
            if self._is_dependency(v):
                continue

            input_bindings[k] = v
            if not has_complex_inputs and check_complexity(v):
                has_complex_inputs = True
~~~~~

~~~~~act
patch_file
packages/cascade-execution-graph/src/cascade/execution/graph/model/adapter.py
~~~~~
~~~~~python.old
    def _create_edges(self, node_ir: NodeIR, target_node: Node):
        # 1. Data Edges & Routers
        for arg_name, value in node_ir.inputs.items():
            if self._is_dependency(value):
                # Simple Data Dependency (Node ID ref)
                source_node = self.node_map[value]
~~~~~
~~~~~python.new
    def _create_edges(self, node_ir: NodeIR, target_node: Node):
        # Create a unified view of all inputs
        all_inputs = {str(i): v for i, v in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        # 1. Data Edges & Routers
        for arg_name, value in all_inputs.items():
            if self._is_dependency(value):
                # Simple Data Dependency (Node ID ref)
                source_node = self.node_map[value]
~~~~~

### 下一步建议
在应用此修复后，最关键的步骤是运行完整的测试套件 (`pytest`)。我们期望这能解决剩余的兼容性问题，并使所有 `77` 个之前失败的测试全部通过。这将最终验证我们的基础重构在整个技术栈中是完整且一致的。
