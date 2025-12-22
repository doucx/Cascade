好的，我将生成一个 **[COMMIT]** 计划来提交许可证变更。

## [COMMIT] chore(meta): Update license from MIT to Apache-2.0

### 用户需求
提交在 `pyproject.toml` 和 `README.md` 中将许可证从 MIT 更改为 Apache 2.0 的文件修改。

### 评论
这个提交将项目元数据与法律协议保持同步。

### 目标
通过 `git_add` 和 `git_commit` 指令，将许可证更新（`pyproject.toml` 和 `README.md` 中的两处修改）作为一个完整的、逻辑上的工作单元提交到 Git 历史。

### 基本原理
根据 Quipu 协议，文件系统修改和 Git 提交操作必须分离。在上一个计划中，我们完成了修改；在这个计划中，我们进行提交操作，确保了工作流的清晰和可回溯性。摘要状态设置为 `[COMMIT]` 且任务状态为 `#task/state/end`，标志着这个宏观任务的完成。

### 标签
#intent/tooling #flow/ready #priority/high
#comp/build #comp/docs #scope/core
#ai/instruct
#task/domain/build #task/object/license #task/action/update
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加更改到暂存区

将 `pyproject.toml` 和 `README.md` 文件添加到 Git 暂存区。

~~~~~act
git_add
pyproject.toml
README.md
~~~~~

#### Acts 2: 提交变更

创建一个描述性提交，完成许可证的更新。

~~~~~act
git_commit
~~~~~
~~~~~text
chore(meta): Update license from MIT to Apache-2.0

Updates the project license in `pyproject.toml` and `README.md` from MIT to Apache License Version 2.0.

- `pyproject.toml`: Changed license identifier to "Apache-2.0".
- `README.md`: Updated the license badge URL to reflect Apache 2.0.
~~~~~

### 下一步建议
虽然元数据已更新，但 Apache 2.0 协议要求在项目中包含完整的 `LICENSE` 文件。如果你尚未创建或更新该文件，建议下一步：

1.  **创建或更新 `LICENSE` 文件**: 确保根目录下的 `LICENSE` 文件内容是完整的 Apache License Version 2.0 文本。
