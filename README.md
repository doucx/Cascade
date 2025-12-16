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