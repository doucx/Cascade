# 欢迎使用 Cascade v0.1.0

`Cascade` 是一个将自动化和数据流处理提升到新水平的 Python 库。

我们的核心思想是：**将所有操作（从 Python 函数到外部命令）视为计算图上的一个节点，并声明它们之间的依赖关系。**

## 核心价值

| 维度 | 传统脚本 (Bash/命令式 Python) | Cascade (声明式) |
| :--- | :--- | :--- |
| **可读性** | 业务逻辑、错误处理和资源管理混杂。 | 业务逻辑与执行策略（缓存、重试、DI）完全分离。 |
| **效率** | 每次运行都从头开始，耗时步骤无法跳过。 | 自动构建依赖图，按需执行，内置智能缓存机制。 |
| **健壮性** | 需手动编写 `try/except` 和 `while` 循环处理重试。 | 策略链式调用 `.with_retry()` 和 `.with_constraints()` 一键实现。 |
| **可配置性** | 难以在多个环境中切换复杂的输入。 | 使用 `cs.Param` 和 `cs.Router` 实现高级动态配置和运行时参数注入。 |

---

## 快速导航

### 📖 教程 (Tutorial)
如果你是第一次接触 `Cascade`，请从这里开始。
*   [快速上手](tutorial/getting-started.md)

### ⚙️ 操作指南 (How-To Guides)
学习如何实现特定的自动化模式和实践。
*   [定义计算：使用 Task 和 Provider](how-to-guides/defining-computations.md)
*   [使用内置 Provider：Shell, File, HTTP, SQL](how-to-guides/using-providers.md)
*   [管理资源 (DI)：使用 `@cs.resource` 和 `cs.inject`](how-to-guides/dependency-injection.md)
*   [提升健壮性：缓存、重试与资源调度](how-to-guides/improving-robustness.md)
*   [构建复杂工作流：Router, Map, Run-If](how-to-guides/advanced-workflows.md)

### 💡 核心概念 (Concepts)
深入了解 `Cascade` 的设计哲学和模型。
*   [核心哲学](concepts/philosophy.md)

### 📚 参考 (Reference)
*   [API 参考](reference/api.md)
*   [CLI 工具](reference/cli-tools.md)