好的，我们将为新实现的时间原语 `cs.wait` 创建提交。

## [COMMIT] feat(providers): Introduce `cs.wait` time primitive

### 用户需求
实现并注册 `cs.wait` 原子任务，以支持工作流对时序的精确控制，实现非阻塞的异步延迟。

### 评论
`cs.wait` 是“萤火计划”的关键基础设施之一。它是一个非阻塞的原子任务，将 `asyncio.sleep` 提升为工作流的一等公民。这使得 Agent 能够定义自己的“脉冲节拍”和时序逻辑，而无需在 Python 代码中手动处理异步。它的实现遵循了“原子化、可组合”的设计原则。

### 目标
创建一个 Git 提交，包含 `cs.wait` 的实现文件和 `pyproject.toml` 的注册信息。

### 基本原理
通过将 `cs.wait` 实现为一个 `Provider` 插件，我们扩展了 `cascade-py` 的能力，同时保持了核心引擎的轻量级和稳定。测试用例已验证它满足非阻塞和动态参数化的要求。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/tests #concept/time #scope/api #ai/instruct #task/domain/providers #task/object/wait-primitive #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交 `cs.wait` 功能及其测试

将新创建的文件和修改后的配置文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-py/src/cascade/providers/time.py
packages/cascade-py/pyproject.toml
tests/py/providers/test_time_provider.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(providers): Introduce cs.wait time primitive

Implements the `cs.wait(delay)` provider, which acts as a non-blocking asynchronous sleep function within the Cascade workflow.

This is a fundamental primitive required for implementing time-based logic, long-running agents, and rate-limiting patterns using dynamic parameters (LazyResults).

The implementation is registered as a standard plugin, keeping the core engine decoupled from the functionality.
~~~~~

### 下一步建议
我们已经完成了 Milestone 1.3。现在我们将转向 **里程碑 1.4：感知原语——信号 (`cs.recv`)**。

`cs.recv` 是实现响应式 Agent 的核心。它将挂起任务直到收到特定的外部信号。

我建议下一步是为 `cs.recv` 编写 TDD 测试用例，以进入 **Red** 阶段。这涉及创建一个新的提供者模块，例如 `cascade-py/src/cascade/providers/signal.py` (或类似的命名，但我们先使用 `recv`)。
