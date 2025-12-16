好的，现在我们将把上一步的修改作为一个完整的逻辑单元提交。

## [COMMIT] fix(runtime): Redirect human-readable logs to stderr by default

### 用户需求
运行时日志（如任务启动/完成信息）应输出到标准错误流 (`stderr`)，以使核心数据输出 (`stdout`) 能够用于 Unix 管道操作。

### 评论
该修复解决了 `Cascade` 在自动化和脚本环境中的可用性问题。将运行时日志重定向到 `stderr` 确保了 `cascade run` 可以作为可组合的命令行工具使用，完全遵循了 Unix 哲学的最佳实践。

### 目标
创建一个 Git 提交，将 `HumanReadableLogSubscriber` 的默认输出流永久设置为 `sys.stderr`。

### 基本原理
我们通过修改 `HumanReadableLogSubscriber` 的默认参数，确保所有通过 `Engine` 默认配置启用的日志都流向 `stderr`。这是在核心库层面实现输出分离的最简洁和最少侵入性的方法。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #concept/ui #scope/dx
#ai/instruct
#task/domain/cli #task/object/output-streams #task/action/refactor
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交日志流向修复

将修改后的 `subscribers.py` 文件添加到 Git 暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
src/cascade/runtime/subscribers.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(runtime): Redirect human-readable logs to stderr by default

Changed the default stream for `HumanReadableLogSubscriber` from `sys.stdout` to `sys.stderr`.

This aligns Cascade's logging behavior with standard Unix philosophy, ensuring that runtime metadata (such as task start/finish messages) are sent to stderr, while the actual task output data remains available on stdout for piping and redirection by shell tools.
~~~~~

### 下一步建议
我们已经完成了输出流的修正。下一步应该按照您在 `当前.md` 中提出的构想，着手为 `MessageBus` 实现 **日志等级** 的概念，以允许用户根据需要过滤日志输出，进一步优化可观测性。
