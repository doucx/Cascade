你对代码冗余的直觉非常敏锐。经过仔细检查，我发现你指出的 `Param` 定义确实是冗余的，但它之所以还存在，是因为有一个核心模块（`cascade-graph`）仍在错误地引用它。

这是一个典型的技术债务案例：新架构（`InputSpec`）已经引入，但旧的依赖关系没有被完全清理干净。

我将生成一个两步计划来安全地完成这项清理工作：首先，我会修正 `Node` 模型的依赖关系，然后彻底删除那个冗余的文件。

## [WIP] refactor(spec): 移除冗余的 Param 定义并清理依赖

### 用户需求
1.  移除 `cascade-spec/src/cascade/spec/common.py` 中过时的 `Param` dataclass 定义。
2.  确保 `cascade-graph/src/cascade/graph/model.py` 中的 `Node` 模型不再引用旧的 `Param` 类，而是使用新的 `ParamSpec`。

### 评论
这是一次重要的架构一致性修复。`cascade-sdk` 引入的 `cs.Param()` 工厂函数和 `ParamSpec` 体系是未来的方向。`cascade-graph` 模块对旧 `spec.common.Param` 的残留引用是导致该冗余代码无法被移除的根本原因。本次修改将彻底切断这种依赖，使 `ParamSpec` 成为 `Node` 模型中参数元数据的唯一事实来源。

### 目标
1.  修改 `cascade-graph/src/cascade/graph/model.py` 文件，将其对 `Param` 的类型引用更新为 `ParamSpec`。
2.  删除 `cascade-spec/src/cascade/spec/common.py` 文件，因为它在修复依赖后将不再被任何代码使用。

### 基本原理
我们将首先修正消费端的代码。通过将 `Node.param_spec` 的类型注解从 `Optional[Param]` 更改为 `Optional[ParamSpec]`，并更新相应的 `import` 语句，我们解除了 `cascade-graph` 对 `common.py` 的依赖。一旦这个依赖被解除，`common.py` 就成为了一个可以被安全删除的孤立文件，从而完成本次代码清理。

### 标签
#intent/refine #flow/ready #priority/high
#comp/graph #comp/spec #concept/type-safety #concept/dependency-graph #scope/core #scope/dx
#ai/instruct
#task/domain/spec #task/object/param-definition #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 更新 Node 模型以使用 ParamSpec

这是关键的第一步。我们将 `Node` 的定义从依赖旧的 `Param` 切换到新的 `ParamSpec`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint


class EdgeType(Enum):
    """Defines the semantic type of a dependency edge."""

    DATA = (
        auto()
    )  # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()  # A control dependency for the run_if condition
    CONSTRAINT = auto()  # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()  # An implicit structural dependency
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
    POTENTIAL = auto()  # A potential flow path inferred via static analysis (e.g. TCO)
    ITERATIVE_JUMP = auto()  # An explicit state transition (Jump)


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
    signature: Optional[inspect.Signature] = None  # Cached signature for performance
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
~~~~~
~~~~~python
from cascade.spec.input import ParamSpec
from cascade.spec.constraint import ResourceConstraint


class EdgeType(Enum):
    """Defines the semantic type of a dependency edge."""

    DATA = (
        auto()
    )  # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()  # A control dependency for the run_if condition
    CONSTRAINT = auto()  # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()  # An implicit structural dependency
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
    POTENTIAL = auto()  # A potential flow path inferred via static analysis (e.g. TCO)
    ITERATIVE_JUMP = auto()  # An explicit state transition (Jump)


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
    signature: Optional[inspect.Signature] = None  # Cached signature for performance
    param_spec: Optional[ParamSpec] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
~~~~~

#### Acts 2: 删除冗余的 common.py 文件

在 `Node` 的依赖被修复后，`common.py` 文件现在是完全多余的了，我们可以安全地删除它。

~~~~~act
delete_file
packages/cascade-spec/src/cascade/spec/common.py
~~~~~

### 下一步建议
我们已经成功地移除了冗余代码并修复了核心模型的依赖关系。现在是时候将这些改进提交到版本控制中了。

如果你同意，我将生成一个 `[COMMIT]` 计划。
