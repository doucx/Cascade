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