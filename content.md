好的，我将更新项目的许可证声明，将其从 MIT 更改为 Apache-2.0。

我将使用 `patch_file` 指令精确修改 `pyproject.toml` 中的许可证名称和 `README.md` 中的许可证徽章链接。

## [WIP] chore: Update license from MIT to Apache-2.0

### 用户需求
将项目许可证从 MIT 协议更改为 Apache License Version 2.0，并更新 `pyproject.toml` 和 `README.md` 以反映此更改。

### 评论
许可证是项目元数据中非常关键的一部分。本次更新将确保代码库的法律声明与实际采用的协议保持一致。

### 目标
1.  在 `pyproject.toml` 中，将 `license = "MIT"` 更改为 `license = "Apache-2.0"`。
2.  在 `README.md` 中，更新许可证徽章 URL，以显示 Apache 2.0。

### 基本原理
为了保持变更的原子性、可读性和稳定性，我将使用 `patch_file`。对于配置文件（如 `pyproject.toml`），直接更新许可证标识符；对于面向用户的文档（如 `README.md`），则更新用于视觉识别的徽章。

### 标签
#intent/tune #flow/ready #priority/high
#comp/build #comp/docs #scope/core
#ai/instruct
#task/domain/build #task/object/license #task/action/update
#task/state/begin #task/status/active

---

### Script

#### Acts 1: 更新 `pyproject.toml` 中的许可证标识符

使用 `patch_file` 将配置中的 `MIT` 替换为 `Apache-2.0`。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~text
license = "MIT"
~~~~~
~~~~~text
license = "Apache-2.0"
~~~~~

#### Acts 2: 更新 `README.md` 中的许可证徽章

将 `README.md` 中引用的徽章 URL 更新，使其显示 Apache 2.0。

~~~~~act
patch_file
README.md
~~~~~
~~~~~markdown
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
~~~~~
~~~~~markdown
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
~~~~~

### 下一步建议
现在文件已经修改完毕。你需要运行测试并验证更改。如果一切正常，下一步将是创建一个 `[COMMIT]` 计划来提交这些更改：

1.  `git_add pyproject.toml README.md`
2.  `git_commit` (提交消息建议使用 `chore(meta): Update license from MIT to Apache-2.0`)
