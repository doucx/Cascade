明白了。在提交之前，我需要将文件系统变更（Acts 1和Acts 2）添加到暂存区，并创建一个 Git 提交。

## [COMMIT] feat(providers): Implement `cs.subflow` for modular workflows

### 用户需求
引入 `cs.subflow` Provider，允许用户将复杂的 `Cascade` 工作流分解、封装到独立的 Python 文件中，并通过隔离的 `Engine` 实例动态执行，实现工作流的模块化和复用。

### 评论
`cs.subflow` 是实现“提供者组合优于封装”原则的核心驱动力。它将大型工作流解耦为可管理的子单元，极大地提高了可维护性、透明度和测试能力。子流程在隔离的 Engine 中运行，保证了上下文的纯净性。

### 目标
创建一个 Git 提交，包含 `subflow` 功能的实现和注册。

### 基本原理
我们通过在 `subflow` 任务内部动态创建 `Engine` 实例来执行子图，这在执行层而非图构建层实现了模块化。同时，将 Provider 注册到 `pyproject.toml`，确保了 `cs.subflow` 能够被动态发现和加载。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/providers #scope/api #task/domain/core #task/object/subflow-provider #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 添加文件并提交变更

我们将 `http.py` (Acts 1)、`pyproject.toml` (Acts 2) 以及 `subflow.py` 和新的测试文件添加到暂存区，并进行提交。

~~~~~act
git_add
src/cascade/providers/http.py
src/cascade/providers/subflow.py
tests/providers/test_http.py
tests/providers/test_subflow.py
pyproject.toml
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(providers): Implement cs.subflow for modular workflows

This commit introduces the core mechanism for workflow modularity and composition: `cs.subflow`.

Key Changes:
1.  **`subflow.py`**: Defines `SubflowProvider` and `_subflow_task`. This task dynamically loads a specified Python file, extracts the target LazyResult, and executes it using a new, isolated `Engine` instance. This isolation is crucial for predictable execution and avoiding state leakage.
2.  **`pyproject.toml`**: Registers the new `subflow` entry point.
3.  **Tests**: Adds `test_subflow.py` to ensure correct loading, execution, and parameter passing to the isolated sub-engine.
4.  **Refactor `cs.http`**: The previous `http.py` was merged and refactored in the preparation phase for this feature, using the new `HttpResponse` object and split into atomic methods (`http.get`, `http.post`, etc.). This change is included in this commit.
~~~~~

### 下一步建议
我们已经完成了路线图第一阶段（IO/网络）和第二阶段（模块化）的实施。

接下来是路线图的第三阶段：**验证组合模式**。

-   **目标**: 创建一个官方参考实现文件 `examples/patterns/llm_openai.py`，用于展示如何仅通过组合 `cs.http`, `cs.template`, `cs.Env`, `cs.Param` 和 `cs.subflow` 来构建一个功能完整的 LLM 调用模式，而无需编写新的原生 Provider 代码。
-   **操作**: 创建 `examples/patterns/llm_openai.py` 文件和必要的测试。

如果你同意，我将生成下一个计划。
