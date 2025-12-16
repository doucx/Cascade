用户的分析是精确且及时的。您观察到的现象——运行时日志（如任务启动/完成信息）默认输出到 `stdout`——确实违反了标准的 CLI/Unix 哲学（数据到 `stdout`，元信息/日志到 `stderr`）。

我同意您的构想：
1.  **规范输出流**: 必须将运行时日志重定向到 `stderr`。
2.  **利用 MessageBus**: `Cascade` 已经通过 `MessageBus` 和 `HumanReadableLogSubscriber` 实现了日志的解耦，我们只需要修改订阅者的默认目标流即可。
3.  **日志等级**: 这是一个很好的未来改进方向，但眼下最重要的是修复流向问题。

我将生成一个实现此修复的计划。

## [WIP] fix(runtime): Redirect HumanReadableLogSubscriber default stream to stderr

### 用户需求
`cascade run` 命令发出的运行时日志（如任务启动/完成信息）默认输出到 `stdout`，这使得 `cascade` 的输出难以通过标准 Unix 管道 (`|`) 或重定向 (`>`) 进行处理。日志应该被重定向到 `stderr`。

### 评论
这是一个对开发者体验 (DX) 的关键修复，它将 `Cascade` 的运行时行为与 CLI/Unix 最佳实践对齐。该改动确保了用户可以轻松地将任务的核心输出通过管道传递给下游工具，而不会受到日志信息的干扰。

### 目标
1.  修改 `src/cascade/runtime/subscribers.py` 中 `HumanReadableLogSubscriber` 类的 `__init__` 方法。
2.  将其默认 `stream` 参数从 `sys.stdout` 更改为 `sys.stderr`。

### 基本原理
运行时日志和状态报告（如任务进度、成功/失败状态）属于辅助信息，其目的在于报告系统状态，因此应通过 `sys.stderr` 输出。只有任务本身返回的实际核心数据才应该被发送到 `sys.stdout`。通过修改 `HumanReadableLogSubscriber` 的默认行为，可以全局解决这一问题，而无需修改 `cs.run` 的调用方。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #concept/ui #scope/dx
#ai/instruct
#task/domain/cli #task/object/output-streams #task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 修改 HumanReadableLogSubscriber 的默认输出流

我们将修改 `src/cascade/runtime/subscribers.py` 文件，将 `HumanReadableLogSubscriber` 的默认输出流从 `sys.stdout` 改为 `sys.stderr`，并更新其文档字符串以反映此变化。

~~~~~act
patch_file
src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
class HumanReadableLogSubscriber:
    """
    Listens to events and prints user-friendly logs to a stream (default: stdout).
    """

    def __init__(self, bus: MessageBus, stream: TextIO = sys.stdout):
        self._stream = stream
~~~~~
~~~~~python
class HumanReadableLogSubscriber:
    """
    Listens to events and prints user-friendly logs to a stream (default: stderr).
    """

    def __init__(self, bus: MessageBus, stream: TextIO = sys.stderr):
        self._stream = stream
~~~~~

### 下一步建议
我们已经完成了输出流的修正。下一步是创建一个独立的 `[COMMIT]` 计划，将此修复提交到代码库。在完成提交后，我们应该考虑实现您提出的 **日志等级** 构想。
