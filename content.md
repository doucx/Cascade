## [WIP] feat(runtime): 实现缓存逻辑与 FileExistenceCache 适配器

### 用户需求
1.  在 `Engine` 执行任务前，检查是否存在有效的缓存。如果命中，跳过执行并直接使用缓存结果。
2.  在任务执行成功后，调用缓存策略保存结果。
3.  实现第一个具体的缓存策略：`FileExistenceCache`，当指定文件存在时视为缓存命中。

### 评论
这是 MVP 阶段的最后一个重要特性。缓存机制极大地提升了自动化流程的效率，特别是对于耗时的数据处理或构建任务。`FileExistenceCache` 是最简单但也最实用的策略之一，特别适合基于文件的自动化工作流（如 Make 风格的任务）。

### 目标
1.  修改 `src/cascade/runtime/engine.py`：
    -   在重试循环之前，增加缓存检查逻辑。
    -   如果命中缓存，发布 `TaskSkipped` 事件，并跳过执行。
    -   在任务成功后，增加缓存保存逻辑。
2.  创建 `src/cascade/adapters/caching/file_existence.py`：实现 `FileExistenceCache` 类。
3.  添加测试 `tests/test_caching.py` 验证缓存命中和未命中的行为。

### 基本原理
-   **优先检查**: 缓存检查必须在任何执行尝试（包括重试）之前进行。
-   **结果一致性**: 缓存命中的结果必须在格式上与实际执行的结果兼容，以便下游任务使用。对于 `FileExistenceCache`，通常返回文件路径或 `True`。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/adapters #concept/caching
#task/domain/core #task/object/resilience-support #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Implement FileExistenceCache Adapter

实现基于文件存在的缓存策略。

~~~~~act
write_file
src/cascade/adapters/caching/file_existence.py
~~~~~
~~~~~python
import os
from typing import Any, Dict, Callable, Union
from cascade.runtime.protocols import CachePolicy

class FileExistenceCache:
    """
    A simple cache policy that considers a task 'cached' if a specific file exists.
    """

    def __init__(self, target_path: Union[str, Callable[[Dict[str, Any]], str]]):
        """
        Args:
            target_path: A string path or a function that accepts task inputs 
                         (args/kwargs dict) and returns a path string.
        """
        self.target_path = target_path

    def _resolve_path(self, inputs: Dict[str, Any]) -> str:
        if callable(self.target_path):
            return self.target_path(inputs)
        return str(self.target_path)

    def check(self, task_id: str, inputs: Dict[str, Any]) -> Any:
        path = self._resolve_path(inputs)
        if os.path.exists(path):
            return path  # Return the path as the cached result
        return None

    def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None:
        # File existence cache usually implies the task itself creates the file.
        # But we can verify it was created.
        path = self._resolve_path(inputs)
        if not os.path.exists(path):
            # In a stricter implementation, we might raise a warning here.
            pass
~~~~~

#### Acts 2: Expose Cache Adapter

方便用户导入。

~~~~~act
write_file
src/cascade/adapters/caching/__init__.py
~~~~~
~~~~~python
from .file_existence import FileExistenceCache

__all__ = ["FileExistenceCache"]
~~~~~

#### Acts 3: Integrate Caching into Engine

在 `Engine` 中集成缓存检查和保存逻辑。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    ResourceAcquired,
    ResourceReleased,
)
~~~~~
~~~~~python
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    ResourceAcquired,
    ResourceReleased,
)
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                results: Dict[str, Any] = {}
                for node in plan:
                    task_start_time = time.time()

                    start_event = TaskExecutionStarted(
                        run_id=run_id, task_id=node.id, task_name=node.name
                    )
                    self.bus.publish(start_event)

                    # Determine retry policy
                    retry_policy = node.retry_policy
~~~~~
~~~~~python
                results: Dict[str, Any] = {}
                for node in plan:
                    task_start_time = time.time()

                    # 0. Check Cache
                    if node.cache_policy:
                        # Construct inputs for cache check
                        # We need to resolve dependencies first to pass them to cache policy
                        # Similar logic to Executor, but just for inputs
                        inputs_for_cache = self._resolve_inputs(node, graph, results)
                        
                        cached_value = node.cache_policy.check(node.id, inputs_for_cache)
                        if cached_value is not None:
                            # Cache Hit!
                            results[node.id] = cached_value
                            self.bus.publish(
                                TaskSkipped(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    reason="CacheHit"
                                )
                            )
                            continue

                    start_event = TaskExecutionStarted(
                        run_id=run_id, task_id=node.id, task_name=node.name
                    )
                    self.bus.publish(start_event)

                    # Determine retry policy
                    retry_policy = node.retry_policy
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                            self.bus.publish(finish_event)
                            # Break the retry loop on success
                            last_exception = None
                            break
~~~~~
~~~~~python
                            self.bus.publish(finish_event)
                            
                            # Save to cache if policy exists
                            if node.cache_policy:
                                # Re-resolve inputs (they are already resolved, but kept in scope)
                                # Optimization: we could calculate inputs once before retry loop
                                inputs_for_save = self._resolve_inputs(node, graph, results)
                                node.cache_policy.save(node.id, inputs_for_save, result)

                            # Break the retry loop on success
                            last_exception = None
                            break
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
~~~~~
~~~~~python
    def _resolve_inputs(self, node: Node, graph: Graph, upstream_results: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to resolve inputs for cache checking."""
        inputs = {}
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            inputs[edge.arg_name] = upstream_results[edge.source.id]
        return inputs

    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
~~~~~

#### Acts 4: Add Caching Tests

编写测试用例验证缓存行为。

~~~~~act
write_file
tests/test_caching.py
~~~~~
~~~~~python
import os
import pytest
import cascade as cs
from cascade.adapters.caching import FileExistenceCache

def test_file_existence_cache_hit(tmp_path):
    """Test that a task is skipped if the target file exists."""
    target_file = tmp_path / "output.txt"
    target_file.touch()  # Create the file to simulate cache hit

    call_count = 0

    @cs.task
    def create_file(path: str):
        nonlocal call_count
        call_count += 1
        return "New Content"

    # Configure cache
    policy = FileExistenceCache(target_path=str(target_file))
    task = create_file(str(target_file)).with_cache(policy)

    result = cs.run(task)

    # Should return the path (cache value), and NOT execute the function
    assert result == str(target_file)
    assert call_count == 0

def test_file_existence_cache_miss(tmp_path):
    """Test that a task runs if the target file does not exist."""
    target_file = tmp_path / "output_miss.txt"

    call_count = 0

    @cs.task
    def create_file(path: str):
        nonlocal call_count
        call_count += 1
        # Create the file to satisfy the cache save contract
        with open(path, "w") as f:
            f.write("content")
        return "Executed"

    policy = FileExistenceCache(target_path=str(target_file))
    task = create_file(str(target_file)).with_cache(policy)

    result = cs.run(task)

    assert result == "Executed"
    assert call_count == 1
    assert target_file.exists()
~~~~~

### 下一步建议
我们已经完成了 Cascade 阶段二的所有核心功能开发（DI、异步、重试、缓存）。
现在的代码库已经具备了“可靠的自动化应用框架”的所有要素。

下一步，为了巩固成果，我建议：
1.  **提交所有更改**: 创建一个 `[COMMIT]` 计划，将当前所有关于缓存和重试的代码变更提交。
2.  **阶段三启动**: 进入阶段三“走向生态与可扩展性”，开始实现 `Shell` 任务和 CLI 集成等功能，进一步提升用户体验。
