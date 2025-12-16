简要回答
这是一个非常低级的参数传递错误。在之前的重构中，我确实忽略了将 `params` 这一关键参数从 `_execute_node_with_policies` 透传给新拆分出来的 `_execute_node_internal`。

`_execute_node_internal` 内部需要使用 `params` 来支持 `.map()` 的递归执行（因为子任务也需要这些全局参数），所以必须修复函数签名和调用点。

## [WIP] fix(core): 修复 Engine 重构导致的参数丢失问题

### 错误分析
在 `src/cascade/runtime/engine.py` 中，`_execute_node_internal` 尝试使用变量 `params`，但在其函数签名中并没有定义该参数。这是因为在将其从 `_execute_node_with_policies` 拆分出来时，遗漏了 `params` 的透传。这直接导致了所有涉及 `.map()` 的操作（因为只有 `.map()` 逻辑用到了 `params`）抛出 `NameError`。

### 用户需求
修复 `NameError: name 'params' is not defined`，确保所有测试尤其是 `.map()` 相关的测试能通过。

### 评论
这是一个典型的重构回归问题。幸运的是，测试套件立即捕获了它。修复非常直接。

### 目标
修改 `src/cascade/runtime/engine.py`，更新 `_execute_node_with_policies` 的调用逻辑和 `_execute_node_internal` 的签名，加上缺失的 `params` 参数。

### 基本原理
简单地补全缺失的参数传递路径。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #scope/core #task/domain/runtime #task/object/engine #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 Engine 参数传递

同时更新调用点和函数定义。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Acquire resources (this may block)
        await self.resource_manager.acquire(requirements)
        
        try:
            return await self._execute_node_internal(
                node, graph, upstream_results, active_resources, run_id, requirements
            )
        finally:
            # Always release resources
~~~~~
~~~~~python
        # Acquire resources (this may block)
        await self.resource_manager.acquire(requirements)
        
        try:
            return await self._execute_node_internal(
                node, graph, upstream_results, active_resources, run_id, params, requirements
            )
        finally:
            # Always release resources
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_node_internal(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        requirements: Dict[str, Any], # Passed for logging if needed
    ) -> Any:
        task_start_time = time.time()
~~~~~
~~~~~python
    async def _execute_node_internal(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        requirements: Dict[str, Any], # Passed for logging if needed
    ) -> Any:
        task_start_time = time.time()
~~~~~

### 下一步建议
这次修复后，所有测试应该都能通过。建议运行完整测试套件，确认无误后提交本次关于资源感知调度的完整变更。
