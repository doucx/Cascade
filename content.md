## [WIP] fix(core): Fix `map` execution for static inputs

### 错误分析
`test_map_basic`、`test_shell_map` 等测试失败，原因为结果为空列表或空字符串。`test_map_dynamic_input` 通过，说明动态输入工作正常。

问题根源在于 `Engine._execute_map_node` 方法中。它目前仅通过 `_resolve_inputs` 获取来自上游任务的动态输入，完全忽略了 `node.literal_inputs` 中存储的静态输入（如列表字面量）。导致当只有静态输入时，`mapped_inputs` 为空，直接返回了空列表。

### 计划
修改 `src/cascade/runtime/engine.py` 中的 `_execute_map_node` 方法，使其在解析输入时，正确地将 `node.literal_inputs` 与从上游解析的动态输入进行合并。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #comp/runtime #concept/map #scope/core #ai/instruct #task/domain/core #task/object/engine #task/action/bugfix #task/state/end

---

### Script

#### Acts 1: 修复 `_execute_map_node` 输入解析逻辑

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_map_node(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> List[Any]:
        """
        Dynamically unfolds and executes a map node.
        """
        # 1. Resolve inputs
        # The node inputs (from edges) correspond to the iterables passed to .map()
        mapped_inputs = self._resolve_inputs(node, graph, upstream_results)
        
        if not mapped_inputs:
            return []
            
        # 2. Validate input lengths
~~~~~
~~~~~python
    async def _execute_map_node(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> List[Any]:
        """
        Dynamically unfolds and executes a map node.
        """
        # 1. Resolve inputs
        # Start with static literals
        mapped_inputs = node.literal_inputs.copy()
        
        # Merge dynamic inputs from upstream
        dynamic_inputs = self._resolve_inputs(node, graph, upstream_results)
        mapped_inputs.update(dynamic_inputs)
        
        if not mapped_inputs:
            return []
            
        # 2. Validate input lengths
~~~~~
