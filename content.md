好的，经过几轮迭代和修复，`cs.cli` 功能现在已经稳定、健壮并且经过了充分的测试。是时候将这个重要的里程碑提交到版本控制中了。

我将生成一个 `[COMMIT]` 计划。

## [COMMIT] feat(tools): 实现 `cs.cli` 以从工作流自动生成 CLI

### 用户需求
将 `cs.cli` 功能及其所有相关的实现、测试和修复作为一个单一的、逻辑完整的单元提交到版本控制中。

### 评论
`cs.cli` 是 Cascade 在开发者体验（DX）方面的一次重大飞跃。它通过元编程技术，将一个声明式工作流无缝转换为一个功能完备的、自文档化的命令行工具，极大地简化了自动化脚本的分发和使用。这项功能兑现了 Cascade 成为一个现代化 `Makefile` 替代品的核心承诺，是项目路线图中的一个关键交付成果。

### 目标
创建一个 Git 提交，包含 `cs.cli` 的完整实现（`src/cascade/tools/cli.py`），其测试用例（`tests/tools/test_cli.py`），相关的依赖更新（`pyproject.toml`），以及在主 `__init__.py` 中的 API 暴露。

### 基本原理
`cs.cli` 功能的开发、测试和问题修复（循环导入、Typer API 错误）已经构成了一个完整的工作周期。将所有相关文件合并到一个原子提交中，可以清晰地在版本历史中标记这个新功能的诞生，并确保代码库在任何一个提交点都是稳定且功能完整的。

### 标签
#intent/build #flow/ready #priority/high #comp/core #scope/dx #ai/instruct #task/domain/tooling #task/object/cli-generator #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有与 `cli` 功能相关的文件

我们将 `cli` 模块、它的测试、依赖项声明和 API 暴露代码一次性添加到 Git 暂存区。

~~~~~act
git_add
pyproject.toml
src/cascade/tools/cli.py
tests/tools/test_cli.py
src/cascade/__init__.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，我们执行 `git commit`，附上详细的提交信息，记录下这个重要的新功能。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(tools): Implement cs.cli to auto-generate CLIs from workflows

Introduces `cascade.cli(target)`, a powerful tool that automatically generates a full-featured command-line interface from a Cascade workflow.

Key Features:
- **Automatic Discovery:** Scans the workflow's dependency graph to find all `cs.Param` objects.
- **Dynamic CLI Generation:** Uses Typer and metaprogramming to create CLI options (`--name`, `--count`, etc.) directly from `cs.Param` definitions.
- **Rich Metadata:** `cs.Param` attributes like `default`, `type`, and `description` are automatically mapped to their corresponding CLI option behaviors and help text.
- **Zero Boilerplate:** Users can now expose a complex, parameterized workflow as a professional CLI application simply by adding `if __name__ == "__main__": cs.cli(target)()` to their script.

This feature significantly improves the usability and distributability of Cascade scripts, fulfilling a core roadmap goal of providing a modern alternative to Makefiles and simple shell scripts.
~~~~~

### 下一步建议
我们已经成功交付了两个核心的开发者工具：`cs.visualize` 和 `cs.cli`。

根据我们的开发路线图，下一个重要的基础功能是 **“图与任务序列化”**。实现将计算图（`Graph`）和任务（`LazyResult`）序列化为一种通用格式（如 JSON），将为未来实现分布式执行、任务持久化和更高级的 UI 工具（如可视化编辑器）奠定至关重要的技术基础。

我建议我们开始这个任务。
