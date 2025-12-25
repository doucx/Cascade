这是一个用于引入任务纯度模型 (Task Purity Model) 的第一阶段计划。

为了能够编写测试用例来验证 CP-006 的行为，我们需要首先在 API 层面引入 `pure` 参数的支持。

**本计划将执行以下操作：**
1.  **API 准备**：修改 `Task` 类和 `task` 装饰器，使其能够接收并存储 `pure` 属性（默认为 `False`）。这一步**不会**改变底层的哈希逻辑，因此 Impure 任务暂时仍会被去重。
2.  **创建测试 (RED)**：创建一个新的测试文件，断言“Impure 任务应该生成不同的 ID”以及“Pure 任务应该生成相同的 ID”。由于哈希逻辑尚未修改，针对 Impure 任务的断言预期会**失败**，从而让我们进入一个有效的 RED 状态。

## 简要回答
我将修改 `Task` 定义以支持 `pure` 参数，并创建一个测试文件来验证 ID 生成行为，预期该测试最初会失败。

## [WIP] feat(spec): 引入 pure 参数并添加行为验证测试

### 用户需求
实现 CP-006 提案，将任务分为默认的“副作用任务 (Impure)”和显式的“纯函数任务 (Pure)”。Impure 任务应具有唯一的实例标识，而 Pure 任务应支持结构化去重。

### 评论
当前系统默认对所有任务进行结构化去重 (Hash-Consing)，这对于包含副作用（如随机数生成、数据库写入）的任务来说是不直观且危险的。本计划是 TDD 流程的第一步：定义 API 并暴露当前行为与期望行为之间的差距。

### 目标
1.  修改 `cascade-spec` 中的 `Task` 类，增加 `pure` 字段。
2.  更新 `@task` 装饰器以支持 `pure=True` 参数。
3.  创建一个测试用例 `tests/core/test_purity_model.py`，证明当前系统无法区分两个相同的 Impure 任务实例。

### 基本原理
我们遵循 TDD 原则。首先定义接口（API），然后编写一个在当前实现下会失败的测试（RED）。只有在下一个计划中修改了哈希逻辑后，测试才会通过（GREEN）。

### 标签
#intent/build #flow/draft #priority/high #comp/spec #comp/tests #concept/state #scope/core #ai/instruct #task/domain/core #task/object/task-purity #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新 Task 定义以支持 Purity 属性

我们需要在 `Task` 类和 `@task` 装饰器中添加 `pure` 参数。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/task.py
~~~~~
~~~~~python
class Task(Generic[T]):
    """
    Wraps a callable to make it return a LazyResult when called.
    """

    def __init__(self, func: Callable[..., T], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self._signature = inspect.signature(func)
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
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/task.py
~~~~~
~~~~~python
def task(
    func: Optional[Callable[..., T]] = None, *, name: Optional[str] = None
) -> Union[Task[T], Callable[[Callable[..., T]], Task[T]]]:
    """
    Decorator to convert a function into a Task.
    """

    def wrapper(f: Callable[..., T]) -> Task[T]:
        return Task(f, name=name)

    if func:
        return wrapper(func)
    else:
        return wrapper
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
    else:
        return wrapper
~~~~~

#### Acts 2: 创建 TDD 测试用例 (Expect Failure)

我们创建一个测试，明确断言 Impure 任务的实例 ID 必须不同，而 Pure 任务的实例 ID 必须相同。

~~~~~act
write_file
tests/core/test_purity_model.py
~~~~~
~~~~~python
import pytest
from cascade.spec.task import task
from cascade.graph.build import build_graph


def test_impure_tasks_have_unique_identities():
    """
    验证默认任务（Impure）是否具有唯一的结构标识。
    
    场景：
    我们调用同一个任务两次，即使参数相同。
    
    期望（CP-006）：
    系统应将它们视为图中的两个独立节点，具有不同的 structural_id。
    
    当前行为（Fail）：
    系统通过 Hash-Consing 将它们合并为一个节点。
    """
    @task  # 默认 pure=False
    def random_int():
        return 42

    # 创建两个实例
    a = random_int()
    b = random_int()

    # 构建图
    # 注意：我们需要一个虚拟的目标来包含这两个节点，或者分别构建
    # 这里为了简单，我们检查构建后的节点 ID
    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)
    
    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # 断言：对于副作用任务，即使函数和参数完全相同，它们也是不同的实体
    assert node_a.structural_id != node_b.structural_id, (
        "Impure tasks (default) must have unique structural IDs to avoid incorrect deduplication."
    )


def test_pure_tasks_are_deduplicated():
    """
    验证纯函数任务（Pure）是否被正确去重。
    """
    @task(pure=True)
    def add(x, y):
        return x + y

    a = add(1, 2)
    b = add(1, 2)

    graph_a, instance_map_a = build_graph(a)
    graph_b, instance_map_b = build_graph(b)

    node_a = instance_map_a[a._uuid]
    node_b = instance_map_b[b._uuid]

    # 断言：纯函数任务应基于内容寻址（Content-Addressable）
    assert node_a.structural_id == node_b.structural_id, (
        "Pure tasks must be deduplicated based on their content (function + args)."
    )
~~~~~

### 下一步建议
一旦执行此计划，请运行测试 `pytest tests/core/test_purity_model.py`。
预期结果：`test_impure_tasks_have_unique_identities` 将会**失败**。
这将确认我们处于正确的 RED 状态。接下来的计划将修改 `HashingService` 来修复此测试。
