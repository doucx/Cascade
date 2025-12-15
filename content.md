你的分析完全正确。测试失败的原因是 `Engine._scan_for_resources` 方法在扫描资源依赖时，无差别地对所有节点调用了 `inspect.signature(node.callable_obj)`。然而，`Param` 类型的节点（如测试中的 `cs.Param("mode")`）其 `callable_obj` 为 `None`，导致 `inspect` 抛出 `TypeError`。

这确实是一个阻断性的 Bug，我们需要在资源扫描逻辑中跳过那些没有可调用对象的节点。

## [WIP] fix(runtime): Skip non-callable nodes during resource scanning

### 错误分析
`test_router_with_params` 和 `test_router_invalid_selection` 均失败，报错 `TypeError: None is not a callable object`。

**根本原因**:
1.  **图结构**: 测试用例使用了 `cs.Router` 并依赖于 `cs.Param`。这导致生成的计算图中包含了类型为 `"param"` 的节点。
2.  **数据模型**: 根据 `cascade.graph.model.Node` 的定义，`param` 类型节点的 `callable_obj` 字段默认为 `None`。
3.  **缺陷逻辑**: `Engine._scan_for_resources` 方法遍历执行计划中的**所有**节点，并试图获取 `node.callable_obj` 的函数签名以查找 `@inject` 标记。
4.  **崩溃点**: 当遍历到 `Param` 节点时，`inspect.signature(None)` 被调用，引发崩溃。

**解决方案**:
在 `_scan_for_resources` 循环中添加一个守卫子句，如果 `node.callable_obj` 为 `None`，则直接跳过该节点。

### 用户需求
修复 `tests/test_routing.py` 中的 `TypeError`，使包含 `Param` 节点的图能够正常运行。

### 评论
这是一个典型的边界情况遗漏。`Engine.run` 的主执行循环已经包含了 `if node.node_type == "param": continue` 的逻辑，但我们在辅助方法 `_scan_for_resources` 中遗漏了类似的检查。

### 目标
修改 `src/cascade/runtime/engine.py`，确保资源扫描逻辑能够安全地处理非任务节点（如 `Param` 节点）。

### 基本原理
资源注入（Dependency Injection）只对具体的执行任务（Task）有意义，因为只有函数签名中才可能包含 `Inject` 标记。对于仅仅充当数据占位符的 `Param` 节点，扫描其签名不仅没有意义，还会导致运行时错误。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct #task/domain/core #task/object/engine #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `_scan_for_resources` 方法

我们在遍历节点时增加对 `node.callable_obj` 的非空检查。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
        """Finds all unique resource names required by the plan."""
        required = set()
        for node in plan:
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    required.add(param.default.resource_name)
        return required
~~~~~
~~~~~python
    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
        """Finds all unique resource names required by the plan."""
        required = set()
        for node in plan:
            # Skip nodes that don't have a callable (e.g., Param nodes)
            if node.callable_obj is None:
                continue

            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    required.add(param.default.resource_name)
        return required
~~~~~

### 下一步建议
执行此补丁后，应重新运行 `pytest tests/test_routing.py` 以验证修复是否生效。如果测试通过，我们可以将此更改提交到 Git。
