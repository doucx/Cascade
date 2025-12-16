简要回答
好的，我将创建项目的 `README.md` 文件（面向外部用户）和 `docs/index.md`（内部文档首页），清晰地阐述 `Cascade` 的价值和核心功能。

## [WIP] docs: Create top-level documentation files (README and index)

### 摘要头
## [WIP] docs: Create top-level documentation files (README and index)

### 用户需求
创建 `README.md` 和 `docs/index.md`，作为项目的入口文档，介绍 `Cascade` 的核心价值、功能和架构。

### 评论
高质量的入门文档是项目成功的关键。这两个文件将作为用户了解 `Cascade` 的第一站，必须清晰、简洁地传达其“声明式、可依赖、可调试”的价值主张，并引导用户进入详细的操作指南。

### 目标
1.  创建 `README.md`，包含项目简介、核心特性和安装说明。
2.  创建 `docs/index.md`，作为 MkDocs 站点的主页，概述架构和主要文档章节。

### 基本原理
这两个文件是基础文档，遵循 `d3-principle-quipu-write-strategy`，使用 `write_file` 一次性提供完整内容。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #scope/ux #ai/instruct #task/domain/documentation #task/object/project-overview #task/action/build #task/state/continue

---

### Script

#### Acts 1: 创建项目根目录下的 `README.md`

~~~~~act
write_file
README.md
~~~~~
~~~~~markdown
# Cascade: 声明式自动化库

[![PyPI Version](https://img.shields.io/pypi/v/cascade-py)](https://pypi.org/project/cascade-py/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Cascade** 是一个用于构建可靠、高效、可复用自动化工作流的 Python 库。
它将传统的命令式脚本升级为**声明式计算图 (Declarative Computation Graph)**。

无论你是在编排本地开发任务、构建数据管道，还是在管理云原生部署，`Cascade` 都能保证：

1.  **依赖驱动**: 任务只在需要时执行，且顺序永远正确。
2.  **默认健壮**: 内置缓存、重试和资源调度能力，无需额外编写复杂的异常处理代码。
3.  **高度可测试**: 业务逻辑与 I/O 依赖完全解耦。

## 🚀 核心特性

### 1. 声明式定义与自动重试

使用 `@cs.task` 将任何 Python 函数转换为可管理的计算节点。你可以通过简单的链式 API 来定义其执行策略。

```python
import cascade as cs

@cs.task
def fetch_data_from_api(url):
    # 模拟一个可能因网络抖动而失败的 I/O 操作
    # ... 业务逻辑 ...
    pass

# 定义一个任务：如果失败，最多重试 3 次，每次延迟 1.0 秒
robust_fetch = fetch_data_from_api(url="...").with_retry(
    max_attempts=3, 
    delay=1.0, 
    backoff=2.0
)

# cs.run(robust_fetch)
```

### 2. 智能缓存与按需执行

`Cascade` 自动构建依赖图，并允许你定义缓存策略，避免重复执行耗时任务。

```python
from cascade.adapters.caching import FileExistenceCache

# 定义一个耗时的报告生成任务
generate_report = cs.shell("generate_large_report.sh").with_cache(
    FileExistenceCache(target_path="output/report.pdf")
)

# 只有当 output/report.pdf 不存在时，generate_report 才会执行。
```

### 3. 资源感知调度

通过声明任务所需的系统资源，`Cascade` 可以自动管理并发和避免资源超额使用。

```python
# 声明此任务需要 1 个 GPU
gpu_task = train_model().with_constraints(gpu_slots=1, memory_gb=16)

# 引擎在运行时，会根据 cs.run(..., system_resources={...}) 的配置进行调度。
```

## 🛠️ 安装

`Cascade` 的核心库没有硬性依赖。所有功能模块（如 HTTP, SQL, Template）都通过可选依赖提供：

```bash
# 核心库
pip install cascade-py

# 安装所有可选依赖 (推荐用于完整体验)
pip install cascade-py[all]
```

## 📚 快速上手

请查阅我们的官方文档，了解如何开始构建你的第一个 `Cascade` 工作流：

[**👉 查看快速上手教程**](docs/tutorial/getting-started.md)
~~~~~

#### Acts 2: 创建 `docs/index.md` 文件

~~~~~act
write_file
docs/index.md
~~~~~
~~~~~markdown
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
~~~~~

### 下一步建议
我们已经完成了文档的基础工作。下一步，我建议我们继续推动**任务：继续核心功能开发**，即开始 **`cs.config` Provider** 的实现，这将涉及增强配置的动态解析能力。
