这是一个将 **第三阶段：验证组合模式 (以 `LLM` 为例)** 的所有更改提交到版本控制的计划。

此提交包含 LLM 模式的实现文件、用于验证组合的集成测试，以及为修复 `cs.template` 的 API 缺陷而进行的微小重构。

## [COMMIT] feat(patterns): Add LLM composition pattern and fix template API

### 用户需求
引入 LLM 调用模式，证明 `cs.http`, `cs.template`, `cs.subflow` 等原子化组件可以组合成复杂的高级工作流（LLM Orchestration），同时修复了 `cs.template` 中由于 Python `**kwargs` 运行时限制导致的问题。

### 评论
这个提交标志着第二层核心能力路线图的成功完成。我们创建了一个行业标准的用例，完全通过组合现有组件实现，证明了架构的正确性。对 `cs.template` 的修复是必要的 API 健壮性改进，确保它可以接收表示未来值的 `LazyResult` 字典。

### 目标
1.  提交 LLM 模式文件 `llm_openai.py` 及其目录结构。
2.  提交 `llm_pattern` 集成测试。
3.  提交对 `src/cascade/providers/template.py` 的修复。

### 基本原理
将 LLM 模式作为官方参考，有助于教育用户如何使用 `Cascade` 的核心特性，特别是 `cs.subflow` 和 `.with_retry()` 策略在网络调用中的精确应用。

### 标签
#intent/build #intent/fix #flow/ready #priority/high #comp/providers #comp/tests #scope/dx #task/domain/patterns #task/object/llm-pattern #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 添加文件并提交变更

将所有新增和修改的文件添加到暂存区，并执行提交。

~~~~~act
git_add
src/cascade/providers/template.py
src/cascade/examples/patterns/llm_openai.py
tests/examples/test_llm_pattern.py
tests/examples/
src/cascade/examples/patterns/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(patterns): Add LLM composition pattern and fix template API

This commit marks the completion of the second-tier core capability roadmap by delivering a non-trivial, complex workflow built purely from atomic providers.

Key Changes:

1.  **New Pattern (`examples/patterns/llm_openai.py`)**: Demonstrates how to orchestrate an OpenAI API call by composing:
    *   `cs.Env` for API keys.
    *   `cs.Param` for dynamic configuration (model, template).
    *   `cs.template` for prompt rendering.
    *   `cs.http.post` for the network call, with an explicit `.with_retry()` policy.
    *   `cs.subflow` is used to call this pattern from an external entry point.

2.  **Fix(template)**: Refactors `cs.template` to explicitly accept a `context` argument. This resolves a `TypeError` encountered when passing a `LazyResult` representing a dictionary (`cs.Param` or upstream task) directly via `**kwargs` in the defining stage (which is a static operation in Python).

3.  **Tests**: Adds end-to-end integration tests for the LLM pattern, validating the flow via `cs.subflow` using a mocked HTTP response.
~~~~~

### 下一步建议
我们已经完成了 Cascade 第二层核心能力的实现和验证，项目处于一个功能完整且经过测试的稳定状态。

接下来，我建议从技术债务监测中选取优先级较高的项目继续迭代，例如：
1.  **缓存键的健壮性**: 这是一个架构稳定性问题，需要引入一个更明确的 `generate_key` 协议。
2.  **增强 `cs.template` 的开发者体验**: 考虑到我们刚刚修复了 `cs.template` 的人体工程学问题，现在正是引入如 `cs.dict` 这样的辅助提供者来提高 DX 的好时机（对应技术债务分析中的选项 B）。

请告诉我你希望继续处理哪个任务。
