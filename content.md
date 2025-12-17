我们已经完成了 `cs.io.stdout.write` 和 `cs.io.stdin.read_line` 的功能实现和测试代码的修正。测试失败的原因已确认为异步运行时环境冲突。现在，我们将把这些变更作为单一逻辑单元进行提交。

## [COMMIT] fix(test): Refactor stdio tests to use Engine.run directly and improve read_line composition

### 错误分析
测试在 `pytest-asyncio` 的异步环境中调用了 `cs.run()`，后者在内部调用了 `asyncio.run()`，导致了 `RuntimeError: asyncio.run() cannot be called from a running event loop`。

### 用户需求
将新的标准 I/O Provider（`cs.io.stdout.write` 和 `cs.io.stdin.read_line`）集成到项目中，同时修复相关的异步测试冲突，并确保 `read_line` 可以通过依赖来强制执行顺序。

### 评论
本次提交解决了在异步测试环境中运行 Cascade 工作流的核心痛点，并将所有测试更改为更健壮的 `await engine.run()` 模式。同时，对 `_stdin_read_line_task` 进行了微小的 API 改进，使其能够接受哑元位置参数，从而完美地支持通过数据依赖来强制执行 `write -> read` 的顺序，进一步强化了我们的“组合优于封装”哲学。

### 目标
1.  移除 `tests/providers/test_stdio.py` 中对 `cs.run()` 的调用，改用 `await engine.run()`。
2.  修改 `_stdin_read_line_task` 使其接受位置参数 `*args`，以支持依赖注入来控制执行顺序。
3.  提交 `src/cascade/providers/stdio.py`、`tests/providers/test_stdio.py` 和 `pyproject.toml` 中的所有变更。

### 基本原理
通过直接使用 `engine.run()` 并 `await` 它，我们将工作流执行融入了 `pytest-asyncio` 已提供的事件循环中，消除了循环冲突。这个修复同时也为今后的所有异步集成测试设定了正确的模式。`_stdin_read_line_task` 的改进是必要的，它允许用户以声明式的方式控制 I/O 顺序，这是人机交互模式的关键。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #comp/core #concept/io #scope/dx #ai/instruct #task/domain/testing #task/object/asyncio-runner #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 添加并提交所有修改文件

我们将新的 Provider 实现文件、修改后的 `pyproject.toml` 和重写的测试文件添加到暂存区，并执行提交。

~~~~~act
git_add
src/cascade/providers/stdio.py
pyproject.toml
tests/providers/test_stdio.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(stdio): Fix asynchronous test conflict and improve read_line composability

This commit finalizes the implementation of atomic standard I/O providers: `cs.io.stdout.write` and `cs.io.stdin.read_line`.

Key changes:
1.  **Test Fix:** Resolved the `asyncio.run() cannot be called from a running event loop` error in `test_stdio.py` by refactoring tests to use `await engine.run()` instead of the high-level `cs.run()`.
2.  **Provider Improvement:** Modified `_stdin_read_line_task` to accept positional arguments (`*args`). This allows users to establish explicit data dependencies, such as making a `read_line` task depend on a `stdout.write` task to ensure the prompt is printed before input is read, reinforcing the composability principle.
3.  **Registration:** Registered the new providers under `io.stdout.write` and `io.stdin.read_line` in `pyproject.toml`.
~~~~~

### 下一步建议
我们已经完成了第二层“核心能力支柱”中的大部分基础设施任务（原子连接器和组合机制）。

下一步的重点应该转向文档和示例，将我们的新哲学（组合优于封装）具体化：

1.  **文档化新哲学**: 创建或更新文档，明确阐述如何使用 `cs.subflow`、`cs.http` 和 `cs.template` 来实现高级功能（例如，LLM 调用、自定义 API 封装），而不是依赖内置 Provider。
2.  **创建示例**: 正式将 `src/cascade/examples/patterns/llm_openai.py` 升级为一个可信赖、可复用的模式。

我建议我们首先专注于**文档更新和 LLM 模式的文档化**，以确保用户能够理解和利用我们新的设计哲学。
