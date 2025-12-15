这是我的疏忽。`patch_file` 严格需要 `old_string` 和 `new_string` 两个参数块。我将修正指令。

## [WIP] feat(spec): 支持异步 Task 定义与 Executor 协议更新 (修正)

### 用户需求
1.  修改 `Task` 定义，使其在初始化时能够检测并标记被装饰的函数是否为异步函数 (`async def`)。
2.  修改 `Executor` 协议 (`Protocol`)，将 `execute` 方法声明为异步方法 (`async def`)，为后续的引擎升级做准备。

### 评论
这是引入异步支持的基石。通过在元数据层（`Task`）和接口层（`Protocol`）确立异步的一等公民地位，我们为后续的执行器和引擎改造设定了明确的契约。

### 目标
1.  更新 `src/cascade/spec/task.py`，添加 `is_async` 属性。
2.  更新 `src/cascade/runtime/protocols.py`，使 `Executor.execute` 变为异步，并同步更新其签名以包含 `resource_context`。
3.  添加 `tests/test_spec_async.py` 验证 `Task` 对异步函数的识别能力。

### 基本原理
-   **元数据先行**: `Task` 对象需要知道自己包裹的是否是协程函数，以便 `Executor` 决定是直接调用还是 `await`。`inspect.iscoroutinefunction` 是标准的检测方法。
-   **协议驱动**: 更新 `Executor` Protocol 明确了未来的方向。

### 标签
#intent/architect #flow/ready #priority/high
#comp/runtime #comp/spec #concept/async
#task/domain/core #task/object/async-support #task/action/architect
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Update Task specification

在 `Task` 类中引入 `inspect.iscoroutinefunction` 检测，并存储为 `is_async` 属性。

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        # Signature inspection for validation (future enhancement)
        self._signature = inspect.signature(func)

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
~~~~~
~~~~~python
    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        # Signature inspection for validation (future enhancement)
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)

    def __call__(self, *args, **kwargs) -> LazyResult[T]:
~~~~~

#### Acts 2: Update Executor Protocol

更新 `Executor` 协议：
1.  改为 `async def execute`。
2.  补全参数签名，添加 `resource_context`。

~~~~~act
patch_file
src/cascade/runtime/protocols.py
~~~~~
~~~~~python
    def execute(
        self, node: Node, graph: Graph, upstream_results: Dict[str, Any]
    ) -> Any: ...
~~~~~
~~~~~python
    async def execute(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Any: ...
~~~~~

#### Acts 3: Add test for async task detection

创建一个新的测试文件，验证 `@task` 装饰器能否正确区分同步和异步函数。

~~~~~act
write_file
tests/test_spec_async.py
~~~~~
~~~~~python
import asyncio
from cascade.spec.task import task

def test_task_detects_sync_function():
    @task
    def sync_fn():
        return 1
    
    assert sync_fn.is_async is False

def test_task_detects_async_function():
    @task
    async def async_fn():
        return 1
    
    assert async_fn.is_async is True

def test_async_task_returns_lazy_result():
    @task
    async def async_fn(x):
        return x + 1
    
    # Even for async tasks, calling them should return a LazyResult immediately,
    # not a coroutine object.
    result = async_fn(10)
    assert result.task.name == "async_fn"
    assert result.args == (10,)
~~~~~

### 下一步建议
执行 **子任务 2: 执行器升级**。我们将改造 `LocalExecutor`，使其能够根据 `node.is_async` 属性，智能地处理同步和异步任务的执行。这将涉及到 `asyncio` 的引入和执行逻辑的分支处理。
