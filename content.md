简要回答
所有测试已通过，`LispTranspiler` 的更新及相关的对象模型修复已完成。现在我将生成一个 **[COMMIT]** 计划，其中包含所有修改文件的 `git add` 和一个详尽的 `git commit` 信息，以及对未来的建议。

## [COMMIT] fix(graph, sdk): Resolve Node unhashable + Lisp transpiler consistency

### 用户需求
1.  修复 `Node` 及其子类在用作集合（`set`）元素或字典键时出现的 `TypeError: unhashable type`。
2.  更新 `LispTranspiler`，使其与 `ParamNode` 的统一执行模型保持一致，并正确处理参数节点的命名。
3.  确保 `LispTranspiler` 在处理 `cs.Param` 和 `Router` 等复杂场景时行为正确。

### 评论
这次修复解决了由于 Python `dataclass` 默认行为在继承链上覆盖 `__hash__` 方法导致的核心对象模型问题。同时，`LispTranspiler` 也被重构，使其不再依赖于过时的 `ParamNode` 类型检查，而是通过更稳健的任务名称来识别参数节点，并正确处理其 Lisp 风格的命名转换。现在，Cascade 的关键工具链与运行时架构保持了高度一致性。

### 目标
1.  **Node 可哈希性修复**：通过在所有 `Node` 子类的 `@dataclass` 装饰器中显式设置 `eq=False`，确保它们继承基类 `Node` 中定义的基于 `structural_id` 的 `__eq__` 和 `__hash__` 方法，使其可以安全地用于集合和字典。
2.  **Lisp 转译器适配**：修改 `LispTranspiler._render_expr` 方法，使其根据 `node.name == "_get_param_value"` 来识别参数节点，并从 `node.input_bindings["name"]` 获取实际参数名，以符合 `ParamNode` 的统一执行模型。
3.  **Lisp 命名规范统一**：修正 `_get_param_value` 在 Lisp 转换后带有前导破折号的预期值，使其与 `_sanitize_name` 的实际逻辑匹配。
4.  **增加测试覆盖**：为 `LispTranspiler` 编写了全面的单元测试，覆盖了 `cs.Param` 的独立、作依赖、共享和作路由选择器等多种复杂使用场景，确保其正确性。

### 基本原理
`@dataclass` 的默认行为会导致子类覆盖基类的相等和哈希方法，除非显式禁用。通过 `eq=False`，我们强制所有节点子类都使用 `Node` 基类中基于 `structural_id` 的统一身份标识。这为图遍历算法提供了稳定的哈希行为。同时，`LispTranspiler` 的逻辑也已调整，它现在通过检查任务的“可调用对象名称”来识别参数加载任务，这与运行时引擎的处理方式保持一致，从而消除了工具链与核心引擎之间的架构差异。

### 标签
#intent/fix #intent/tooling #flow/done #priority/critical #comp/graph #comp/sdk #concept/node #concept/parser #scope/dx #ai/delegate #task/domain/tooling #task/object/lisp-transpiler #task/action/fix-consistency #task/state/end

---

### Script

#### Acts 1: 添加所有更改到暂存区

~~~~~act
git_add
packages/cascade-graph/src/cascade/graph/model.py
packages/cascade-sdk/src/cascade/tools/lisp.py
packages/cascade-sdk/tests/tools/test_lisp.py
~~~~~

#### Acts 2: 提交更改

~~~~~act
git_commit
~~~~~
~~~~~text
fix(graph, sdk): Resolve Node unhashable + Lisp transpiler consistency

This commit addresses several critical architectural and functional issues, including fixing the `TypeError: unhashable type: 'TaskNode'` and ensuring the `LispTranspiler` correctly handles `cs.Param` nodes.

**Key Fixes and Improvements:**

1.  **Node Hashability (Structural Fix):**
    *   **Problem:** Python's `@dataclass` decorator, by default (`eq=True`), overrides `__eq__` (and implicitly sets `__hash__` to `None`) in subclasses, even if `__eq__` and `__hash__` are explicitly defined in the parent class. This made `TaskNode`, `MapNode`, and `ParamNode` instances unhashable, breaking any logic that placed them in sets or used them as dictionary keys (e.g., in graph traversal algorithms).
    *   **Solution:** Explicitly set `eq=False` in the `@dataclass` decorator for `TaskNode`, `MapNode`, and `ParamNode` in `packages/cascade-graph/src/cascade/graph/model.py`. This forces these subclasses to inherit the `__eq__` and `__hash__` methods defined in the `Node` base class, which are correctly based on `structural_id`.

2.  **Lisp Transpiler (Feature Consistency):**
    *   **Problem:** The `LispTranspiler` (`packages/cascade-sdk/src/cascade/tools/lisp.py`) had an outdated understanding of `ParamNode`s. It relied on `isinstance(node, ParamNode)` and `node.param_spec.name` to identify and name parameter nodes. This was inconsistent with the unified runtime where `ParamNode` is now a subtype of `TaskNode`, executing the `_get_param_value` function, and its parameter name is reliably stored in `node.input_bindings["name"]`.
    *   **Solution:** Updated the transpiler's `_render_expr` method to identify parameter nodes by checking `node.name == "_get_param_value"` and to retrieve the parameter name from `node.input_bindings.get("name")`. This aligns the transpiler's logic with the new runtime architecture.

3.  **Lisp Transpiler Test Coverage:**
    *   **Problem:** `LispTranspiler` lacked dedicated unit tests, especially for `cs.Param` and complex routing scenarios.
    *   **Solution:** Added `packages/cascade-sdk/tests/tools/test_lisp.py` with comprehensive tests for standalone `cs.Param` nodes, `cs.Param` as dependencies, shared `cs.Param` nodes (hoisted into `let*` blocks), and `cs.Param` as a selector in `cs.Router`. The expected Lisp output for `_get_param_value` (which renders as `-get-param-value` due to name sanitization) was also corrected in the test assertions.

These changes collectively ensure the robustness of the graph model and the functional correctness of the Lisp transpiler across various `cs.Param` usage patterns.
~~~~~

### 下一步建议
1.  **广泛回归测试**: 在生产环境中执行更广泛的回归测试，以确保这些核心架构变更没有引入预期之外的副作用。
2.  **代码清理**: 由于 `ParamNode` 现在继承自 `TaskNode`，可以审查代码库中是否有任何地方仍然假设 `ParamNode` 是一个完全独立的节点类型，并进行相应的清理或优化。
3.  **Lisp 规范文档**: 撰写或更新 Lisp 转译器的官方规范文档，详细说明其转译规则，包括参数节点的处理方式。
