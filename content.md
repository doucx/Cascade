这是一个实现资源感知调度基础架构的计划。我们将在核心规范层 (`spec`) 和图模型层 (`graph`) 引入资源约束的概念，而不引入新的外部依赖。

## [WIP] feat(core): 引入 Node 资源约束与调度感知

### 用户需求
增强 `Node` 模型以支持声明资源约束（例如 `memory_gb`, `gpu_count`），并修改 `GraphBuilder` 以便将这些约束从任务定义传递到计算图节点中。这是为了支持未来高级调度器（如 CSPSolver）进行资源检查和分配的基础性工作。

### 评论
该任务是实现高级调度和健壮性管理的关键步骤。它遵循洋葱架构原则，在核心模型中完成元数据的添加和必要的类型检查，而将具体的求解逻辑留给适配器层。通过在 `LazyResult` 和 `Node` 中显式建模约束，我们为构建资源感知的 DAG 奠定了数据基础。

### 目标
1.  创建 `src/cascade/spec/constraint.py`，定义 `ResourceConstraint` 规范。
2.  修改 `src/cascade/spec/task.py`，允许 `LazyResult` 通过 `.with_constraints()` 方法链式添加约束。
3.  修改 `src/cascade/graph/model.py` 中的 `Node` 定义，添加 `constraints` 字段。
4.  更新 `src/cascade/graph/build.py`，在构建图时传递约束信息。
5.  在顶级包中暴露 `with_constraints` 辅助函数。

### 基本原理
资源约束本质上是任务的静态元数据。将其定义在 `spec` 层并固化到 `Node` 模型中，确保了约束数据能随着计算图一起流转。这允许执行引擎或调度器在运行时访问这些信息，而无需反向查找任务定义。

### 标签
#intent/architect #flow/ready #priority/high #comp/core #comp/runtime #concept/solver #task/domain/core #task/object/resource-constraint #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义约束规范

创建一个新的模块来保存 `ResourceConstraint` 数据结构定义。

~~~~~act
write_file
src/cascade/spec/constraint.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ResourceConstraint:
    """
    Defines the resource requirements for a Task.
    
    The keys represent the resource name (e.g., "memory_gb", "gpu_count")
    and the values represent the required amount (literal value or a LazyResult).
    """
    
    requirements: Dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.requirements

    def __bool__(self):
        return not self.is_empty()

def with_constraints(**kwargs) -> ResourceConstraint:
    """Helper function for task definitions."""
    return ResourceConstraint(requirements=kwargs)
~~~~~

#### Acts 2: 扩展 LazyResult API

更新 `LazyResult`，使其支持 `.with_constraints()` 链式调用，并在模块中引入新的约束类型。

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
# Import protocols only for type hinting to avoid circular imports if possible
# But here we just need Any or "CachePolicy" forward ref
from cascade.runtime.protocols import CachePolicy, LazyFactory

T = TypeVar("T")
~~~~~
~~~~~python
# Import protocols only for type hinting to avoid circular imports if possible
# But here we just need Any or "CachePolicy" forward ref
from cascade.runtime.protocols import CachePolicy, LazyFactory
from cascade.spec.constraint import ResourceConstraint

T = TypeVar("T")
~~~~~

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[CachePolicy] = None
    _condition: Optional["LazyResult"] = None

    def __hash__(self):
~~~~~
~~~~~python
    _uuid: str = field(default_factory=lambda: str(uuid4()))
    _retry_policy: Optional[RetryPolicy] = None
    _cache_policy: Optional[CachePolicy] = None
    _condition: Optional["LazyResult"] = None
    _constraints: Optional[ResourceConstraint] = None

    def __hash__(self):
~~~~~

~~~~~act
patch_file
src/cascade/spec/task.py
~~~~~
~~~~~python
    def with_cache(self, policy: CachePolicy) -> "LazyResult[T]":
        """Configures caching strategy for this task."""
        self._cache_policy = policy
        return self
~~~~~
~~~~~python
    def with_cache(self, policy: CachePolicy) -> "LazyResult[T]":
        """Configures caching strategy for this task."""
        self._cache_policy = policy
        return self

    def with_constraints(self, **kwargs) -> "LazyResult[T]":
        """
        Attaches resource constraints to this task.
        e.g., .with_constraints(memory_gb=4, gpu_count=1)
        """
        self._constraints = ResourceConstraint(requirements=kwargs)
        return self
~~~~~

#### Acts 3: 扩展 Graph Model

在 `Node` 数据模型中添加 `constraints` 字段。

~~~~~act
patch_file
src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict


from cascade.spec.common import Param
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict


from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint
~~~~~

~~~~~act
patch_file
src/cascade/graph/model.py
~~~~~
~~~~~python
    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None

    # Pre-resolved literal inputs for the task
~~~~~
~~~~~python
    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Pre-resolved literal inputs for the task
~~~~~

#### Acts 4: 扩展 Graph Builder

在 `GraphBuilder` 中提取约束信息并将其传递给 `Node` 构造函数。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
        )
        self.graph.add_node(node)
~~~~~
~~~~~python
        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
        )
        self.graph.add_node(node)
~~~~~

#### Acts 5: 暴露新的 API

在顶级 `__init__.py` 中暴露 `with_constraints` 辅助函数。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
~~~~~
~~~~~python
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json
from .spec.constraint import with_constraints

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
~~~~~

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
    "cli",
    "to_json",
    "from_json",
    "LazyResult",
    "Router",
~~~~~
~~~~~python
    "cli",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
~~~~~

#### Acts 6: 添加测试

验证约束的定义、传递和在图中的存在性。

~~~~~act
write_file
tests/spec/test_constraint.py
~~~~~
~~~~~python
import cascade as cs
from cascade.graph.build import build_graph
from cascade.spec.constraint import ResourceConstraint


def test_resource_constraint_definition():
    """Test the basic definition of ResourceConstraint."""
    constraints = cs.with_constraints(gpu_count=1, memory_gb=8)
    
    assert isinstance(constraints, ResourceConstraint)
    assert constraints.requirements["gpu_count"] == 1
    assert not constraints.is_empty()
    assert bool(constraints) is True


def test_lazy_result_constraint_chaining():
    """Test that .with_constraints is chainable and attaches metadata."""
    @cs.task
    def heavy_task():
        pass
    
    lazy_result = heavy_task().with_constraints(cpu_cores=4)
    
    assert lazy_result._constraints is not None
    assert lazy_result._constraints.requirements["cpu_cores"] == 4


def test_constraint_propagation_to_node():
    """Test that the constraint metadata is correctly stored on the graph node."""
    @cs.task
    def heavy_task():
        pass
    
    target = heavy_task().with_constraints(io_bandwidth="high")
    graph = build_graph(target)
    
    node = next(n for n in graph.nodes if n.name == "heavy_task")
    
    assert node.constraints is not None
    assert isinstance(node.constraints, ResourceConstraint)
    assert node.constraints.requirements["io_bandwidth"] == "high"
~~~~~

### 下一步建议
元数据层已就绪。为了保证系统的完整性，建议下一步：
1.  **更新序列化模块** (`src/cascade/graph/serialize.py`)：使其支持 `ResourceConstraint` 的序列化与反序列化，防止数据在持久化过程中丢失。
2.  **实现占位符调度逻辑**：修改 `NativeSolver` 或 `Engine`，添加一个简单的检查点，虽然暂时不进行复杂的 CSP 求解，但可以验证约束数据在运行时是可访问的。
