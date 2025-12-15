## [WIP] feat(runtime): 在 Engine 中实现重试逻辑

### 用户需求
1.  在 `Engine` 执行任务时，能够识别并应用 `retry_policy`。
2.  当任务失败时，根据策略进行多次重试，支持延迟 (`delay`) 和指数退避 (`backoff`)。
3.  确保每次重试失败和最终失败都能正确记录日志或抛出异常。

### 评论
重试机制是构建健壮自动化脚本的关键。通过将这一逻辑内建于引擎中，用户不再需要在每个任务函数里手写 `try...except` 循环。这是一个典型的“关注点分离”：用户只管写“快乐路径”的业务逻辑，错误处理交给框架。

### 目标
1.  修改 `src/cascade/runtime/engine.py`：
    -   在 `executor.execute` 的调用外层包裹一个重试循环。
    -   使用 `asyncio.sleep` 实现异步延迟。
2.  添加测试 `tests/test_retry.py`，验证重试次数、延迟和最终成功/失败的行为。

### 基本原理
-   **装饰器模式 vs 引擎内置**: 虽然可以用装饰器实现，但在引擎层面实现能更好地控制事件发布（例如发布 `TaskRetry` 事件，尽管 MVP 阶段可能先简化处理），并且能更好地与资源管理、超时控制等其他引擎特性集成。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #concept/resilience
#task/domain/core #task/object/resilience-support #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Implement Retry Loop in Engine

在 `Engine.run` 中实现重试逻辑。我们需要引入 `asyncio` 来处理非阻塞延迟。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
import time
import inspect
from typing import Any, Dict, Optional, Generator, Callable
from uuid import uuid4
from contextlib import ExitStack
~~~~~
~~~~~python
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable
from uuid import uuid4
from contextlib import ExitStack
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                    self.bus.publish(start_event)

                    try:
                        result = await self.executor.execute(
                            node, graph, results, active_resources
                        )
                        results[node.id] = result

                        task_duration = time.time() - task_start_time
                        finish_event = TaskExecutionFinished(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            status="Succeeded",
                            duration=task_duration,
                            result_preview=repr(result)[:100],
                        )
                        self.bus.publish(finish_event)

                    except Exception as e:
                        task_duration = time.time() - task_start_time
                        fail_event = TaskExecutionFinished(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            status="Failed",
                            duration=task_duration,
                            error=f"{type(e).__name__}: {e}",
                        )
                        self.bus.publish(fail_event)
                        raise
~~~~~
~~~~~python
                    self.bus.publish(start_event)

                    # Determine retry policy
                    retry_policy = node.retry_policy
                    max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
                    delay = retry_policy.delay if retry_policy else 0.0
                    backoff = retry_policy.backoff if retry_policy else 1.0

                    attempt = 0
                    last_exception = None

                    while attempt < max_attempts:
                        attempt += 1
                        try:
                            result = await self.executor.execute(
                                node, graph, results, active_resources
                            )
                            results[node.id] = result

                            task_duration = time.time() - task_start_time
                            finish_event = TaskExecutionFinished(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                status="Succeeded",
                                duration=task_duration,
                                result_preview=repr(result)[:100],
                            )
                            self.bus.publish(finish_event)
                            # Break the retry loop on success
                            last_exception = None
                            break

                        except Exception as e:
                            last_exception = e
                            # If we have retries left, wait and continue
                            if attempt < max_attempts:
                                # Optional: Publish a specific Retry event here in the future
                                await asyncio.sleep(delay)
                                delay *= backoff
                            else:
                                # Final failure
                                task_duration = time.time() - task_start_time
                                fail_event = TaskExecutionFinished(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    status="Failed",
                                    duration=task_duration,
                                    error=f"{type(e).__name__}: {e}",
                                )
                                self.bus.publish(fail_event)
                                raise last_exception
~~~~~

#### Acts 2: Add Retry Tests

编写测试用例验证重试行为。

~~~~~act
write_file
tests/test_retry.py
~~~~~
~~~~~python
import pytest
from unittest.mock import Mock
import asyncio
import cascade as cs

def test_retry_success_after_failure():
    """Test that a task retries and eventually succeeds."""
    
    call_count = 0

    @cs.task
    def flaky_task():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Fail!")
        return "Success"

    # Retry 3 times (total 4 attempts allowed)
    task_with_retry = flaky_task().with_retry(max_attempts=3, delay=0.01)

    result = cs.run(task_with_retry)

    assert result == "Success"
    assert call_count == 3  # Failed twice, succeeded on 3rd

def test_retry_exhausted_failure():
    """Test that a task fails after exhausting all retries."""
    
    call_count = 0

    @cs.task
    def always_fail():
        nonlocal call_count
        call_count += 1
        raise ValueError("Always fail")

    task_with_retry = always_fail().with_retry(max_attempts=2, delay=0.01)

    with pytest.raises(ValueError, match="Always fail"):
        cs.run(task_with_retry)
    
    assert call_count == 3  # Initial + 2 retries
~~~~~

### 下一步建议
执行 **子任务 3: 缓存逻辑实现与 FileExistenceCache**。
现在我们有了健壮的重试，接下来要实现“避免重复劳动”的能力。我们将实现 `FileExistenceCache` 适配器，并在 `Engine` 中集成缓存检查 (`check`) 和保存 (`save`) 逻辑。
