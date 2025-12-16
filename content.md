好的，我们继续批量填充内容，这次将完成“操作指南”的最后两篇文章。

这将涵盖 `Cascade` 的两个高级但至关重要的特性：依赖注入（资源管理）和健壮性（缓存与重试）。

## [WIP] docs: 填充高级“操作指南” (DI 与健壮性)

### 用户需求
完成“操作指南”部分的文档填充工作，具体包括“依赖注入”和“提升健壮性”两篇指南。

### 评论
这两篇指南是 `Cascade` 从一个简单的脚本编排工具走向生产级自动化框架的关键。清晰地阐述资源管理和容错机制，将极大地提升用户构建复杂、可靠应用的信心。我将确保示例代码准确且易于理解。

### 目标
1.  填充 `docs/how-to-guides/dependency-injection.md`，内容来自手册第 6 节。
2.  填充 `docs/how-to-guides/improving-robustness.md`，内容来自手册第 7 节。

### 基本原理
我将继续采用内容迁移和适配的策略。对于依赖注入部分，重点是解释 `@cs.resource` 的 `yield` 模式和 `@cs.task` 中 `cs.inject` 的用法。对于健壮性部分，将分别介绍缓存和重试的使用场景和 API，并提供基于 `Cascade` 内置能力的具体示例（例如使用 `FileExistenceCache`）。

### 标签
#intent/document #flow/ready #priority/high #comp/docs #scope/dx #ai/delegate #task/domain/docs #task/object/content-population #task/action/batch-write #task/state/continue

---

### Script

#### Acts 1: 填充“依赖注入”指南

这部分内容解释了如何使用 `@cs.resource` 和 `cs.inject` 来管理数据库连接、API 客户端等有生命周期的外部服务。

~~~~~act
write_file
docs/how-to-guides/dependency-injection.md
~~~~~
~~~~~markdown
# 操作指南：管理资源 (DI)

在真实世界的自动化工作流中，许多任务都依赖于外部资源，例如数据库连接、HTTP 会话客户端或硬件设备句柄。这些资源通常需要一个明确的**初始化 (Setup)** 和**清理 (Teardown)** 过程。

`Cascade` 通过一个优雅的依赖注入 (Dependency Injection, DI) 系统来解决这个问题，确保资源被正确地管理和传递。

## 核心组件

1.  **`@cs.resource`**: 一个装饰器，用于将一个资源管理函数转换为 `Cascade` 可识别的资源定义。
2.  **`cs.inject()`**: 一个函数，用于在任务的签名中声明对某个资源的依赖。

## 定义一个资源

一个资源必须被定义为一个**生成器 (generator) 函数**，即函数体内必须使用 `yield` 关键字。

*   `yield` 之前的所有代码，是资源的**初始化**逻辑。
*   `yield` 产生的值，是真正要被注入到任务中的**资源实例**。
*   `yield` 之后的所有代码，是资源的**清理**逻辑。`Cascade` 引擎保证在整个工作流运行结束后，这部分代码一定会被执行。

**示例：定义一个数据库连接资源**

```python
import cascade as cs
from sqlalchemy import create_engine

# 假设 db_url 来自于配置
db_url = cs.config("db.url.analytics")

@cs.resource
def analytics_db(url: str = db_url):
    """一个管理数据库连接的资源"""
    
    print("【资源】正在连接数据库...")
    engine = create_engine(url)
    connection = engine.connect()
    
    # yield 出可用的连接对象
    yield connection
    
    # 工作流结束后，这里的代码将被执行
    print("【资源】关闭数据库连接...")
    connection.close()
    engine.dispose()
```

## 在任务中使用资源

要在任务中使用上面定义的资源，只需在该任务的函数签名中，使用 `cs.inject("资源名称")` 作为参数的默认值。

```python
import cascade as cs

@cs.task
def fetch_active_users(
    conn = cs.inject("analytics_db") # 声明依赖于名为 'analytics_db' 的资源
):
    """一个使用数据库连接的任务"""
    
    # 在任务内部，conn 就是 yield 出来的那个 connection 对象
    result = conn.execute("SELECT * FROM users WHERE status = 'active'")
    return result.fetchall()

# 当你运行这个任务时，Cascade 引擎会自动：
# 1. 发现 fetch_active_users 依赖于 analytics_db。
# 2. 找到 analytics_db 资源，并执行其初始化逻辑。
# 3. 将 yield 的值注入到 fetch_active_users 的 conn 参数中。
# 4. 执行任务。
# 5. 在整个工作流结束后，执行 analytics_db 的清理逻辑。
final_result = fetch_active_users()
```

### Provider 的隐式使用

`Cascade` 的一些内置 Provider（如 `cs.sql`）也隐式地使用了这个资源系统。

```python
# 这行代码等效于在内部执行了 cs.inject("analytics_db")
users = cs.sql("SELECT ...", db="analytics_db")
```

通过这种方式，`Cascade` 将业务逻辑（`fetch_active_users`）与资源管理的复杂性完全解耦，使你的代码更清晰、更易于测试。
~~~~~

#### Acts 2: 填充“提升健壮性”指南

这部分内容介绍如何使用 `.with_cache()` 和 `.with_retry()` 来让工作流更稳定、更高效。

~~~~~act
write_file
docs/how-to-guides/improving-robustness.md
~~~~~
~~~~~markdown
# 操作指南：提升健壮性

自动化工作流经常面临两大挑战：**暂时性故障**（如网络抖动）和**重复执行昂贵的操作**。`Cascade` 提供了两个强大的链式方法来应对这些问题，让你的工作流在不修改核心逻辑的情况下，变得更加健壮和高效。

## 避免重复计算：使用缓存 (`.with_cache()`)

对于那些输入相同、输出也必定相同（确定性的）且执行成本高昂的任务，你可以附加一个缓存策略。

`.with_cache()` 方法可以被链式调用在任何 `LazyResult` 之后，它接受一个**缓存策略 (Cache Policy)** 对象作为参数。

**示例：缓存一个耗时的文件生成任务**

`Cascade` 提供了一个简单的 `FileExistenceCache` 策略：如果目标文件已存在，则跳过任务。

```python
import cascade as cs
from cascade.adapters.caching import FileExistenceCache

# 定义一个 shell 命令，它会模拟一个耗时的操作并创建一个文件
# 注意：我们让它打印日志，以便观察它是否被执行
create_report_task = cs.shell(
    "echo 'Generating report...' && sleep 2 && touch report.txt"
)

# 定义缓存策略：如果 'report.txt' 文件存在，就认为任务已缓存
cache_policy = FileExistenceCache(target_path="report.txt")

# 将缓存策略附加到任务上
cached_task = create_report_task.with_cache(cache_policy)

# 第一次运行：
# > cs.run(cached_task)
# 输出: "Generating report..."
# (等待 2 秒)
# report.txt 文件被创建

# 第二次运行：
# > cs.run(cached_task)
# (立即返回, 无任何输出)
# 因为 report.txt 已经存在，shell 命令被完全跳过。
```

## 处理暂时性故障：自动重试 (`.with_retry()`)

对于可能因网络问题或服务临时不可用而失败的任务（如 API 调用），你可以配置自动重试逻辑。

`.with_retry()` 方法可以被链式调用在任何 `LazyResult` 之后，它允许你配置重试次数、延迟和退避策略。

**示例：为一个可能失败的 API 调用配置重试**

假设我们有一个调用外部服务的 `http` 任务，该服务有时会不稳定。

```python
import cascade as cs

# 定义一个 API 调用任务
# (为了示例，我们假设这个 URL 可能会间歇性失败)
api_call = cs.http("https://api.flaky-service.com/data")

# 为这个任务配置重试逻辑：
# - max_attempts: 最多尝试 3 次 (即首次失败后，再重试 2 次)
# - delay: 首次重试前等待 1.0 秒
# - backoff: 后续每次重试的延迟时间乘以 2.0 (即 1s, 2s, 4s...)
robust_api_call = api_call.with_retry(max_attempts=3, delay=1.0, backoff=2.0)

# 当运行 robust_api_call 时:
# - 如果 `api_call` 第一次就成功, 流程继续。
# - 如果 `api_call` 第一次失败, Cascade 会捕获异常, 等待 1 秒, 然后再次尝试。
# - 如果第二次又失败, 它会等待 2 秒 (1.0 * 2.0), 然后进行第三次尝试。
# - 如果第三次仍然失败, 最终的异常才会被抛出, 导致工作流失败。
```

通过组合使用 `.with_cache()` 和 `.with_retry()`，你可以用声明式的方式，极大地提升工作流的稳定性和效率，而无需用 `try/except` 和 `if os.path.exists()` 把你的业务逻辑弄得一团糟。
~~~~~

### 下一步建议
我们已经完成了“教程”、“操作指南”和“概念”这三个主要部分的内容填充。最后剩下的就是“参考”部分了。

*   `docs/reference/cli-tools.md`：这部分可以手动编写，介绍 `cs.cli` 工具如何使用。
*   `docs/reference/api.md`：这部分设计的初衷是使用 `mkdocstrings` 从代码的 docstrings 自动生成。

我们可以先手动编写 `cli-tools.md` 的内容。如果你同意，我将为你生成这篇文档。
