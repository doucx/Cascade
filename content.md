Excellent catch. You've found a classic refactoring error. My apologies, in rewriting `resolvers.py` I completely removed the `ConstraintResolver` class, which is still needed by `NodeProcessor`.

The `ImportError` is entirely my fault. I will generate a plan to fix this immediately by restoring the missing class.

## [WIP] fix(engine): 恢复被误删的 ConstraintResolver 类

### 错误分析
在 `[WIP] refactor(core): 适配 Engine 与 Resolver 到新数据模型` 计划中，当使用 `write_file` 重写 `packages/cascade-engine/src/cascade/runtime/resolvers.py` 文件时，我只包含了重构后的 `ArgumentResolver`，却遗漏了该文件中原有的、并且仍然被 `NodeProcessor` 依赖的 `ConstraintResolver` 类。这导致 `from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver` 语句在 `processor.py` 中失败，从而引发了 `ImportError`。

### 用户需求
修复 `ImportError: cannot import name 'ConstraintResolver' from 'cascade.runtime.resolvers'`，使测试可以正常运行。

### 评论
这是一个简单的疏忽，但它完全阻断了开发流程。修复这个问题将使我们能够继续验证核心重构的正确性。`ConstraintResolver` 的逻辑与 `literal_inputs` 无关，因此恢复其原始实现即可。

### 目标
1.  将 `ConstraintResolver` 类添加回 `resolvers.py` 文件中。

### 基本原理
使用 `patch_file` 操作，在 `ArgumentResolver` 类定义的末尾追加回完整的 `ConstraintResolver` 类定义。这是一种最小化、最精确的修复方式。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/resolver #scope/core #ai/instruct #task/domain/core #task/object/engine-resolver #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 恢复 ConstraintResolver

我们将 `ConstraintResolver` 的实现追加回 `resolvers.py` 文件。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]

        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)
~~~~~
~~~~~python
    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]

        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)


class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        constraint_manager: Any = None,
    ) -> Dict[str, Any]:
        resolved = {}

        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            for res, amount in node.constraints.requirements.items():
                if isinstance(amount, (LazyResult, MappedLazyResult)):
                    if state_backend.has_result(amount._uuid):
                        resolved[res] = state_backend.get_result(amount._uuid)
                    else:
                        raise DependencyMissingError(
                            node.id, f"constraint:{res}", amount._uuid
                        )
                else:
                    resolved[res] = amount

        # 2. Resolve Global constraints
        if constraint_manager:
            extra = constraint_manager.get_extra_requirements(node)
            resolved.update(extra)

        return resolved
~~~~~

### 下一步建议
执行此修复后，`ImportError` 应该会解决。请再次尝试运行 `pytest`。我们可能会遇到由本次重构引入的新的、逻辑上的错误，但至少导入问题应该已经清除了。
