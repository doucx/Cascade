好的，我们已经成功完成了 **里程碑 1.4：感知原语——信号 (`cs.recv`)** 的实现，并且所有 TDD 测试均已通过。这个功能涉及到对接口协议、核心引擎和 `LocalBusConnector` 的多处、精密的修改。

现在我将生成一个 `[COMMIT]` 计划来封装这些变更。

## [COMMIT] feat(providers): Implement signal primitive `cs.recv` for responsive agents

### 用户需求
实现 `cs.recv` 原子任务，赋予工作流异步等待外部信号并处理超时的能力。

### 评论
`cs.recv` 是实现“涌现式分布式执行”和响应式 Agent 的最后一个关键原子积木。它通过将任务执行挂起，直到从 `Connector` 接收到消息，从而将 Cascade 升级为具备“听觉”的 Reactive Engine。本次实现也同时升级了 `Connector` 协议，引入了 `SubscriptionHandle` 来确保在任务完成或超时时，订阅资源能够被确定性地释放，从而满足长运行 Agent 对资源清洁度的要求。

### 目标
创建一个 Git 提交，包含所有必要的接口协议、核心引擎、LocalBusConnector 以及 `cs.recv` 提供者本身的实现和注册。

### 基本原理
我们通过以下三个核心步骤实现了该功能：
1.  **协议扩展**: 定义了 `SubscriptionHandle` 协议，使订阅操作可取消。
2.  **引擎桥接**: `Engine` 在运行时将自身的 `Connector` 注册为 `_internal_connector` 资源。
3.  **任务实现**: `cs.recv` 任务通过注入 `_internal_connector` 来执行订阅和 `asyncio.wait_for`，并在 `finally` 块中调用 `unsubscribe` 来进行清理。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #comp/interfaces #concept/signal #concept/resource #scope/api #ai/instruct #task/domain/providers #task/object/recv-primitive #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交所有相关的变更文件

~~~~~act
git_add
packages/cascade-interfaces/src/cascade/interfaces/protocols.py
packages/cascade-py/src/cascade/providers/signal.py
packages/cascade-py/pyproject.toml
packages/cascade-runtime/src/cascade/connectors/local.py
packages/cascade-runtime/src/cascade/runtime/engine.py
tests/py/providers/test_signal_provider.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(providers): Implement signal primitive `cs.recv` for responsive agents

This adds the core primitive `cs.recv(topic, timeout=...)` which allows a Cascade task to pause execution and wait for a signal message via the configured Connector.

Key architectural changes include:
1.  **Subscription Cleanup**: The `Connector` protocol is updated to return a `SubscriptionHandle`, guaranteeing deterministic cleanup of listeners via an `unsubscribe` method (critical for long-running TCO loops).
2.  **Engine Injection**: The `Engine` now registers its `Connector` instance as a special internal resource (`_internal_connector`), allowing `cs.recv` to inject and interact with the communication channel directly.
3.  **LocalBus Update**: `LocalBusConnector` is updated to implement `SubscriptionHandle` with proper queue and task cancellation logic, ensuring resources are not leaked during concurrent subscriptions.

This feature completes the set of primitives required for the "Firefly Test" (TCO, cs.wait, cs.recv).
~~~~~

### 下一步建议
我们已经完成了 **萤火计划** 第一阶段的所有里程碑（1.1-1.4）：
*   **1.1 LocalBus Connector**: 已实现。
*   **1.2 引擎 TCO**: 已实现。
*   **1.3 `cs.wait`**: 已实现。
*   **1.4 `cs.recv`**: 已实现。

现在，我们拥有了一个具备永续执行和基本感知（时间、信号）能力的 Agent 运行时。

根据 [萤火计划：合成智能与涌现架构演进技术路线图](萤火计划：合成智能与涌现架构演进路线图.md) 的指导，下一步是 **第三部分：观测站建设 (The Observatory)**，即搭建实验环境并运行第一个基准测试。

我建议：
1.  **创建 `/observatory` 目录**。
2.  **创建第一个 Agent 逻辑**: 实现一个简单的、只包含 `cs.wait` 的 `firefly.py`，作为基准测试的 Agent。
3.  **创建实验运行脚本**: 定义如何启动多个 Agent 实例，并使用 `cs.run` 和 `LocalBusConnector` 运行它们。

如果你同意，我将首先创建 `/observatory` 目录结构。
