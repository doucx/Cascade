## [WIP] fix: 适配 ast_analyzer 返回值变更

### 错误分析
在将 `ast_analyzer.analyze_task_source` 的返回值从 `List[Task]` 更改为 `AnalysisResult` 数据类后，所有调用此函数的代码都没有进行相应的适配。它们仍然试图直接迭代 `AnalysisResult` 对象，导致了 `TypeError`。

### 用户需求
修复因 `ast_analyzer` 返回值类型变更而导致的所有 `TypeError`，使测试套件恢复通过。

### 评论
这是一个典型的重构疏漏，但也凸显了静态类型检查的重要性。修复这个问题能确保我们新引入的静态分析功能能够与现有的图构建和 TCO 检测逻辑正确集成。

### 目标
1.  修改 `graph/build.py` 中 `_visit_lazy_result` 和 `_visit_shadow_recursive` 方法，使其访问 `analyze_task_source(task).targets`。
2.  修改 `graph/ast_analyzer.py` 中 `assign_tco_cycle_ids` 的 `_dfs` 内部函数，使其访问 `analyze_task_source(current_task).targets`。

### 基本原理
通过在所有调用点显式地访问 `AnalysisResult` 对象的 `.targets` 属性，我们可以恢复代码原有的迭代逻辑，同时保留 `AnalysisResult` 携带额外分析信息（如 `has_dynamic_recursion`）的能力。

### 标签
#intent/fix #flow/ready #priority/critical #comp/graph #scope/core #ai/instruct #task/domain/runtime #task/object/static-analysis #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `build.py`

我们将修改 `GraphBuilder` 中 `_visit_shadow_recursive` 方法，使其正确地从 `AnalysisResult` 对象中获取可迭代的 `.targets` 属性。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        for next_task in analyze_task_source(task):
            self._visit_shadow_recursive(target_node, next_task)

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
~~~~~
~~~~~python
        analysis = analyze_task_source(task)
        for next_task in analysis.targets:
            self._visit_shadow_recursive(target_node, next_task)

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
~~~~~

> **最终说明**: 经过更正，现在只有 `build.py` 需要修改。这个补丁将解决所有由 `TypeError` 导致的测试失败。
