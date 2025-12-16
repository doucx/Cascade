好的，我们已经完成了代码清理。现在是时候将这些改进作为一个完整的逻辑单元提交了。

我将生成一个 `[COMMIT]` 计划。

## [COMMIT] fix(core): 清理代码审查中发现的技术债务

### 用户需求
将之前计划中完成的代码清理和修复工作（针对 `http.py`, `__init__.py`, 和 `engine.py`）作为一个原子提交记录到版本控制中。

### 评论
这次提交有效地偿还了代码审查中发现的技术债务。通过移除冗余代码、修正导出规范和简化死代码，我们提升了代码库的健康度、可读性和可维护性，为未来的开发工作奠定了更坚实的基础。

### 目标
创建一个 Git 提交，该提交包含所有三个文件的修复，并附有一个清晰的提交信息，解释每个修复的内容和动机。

### 基本原理
这三项修复都源于同一次代码审查，共同服务于“提升代码质量”这一目标。将它们合并到一次提交中，可以保持 Git 历史的整洁和逻辑性，将相关的清理工作作为一个独立的工作单元来记录。

### 标签
#intent/fix #flow/ready #priority/medium #comp/core #comp/runtime #scope/dx #ai/instruct #task/domain/cleanup #task/object/code-review #task/action/fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存已修复的文件

我们将所有修改过的文件添加到 Git 暂存区。

~~~~~act
git_add
src/cascade/providers/http.py
src/cascade/__init__.py
src/cascade/runtime/engine.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，我们执行 `git commit`，并附上详细的提交信息，说明本次提交包含的修复内容。

~~~~~act
git_commit
~~~~~
~~~~~text
fix(core): Clean up technical debt from code review

This commit addresses several issues identified during code review, improving code quality, consistency, and correctness.

Key fixes:
1.  **`providers/http.py`:** Removed redundant `HttpResponse` class and a duplicate `_http_task` definition. The file now contains only the correct, safe `SimpleHttpResponse` implementation, eliminating ambiguity and potential for incorrect usage.

2.  **`__init__.py`:** Removed the `"shell"` provider from the static `__all__` export list. This aligns the module with Python best practices, as `shell` is loaded dynamically via `__getattr__` and should not be part of the static API surface.

3.  **`runtime/engine.py`:** Simplified the `_execute_map_node` method by removing a dead code path. The `if hasattr(factory, "map_item")` check was redundant and would never evaluate to True, so it has been removed to improve clarity and logical flow.
~~~~~

### 下一步建议
我们已经成功地完成了代码库的清理工作，测试套件结构也已优化。现在我们的基础非常稳固。

根据我们的开发路线图和之前的讨论，下一个最高价值的目标是提供一流的开发者工具。我建议我们开始实现 **`cs.visualize(target)`** 功能。它能将复杂的计算图以 Graphviz DOT 格式输出，这将极大地帮助我们（以及未来的用户）调试和理解工作流。如果你同意，我将开始制定实现 `cs.visualize` 的计划。
