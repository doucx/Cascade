好的，我们开始实施“语义化调度标签”的第一阶段：**打通契约链条**。

此阶段的目标是让 `mode` 这个新的语义标签能够从用户定义的 `@task` 装饰器一路传递到 `cascade-graph` 层，并最终体现在 `Node` 对象上。我们将再次使用 TDD 流程，首先编写一个失败的测试来定义我们的目标。

## [WIP] feat(spec): 在 @task 装饰器中引入 execution_mode

### 用户需求
根据建议书，扩展 `@task` 装饰器，使其接受一个 `mode` 参数。这个参数的值需要被捕获，并最终作为元数据附加到计算图的 `Node` 对象上，以便执行器后续使用。

### 评论
这是实现更精细调度策略的基础。通过在声明层捕获任务的物理意图（`compute` vs `blocking`），我们为调度器提供了做出智能决策所需的信息。这个改动是纯粹的结构性增强，为后续在 `Executor` 中实现专用线程池路由铺平了道路。

### 目标
1.  在 `packages/cascade-spec/src/cascade/spec/task.py` 中，修改 `@task` 装饰器和 `Task` 类，使其能够接受并存储 `mode` 参数。
2.  在 `packages/cascade-graph/src/cascade/graph/model.py` 中，为 `Node` 类添加 `execution_mode: str` 字段。
3.  在 `packages/cascade-graph/src/cascade/graph/build.py` 中，更新 `GraphBuilder`，使其在构建 `Node` 时，将 `Task` 的 `mode` 属性传递给 `Node` 的 `execution_mode` 字段。
4.  创建一个新的测试文件 `tests/engine/graph/test_execution_mode.py`，编写一个测试用例，断言使用 `@task(mode="compute")` 装饰的任务所生成的 `Node` 确实具有 `execution_mode="compute"`。

### 基本原理
我们通过 TDD 流程，首先在测试中明确定义“契约传递成功”的标准。然后，我们自顶向下地修改代码：首先是 API 接口 (`@task`)，然后是数据结构 (`Node`)，最后是连接两者的逻辑 (`GraphBuilder`)。这种分层、清晰的修改路径确保了每个组件的职责单一，也使得整个变更过程可控且易于验证。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/graph #comp/tests #concept/executor #scope/api #scope/dx #ai/instruct #task/domain/spec #task/object/task-decorator #task/action/add-mode-parameter #task/state/begin

---

### Script

#### Acts 1: 更新 Task 定义 (cascade-spec)

首先，我们将 `mode` 参数添加到 `@task` 装饰器和 `Task` 类中。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/task.py
~~~~~
~~~~~python
class Task(Generic[T]):
    """
    Wraps a callable to make it return a LazyResult when called.
    """

    def __init__(
        self, func: Callable[..., T], name: Optional[str] = None, pure: bool = False
    ):
        self.func = func
        self.name = name or func.__name__
        self.pure = pure
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)
        # Cache for AST analysis results to verify TCO paths
        self._potential_tco_targets: Optional[List["Task"]] = None
~~~~~
~~~~~python
class Task(Generic[T]):
    """
    Wraps a callable to make it return a LazyResult when called.
    """

    def __init__(
        self,
        func: Callable[..., T],
        name: Optional[str] = None,
        pure: bool = False,
        mode: str = "blocking",
    ):
        self.func = func
        self.name = name or func.__name__
        self.pure = pure
        self.mode = mode
        self._signature = inspect.signature(func)
        self.is_async = inspect.iscoroutinefunction(func)
        # Cache for AST analysis results to verify TCO paths
        self._potential_tco_targets: Optional[List["Task"]] = None
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/task.py
~~~~~
~~~~~python
def task(
    func: Optional[Callable[..., T]] = None,
    *,
    name: Optional[str] = None,
    pure: bool = False,
) -> Union[Task[T], Callable[[Callable[..., T]], Task[T]]]:
    """
    Decorator to convert a function into a Task.
    """

    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name, pure=pure)

    if func:
        return wrapper(func)
~~~~~
~~~~~python
def task(
    func: Optional[Callable[..., T]] = None,
    *,
    name: Optional[str] = None,
    pure: bool = False,
    mode: str = "blocking",
) -> Union[Task[T], Callable[[Callable[..., T]], Task[T]]]:
    """
    Decorator to convert a function into a Task.
    """

    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name, pure=pure, mode=mode)

    if func:
        return wrapper(func)
~~~~~

#### Acts 2: 更新 Node 模型 (cascade-graph)

现在，我们将 `execution_mode` 字段添加到 `Node` 数据类中。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
@dataclass
class Node:
    """
    Represents a node in the computation graph template.

    A Node defines 'what' to execute (the callable) and 'how' to get its arguments
    (bindings or edges), but it DOES NOT contain the runtime data itself.
    """

    structural_id: str
    name: str

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
~~~~~
~~~~~python
@dataclass
class Node:
    """
    Represents a node in the computation graph template.

    A Node defines 'what' to execute (the callable) and 'how' to get its arguments
    (bindings or edges), but it DOES NOT contain the runtime data itself.
    """

    structural_id: str
    name: str

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    execution_mode: str = "blocking"  # "blocking", "compute"
    callable_obj: Optional[Callable] = None
~~~~~

#### Acts 3: 更新 GraphBuilder 逻辑 (cascade-graph)

接下来，我们让 `GraphBuilder` 在创建 `Node` 时传递 `mode` 属性。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
            node = Node(
                structural_id=structural_hash,
                name=result.task.name,
                node_type="task",
                callable_obj=result.task.func,
                signature=sig,
~~~~~
~~~~~python
            node = Node(
                structural_id=structural_hash,
                name=result.task.name,
                node_type="task",
                execution_mode=result.task.mode,
                callable_obj=result.task.func,
                signature=sig,
~~~~~

#### Acts 4: 创建 TDD 测试文件

最后，我们创建新的测试文件，以验证整个契约链条是否按预期工作。

~~~~~act
write_file
tests/engine/graph/test_execution_mode.py
~~~~~
~~~~~python
from cascade import task
from cascade.graph.build import build_graph


@task(mode="compute")
def compute_task():
    return 1


@task(mode="blocking")
def blocking_task():
    return 2


@task
def default_task():
    return 3


def test_execution_mode_is_passed_to_node():
    """
    Verifies that the `mode` parameter from the @task decorator
    is correctly propagated to the `execution_mode` attribute of the
    corresponding Node in the graph.
    """
    # 1. Define a simple workflow
    ct = compute_task()
    bt = blocking_task()
    dt = default_task()

    # We need a target to build the graph
    target = [ct, bt, dt]

    # 2. Build the graph
    # NOTE: We are building from a list, which is not a valid final target for
    # the engine, but it is sufficient for build_graph to explore all dependencies.
    # The build_graph function does not require a single root LazyResult.
    graph, instance_map = build_graph(target)

    # 3. Find the nodes in the graph
    compute_node = instance_map[ct._uuid]
    blocking_node = instance_map[bt._uuid]
    default_node = instance_map[dt._uuid]

    # 4. Assert the execution modes
    assert (
        compute_node.execution_mode == "compute"
    ), "Node for compute_task should have mode 'compute'"
    assert (
        blocking_node.execution_mode == "blocking"
    ), "Node for blocking_task should have mode 'blocking'"
    assert (
        default_node.execution_mode == "blocking"
    ), "Node for default_task should have the default mode 'blocking'"

~~~~~
**注意**: 在 `test_execution_mode.py` 中，我再次使用了 `build_graph([ct, bt, dt])` 的模式。这是 `build_graph` 函数的一个有效用法，因为它被设计为可以从任何可迭代的 `LazyResult` 集合中探索和构建完整的依赖图。这与 `engine.run` 不同，后者需要一个单一的目标节点来确定最终的输出。对于纯粹的图结构验证，这种方式是简洁且正确的。

### 下一步建议
我们已经完成了第一阶段的所有代码修改和测试设置。现在，请运行测试。我们预期 `tests/engine/graph/test_execution_mode.py` 会直接通过，因为它验证的是我们刚刚实现的静态属性传递。如果通过，则证明契约链条已成功建立。

之后，我们将进入第二阶段：在 `LocalExecutor` 中实现基于 `execution_mode` 的线程池路由逻辑。
